"""Tasks window: filters and lists on the left, quick entry and task table on the right."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import QDateTime, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import DATA_ROLE, EmptyState, Table, item
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.reminders import logic as reminders
from desktop_organizer.tools.tasks import SETTINGS
from desktop_organizer.tools.tasks.logic import (
    FILTERS,
    Task,
    counts,
    create,
    delete,
    delete_done,
    get,
    lists,
    query,
    set_done,
    update,
)

TOOL = "tasks"
FILTER_ICONS = {
    "open": "list-checks",
    "today": "calendar",
    "overdue": "circle-alert",
    "upcoming": "calendar-check",
    "done": "check",
}


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class TaskDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        task: Task | None,
        list_names: list[str],
        has_reminder: bool,
        lead: int,
        default_hour: int,
        language: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("edit") if task else t("new"))
        self.setMinimumWidth(560)
        self.title = QLineEdit(task.title if task else "")
        self.notes = QPlainTextEdit(task.notes if task else "")
        self.notes.setMaximumHeight(120)
        self.has_due = QCheckBox(t("field.has_due"))
        self.due = QDateTimeEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("dd.MM.yyyy HH:mm" if language == "de" else "yyyy-MM-dd HH:mm")
        default_due = datetime.now().replace(
            hour=default_hour, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        self.due.setDateTime(
            QDateTime.fromSecsSinceEpoch(
                int(task.due if task and task.due else default_due.timestamp())
            )
        )
        self.has_due.setChecked(bool(task and task.due))
        self.priority = QComboBox()
        for value in (2, 1, 0):
            self.priority.addItem(t(f"priority.{value}"), value)
        self.priority.setCurrentIndex(self.priority.findData(task.priority if task else 1))
        self.list_name = QComboBox()
        self.list_name.setEditable(True)
        self.list_name.addItem("")
        self.list_name.addItems(list_names)
        self.list_name.setCurrentText(task.list if task else "")
        line = self.list_name.lineEdit()
        if line is not None:
            line.setPlaceholderText(t("field.list.placeholder"))
        self.remind = QCheckBox(t("field.remind"))
        self.remind.setChecked(has_reminder)
        self.lead = QSpinBox()
        self.lead.setRange(0, 10080)
        self.lead.setValue(lead)
        self.lead.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.lead.setSuffix(f" {t('minutes_before')}")
        self.has_due.toggled.connect(self._update)
        self.remind.toggled.connect(self._update)
        due_row = QHBoxLayout()
        due_row.addWidget(self.has_due)
        due_row.addWidget(self.due, 1)
        remind_row = QHBoxLayout()
        remind_row.addWidget(self.remind)
        remind_row.addWidget(self.lead, 1)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        form.addRow(t("field.title"), self.title)
        form.addRow(t("field.due"), due_row)
        form.addRow(t("field.reminder"), remind_row)
        form.addRow(t("field.priority"), self.priority)
        form.addRow(t("field.list"), self.list_name)
        form.addRow(t("field.notes"), self.notes)
        self.error = QLabel()
        self.error.setProperty("textStyle", "error")
        save = QPushButton(tr("common.save"))
        save.setProperty("role", "primary")
        save.setDefault(True)
        save.clicked.connect(self._accept)
        cancel = QPushButton(tr("common.cancel"))
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        self._update()

    def _update(self) -> None:
        self.due.setEnabled(self.has_due.isChecked())
        self.remind.setEnabled(self.has_due.isChecked())
        self.lead.setEnabled(self.has_due.isChecked() and self.remind.isChecked())

    def _accept(self) -> None:
        if not self.title.text().strip():
            self.error.setText(t("error.title"))
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        due = float(self.due.dateTime().toSecsSinceEpoch()) if self.has_due.isChecked() else None
        return {
            "title": self.title.text().strip(),
            "due": due,
            "priority": int(self.priority.currentData()),
            "list": self.list_name.currentText().strip(),
            "notes": self.notes.toPlainText(),
            "remind": bool(due and self.remind.isChecked()),
            "lead": self.lead.value(),
        }


class TasksWindow(ToolWindow):
    tool_id = TOOL
    icon = "list-checks"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.conn = context.database.connection
        self._filter = self.option("default_filter")
        self._list = ""

        self.nav = QListWidget()
        self.nav.setIconSize(QSize(18, 18))
        self.nav.currentItemChanged.connect(self._nav_changed)
        left = QFrame()
        left.setObjectName("Panel")
        left.setMinimumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.nav)

        self.quick = QLineEdit()
        self.quick.addAction(
            context.theme.icon("plus", secondary=True), QLineEdit.ActionPosition.LeadingPosition
        )
        self.quick.returnPressed.connect(self.quick_add)
        self.details_button = QPushButton()
        self.details_button.clicked.connect(self.new_task)
        self.filter_text = QLineEdit()
        self.filter_text.setClearButtonEnabled(True)
        self.filter_text.setMaximumWidth(260)
        self.filter_text.textChanged.connect(lambda _t: self.refresh())
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        quick_row.addWidget(self.quick, 1)
        quick_row.addWidget(self.details_button)
        quick_row.addWidget(self.filter_text)

        self.heading_label = QLabel()
        self.heading_label.setProperty("textStyle", "subtitle")
        self.table = Table(4)
        self.table.setColumnWidth(1, 240)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 150)
        self.table.doubleClicked.connect(lambda i: self.edit(self._id(self.table.source_row(i))))
        self.table.source.itemChanged.connect(self._checked)
        self.table.context_requested.connect(self._menu)
        self.empty = EmptyState(context.theme, "list-checks")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addLayout(quick_row)
        right_layout.addWidget(self.heading_label)
        right_layout.addWidget(self.table, 1)
        right_layout.addWidget(self.empty, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([250, 850])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        self.summary = QLabel()
        self.summary.setProperty("textStyle", "caption")
        self.clear_done_button = QPushButton()
        self.clear_done_button.clicked.connect(self.clear_done)
        self.footer.addWidget(self.summary, 1)
        self.footer.addWidget(self.clear_done_button)

        dialogs.shortcut("Ctrl+N", self, lambda: self.quick.setFocus())
        timer = QTimer(self)
        timer.timeout.connect(self.refresh)
        timer.start(60_000)  # "today" and "overdue" change with the clock
        self.retranslate()

    # -- texts and navigation ---------------------------------------------------------------

    def retranslate(self) -> None:
        self.quick.setPlaceholderText(t("quick"))
        self.details_button.setText(t("new_detailed"))
        self.filter_text.setPlaceholderText(tr("common.search"))
        self.table.set_headers([t("col.title"), t("col.due"), t("col.priority"), t("col.list")])
        self.clear_done_button.setText(t("clear_done"))
        self.refresh()

    def _fill_nav(self) -> None:
        number = counts(self.conn)
        self.nav.blockSignals(True)
        self.nav.clear()
        selected = None
        for name in FILTERS:
            entry = QListWidgetItem(
                self.context.theme.icon(FILTER_ICONS[name], secondary=True),
                f"{self._filter_label(name)}   {number[name]}",
            )
            entry.setData(Qt.ItemDataRole.UserRole, ("filter", name))
            self.nav.addItem(entry)
            if not self._list and name == self._filter:
                selected = entry
        task_lists = lists(self.conn)
        if task_lists:
            header = QListWidgetItem(t("lists"))
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = QFont(header.font())
            font.setWeight(QFont.Weight.DemiBold)
            header.setFont(font)
            self.nav.addItem(header)
            for name, open_count in task_lists:
                entry = QListWidgetItem(
                    self.context.theme.icon("folder", secondary=True), f"{name}   {open_count}"
                )
                entry.setData(Qt.ItemDataRole.UserRole, ("list", name))
                self.nav.addItem(entry)
                if self._list == name:
                    selected = entry
        if selected is not None:
            self.nav.setCurrentItem(selected)
        self.nav.blockSignals(False)

    def _filter_label(self, name: str) -> str:
        return {
            "open": t("filter.open"),
            "today": t("filter.today"),
            "overdue": t("filter.overdue"),
            "upcoming": t("filter.upcoming"),
            "done": t("filter.done"),
        }[name]

    def _nav_changed(self, current: QListWidgetItem | None, _prev: object) -> None:
        if current is None:
            return
        kind, name = current.data(Qt.ItemDataRole.UserRole)
        if kind == "filter":
            self._filter, self._list = name, ""
        else:
            self._filter, self._list = "open", name
        self.refresh()

    # -- table -----------------------------------------------------------------------------------

    def refresh(self) -> None:
        lang = self.context.translator.language
        self._fill_nav()
        tasks = query(self.conn, self._filter, self._list, text=self.filter_text.text().strip())
        now = time.time()
        self.heading_label.setText(self._list or self._filter_label(self._filter))
        self._filling = True
        self.table.setSortingEnabled(False)
        self.table.clear_rows()
        for task in tasks:
            title = item(task.title, data=task.id, checkable=True)
            title.setCheckState(Qt.CheckState.Checked if task.done else Qt.CheckState.Unchecked)
            if task.notes:
                title.setToolTip(task.notes)
            if task.done:
                font = QFont(title.font())
                font.setStrikeOut(True)
                title.setFont(font)
            due_text = format_datetime(task.due, lang) if task.due else ""
            due = item(due_text, sort=task.due or 9e15)
            if task.due and task.due < now and not task.done:
                due.setForeground(self._error_brush())
                due.setText(f"{due_text}  ·  {t('overdue')}")
            self.table.source.appendRow(
                [
                    title,
                    due,
                    item(t(f"priority.{task.priority}"), sort=-task.priority),
                    item(task.list),
                ]
            )
        self.table.setSortingEnabled(True)
        self._filling = False
        self.table.setVisible(bool(tasks))
        self.empty.setVisible(not tasks)
        self.empty.set_texts(
            t("empty.title"), t(f"empty.{self._filter}") if not self._list else t("empty.list")
        )
        number = counts(self.conn)
        self.summary.setText(
            t("summary", open=number["open"], today=number["today"], overdue=number["overdue"])
        )
        self.clear_done_button.setEnabled(number["done"] > 0)

    def _error_brush(self) -> Any:
        from PySide6.QtGui import QBrush, QColor

        return QBrush(QColor(self.context.theme.tokens.error))

    def _id(self, row: int) -> int:
        return int(self.table.source.item(row, 0).data(DATA_ROLE))

    def _checked(self, cell: Any) -> None:
        if getattr(self, "_filling", False) or cell.column() != 0:
            return
        set_done(self.conn, self._id(cell.row()), cell.checkState() == Qt.CheckState.Checked)
        QTimer.singleShot(150, self.refresh)

    # -- editing --------------------------------------------------------------------------------

    def quick_add(self) -> None:
        text = self.quick.text().strip()
        if not text:
            return
        due = None
        if self._filter == "today" and not self._list:
            due = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0).timestamp()
        create(self.conn, text, due=due, list_name=self._list)
        self.quick.clear()
        self.refresh()

    def _dialog(self, task: Task | None) -> TaskDialog:
        has_reminder = bool(task and reminders.for_task(self.conn, task.id))
        return TaskDialog(
            self,
            task,
            [name for name, _ in lists(self.conn)],
            has_reminder,
            self.option("reminder_lead_minutes"),
            self.option("default_due_hour"),
            self.context.translator.language,
        )

    def new_task(self) -> None:
        dialog = self._dialog(None)
        dialog.title.setText(self.quick.text())
        if dialog.exec():
            v = dialog.values()
            task_id = create(self.conn, v["title"], v["due"], v["priority"], v["list"], v["notes"])
            self._sync_reminder(task_id, v)
            self.quick.clear()
            self.refresh()

    def edit(self, task_id: int) -> None:
        task = get(self.conn, task_id)
        if task is None:
            return
        dialog = self._dialog(task)
        if dialog.exec():
            v = dialog.values()
            update(self.conn, task_id, v["title"], v["due"], v["priority"], v["list"], v["notes"])
            self._sync_reminder(task_id, v)
            self.refresh()

    def _sync_reminder(self, task_id: int, values: dict[str, Any]) -> None:
        existing = reminders.for_task(self.conn, task_id)
        if values["remind"] and values["due"]:
            when = values["due"] - values["lead"] * 60
            if existing:
                reminders.update(
                    self.conn, existing.id, values["title"], when, "once", 1, t("reminder_message")
                )
            else:
                reminders.create(
                    self.conn, values["title"], when, "once", 1, t("reminder_message"), task_id
                )
        elif existing:
            reminders.delete(self.conn, existing.id)

    def remove(self, task_id: int) -> None:
        task = get(self.conn, task_id)
        if task is None:
            return
        if self.option("confirm_delete") and not dialogs.confirm_destructive(
            self,
            t("delete.title", name=task.title),
            t("delete.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        existing = reminders.for_task(self.conn, task_id)
        if existing:
            reminders.delete(self.conn, existing.id)
        delete(self.conn, task_id)
        self.refresh()

    def clear_done(self) -> None:
        number = counts(self.conn)["done"]
        if not dialogs.confirm_destructive(
            self,
            t("clear_done.title", count=number),
            t("clear_done.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        delete_done(self.conn)
        self.refresh()

    def _set_done(self, task_id: int, done: bool) -> None:
        set_done(self.conn, task_id, done)
        self.refresh()

    def _menu(self, row: int, pos: QPoint) -> None:
        task_id = self._id(row)
        task = get(self.conn, task_id)
        if task is None:
            return
        menu = QMenu(self)
        menu.addAction(
            t("mark_open") if task.done else t("mark_done"),
            lambda: self._set_done(task_id, not task.done),
        )
        menu.addAction(tr("common.edit"), lambda: self.edit(task_id))
        menu.addSeparator()
        menu.addAction(tr("common.delete"), lambda: self.remove(task_id))
        menu.exec(pos)

    def screenshot_prepare(self) -> None:
        if not query(self.conn, "open") and not query(self.conn, "done"):
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            create(
                self.conn,
                "Angebot an Kunden senden",
                (now - timedelta(hours=3)).timestamp(),
                2,
                "Arbeit",
            )
            create(
                self.conn,
                "Steuerunterlagen sortieren",
                (now + timedelta(hours=4)).timestamp(),
                1,
                "Privat",
            )
            create(
                self.conn,
                "Team-Meeting vorbereiten",
                (now + timedelta(days=2)).timestamp(),
                1,
                "Arbeit",
            )
            create(
                self.conn,
                "Fahrrad zur Inspektion",
                (now + timedelta(days=6)).timestamp(),
                0,
                "Privat",
            )
            create(self.conn, "Bücher zurückgeben")
            done = create(self.conn, "Backup einrichten", None, 1, "Privat")
            set_done(self.conn, done, True)
        self.refresh()
