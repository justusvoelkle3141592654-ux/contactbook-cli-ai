"""Reminders window: list of reminders with an editor dialog and quick presets."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import QDateTime, QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import DATA_ROLE, EmptyState, Table, item
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.reminders import SETTINGS
from desktop_organizer.tools.reminders.logic import (
    RECURRENCES,
    Reminder,
    all_reminders,
    create,
    delete,
    get,
    set_enabled,
    update,
)

TOOL = "reminders"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


def describe(reminder: Reminder) -> str:
    if reminder.recurrence == "minutes":
        return t("every_minutes", minutes=reminder.interval)
    return t(f"recurrence.{reminder.recurrence}")


class ReminderDialog(QDialog):
    def __init__(
        self, parent: QWidget, reminder: Reminder | None, lead_minutes: int, language: str
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("edit") if reminder else t("new"))
        self.setMinimumWidth(520)
        self.title = QLineEdit(reminder.title if reminder else "")
        self.message = QLineEdit(reminder.message if reminder else "")
        self.due = QDateTimeEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("dd.MM.yyyy HH:mm" if language == "de" else "yyyy-MM-dd HH:mm")
        start = reminder.due if reminder else time.time() + lead_minutes * 60
        self.due.setDateTime(QDateTime.fromSecsSinceEpoch(int(start)))
        self.recurrence = QComboBox()
        for value in RECURRENCES:
            self.recurrence.addItem(t(f"recurrence.{value}"), value)
        self.recurrence.setCurrentIndex(RECURRENCES.index(reminder.recurrence) if reminder else 0)
        self.interval = QSpinBox()
        self.interval.setRange(1, 24 * 60)
        self.interval.setValue(reminder.interval if reminder else 60)
        self.interval.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.interval.setSuffix(f" {t('minutes')}")
        self.interval_label = QLabel(t("interval"))
        self.recurrence.currentIndexChanged.connect(self._update)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        form.addRow(t("field.title"), self.title)
        form.addRow(t("field.message"), self.message)
        form.addRow(t("field.due"), self.due)
        form.addRow(t("field.recurrence"), self.recurrence)
        form.addRow(self.interval_label, self.interval)
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
        self.error = QLabel()
        self.error.setProperty("textStyle", "error")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        self._update()

    def _update(self) -> None:
        minutes = self.recurrence.currentData() == "minutes"
        self.interval.setVisible(minutes)
        self.interval_label.setVisible(minutes)

    def _accept(self) -> None:
        if not self.title.text().strip():
            self.error.setText(t("error.title"))
            self.title.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, float, str, int, str]:
        return (
            self.title.text().strip(),
            float(self.due.dateTime().toSecsSinceEpoch()),
            self.recurrence.currentData(),
            self.interval.value(),
            self.message.text().strip(),
        )


class RemindersWindow(ToolWindow):
    tool_id = TOOL
    icon = "bell"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.conn = context.database.connection

        self.new_button = QPushButton()
        self.new_button.setProperty("role", "primary")
        self.new_button.setIcon(context.theme.icon("plus"))
        self.new_button.clicked.connect(self.new_reminder)
        self.preset_button = QPushButton()
        self.preset_menu = QMenu(self)
        self.preset_button.setMenu(self.preset_menu)
        self.test_button = QPushButton()
        self.test_button.clicked.connect(self.test_notification)
        self.toolbar.addWidget(self.new_button)
        self.toolbar.addWidget(self.preset_button)
        self.toolbar.addStretch(1)
        self.toolbar.addWidget(self.test_button)

        self.table = Table(4)
        self.table.setColumnWidth(1, 190)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.setColumnWidth(2, 190)
        self.table.setColumnWidth(3, 120)
        self.table.doubleClicked.connect(lambda i: self.edit(self._id(self.table.source_row(i))))
        self.table.context_requested.connect(self._menu)
        self.table.source.itemChanged.connect(self._toggled)
        self.empty = EmptyState(context.theme, "bell")
        self.content.addWidget(self.table, 1)
        self.content.addWidget(self.empty, 1)

        self.hint = QLabel()
        self.hint.setProperty("textStyle", "caption")
        self.hint.setWordWrap(True)
        self.footer.addWidget(self.hint, 1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(20_000)  # the main process advances recurring reminders
        self.retranslate()

    def retranslate(self) -> None:
        self.new_button.setText(t("new"))
        self.preset_button.setText(t("presets"))
        self.test_button.setText(t("test"))
        self.preset_menu.clear()
        self.preset_menu.addAction(
            t("preset.break", minutes=self.option("break_interval_minutes")), self._preset_break
        )
        self.preset_menu.addAction(t("preset.water"), self._preset_water)
        self.preset_menu.addAction(t("preset.stand"), self._preset_stand)
        self.table.set_headers(
            [t("col.title"), t("col.next"), t("col.recurrence"), t("col.active")]
        )
        self.empty.set_texts(t("empty.title"), t("empty.text"))
        self.hint.setText(t("hint"))
        self._background_notice()
        self.refresh()

    def _background_notice(self) -> None:
        if not self.context.settings.get("run_in_background"):
            self.info.show_message(
                "warning",
                t("background.off"),
                t("background.enable"),
                self._enable_background,
            )

    def _enable_background(self) -> None:
        self.context.settings.set("run_in_background", True)
        self.info.show_message("success", t("background.on"))

    def settings_changed(self) -> None:
        self.retranslate()

    def refresh(self) -> None:
        lang = self.context.translator.language
        reminders = all_reminders(self.conn)
        self._filling = True
        self.table.setSortingEnabled(False)
        self.table.clear_rows()
        for reminder in reminders:
            title = item(reminder.title, data=reminder.id)
            if reminder.message:
                title.setToolTip(reminder.message)
            active = item(
                t("active") if reminder.enabled else t("inactive"), sort=int(reminder.enabled)
            )
            active.setCheckable(True)
            active.setCheckState(
                Qt.CheckState.Checked if reminder.enabled else Qt.CheckState.Unchecked
            )
            next_text = format_datetime(reminder.due, lang) if reminder.enabled else "–"
            self.table.source.appendRow(
                [title, item(next_text, sort=reminder.due), item(describe(reminder)), active]
            )
        self.table.setSortingEnabled(True)
        self._filling = False
        self.table.setVisible(bool(reminders))
        self.empty.setVisible(not reminders)

    def _id(self, row: int) -> int:
        return int(self.table.source.item(row, 0).data(DATA_ROLE))

    def _toggled(self, cell: Any) -> None:
        if getattr(self, "_filling", False) or cell.column() != 3:
            return
        reminder_id = self._id(cell.row())
        enabled = cell.checkState() == Qt.CheckState.Checked
        reminder = get(self.conn, reminder_id)
        if reminder and enabled and reminder.due < time.time() and reminder.recurrence == "once":
            self.info.show_message("info", t("past_due"))
            self.edit(reminder_id)
            return
        set_enabled(self.conn, reminder_id, enabled)
        QTimer.singleShot(0, self.refresh)

    def new_reminder(self) -> None:
        dialog = ReminderDialog(
            self, None, self.option("default_lead_minutes"), self.context.translator.language
        )
        if dialog.exec():
            title, due, recurrence, interval, message = dialog.values()
            create(self.conn, title, due, recurrence, interval, message)
            self.refresh()

    def edit(self, reminder_id: int) -> None:
        reminder = get(self.conn, reminder_id)
        if reminder is None:
            return
        dialog = ReminderDialog(
            self, reminder, self.option("default_lead_minutes"), self.context.translator.language
        )
        if dialog.exec():
            title, due, recurrence, interval, message = dialog.values()
            update(self.conn, reminder_id, title, due, recurrence, interval, message)
            self.refresh()

    def remove(self, reminder_id: int) -> None:
        reminder = get(self.conn, reminder_id)
        if reminder is None:
            return
        if self.option("confirm_delete") and not dialogs.confirm_destructive(
            self,
            t("delete.title", name=reminder.title),
            t("delete.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        delete(self.conn, reminder_id)
        self.refresh()

    def _menu(self, row: int, pos: QPoint) -> None:
        reminder_id = self._id(row)
        menu = QMenu(self)
        menu.addAction(tr("common.edit"), lambda: self.edit(reminder_id))
        menu.addAction(tr("common.delete"), lambda: self.remove(reminder_id))
        menu.exec(pos)

    def _preset(self, title: str, message: str, minutes: int) -> None:
        create(self.conn, title, time.time() + minutes * 60, "minutes", minutes, message)
        self.refresh()
        self.info.show_message("success", t("preset.added", title=title))

    def _preset_break(self) -> None:
        minutes = self.option("break_interval_minutes")
        self._preset(t("preset.break.title"), t("preset.break.message"), minutes)

    def _preset_water(self) -> None:
        self._preset(t("preset.water.title"), t("preset.water.message"), 60)

    def _preset_stand(self) -> None:
        self._preset(t("preset.stand.title"), t("preset.stand.message"), 30)

    def test_notification(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.info.show_message("warning", t("test.unavailable"))
            return
        tray = QSystemTrayIcon(self.windowIcon() or self.context.theme.icon("bell"), self)
        tray.show()
        tray.showMessage(
            t("test.title"), t("test.message"), QSystemTrayIcon.MessageIcon.Information, 8000
        )
        QTimer.singleShot(10_000, tray.deleteLater)

    def screenshot_prepare(self) -> None:
        if not all_reminders(self.conn):
            now = datetime.now().replace(second=0, microsecond=0)
            create(
                self.conn,
                t("preset.break.title"),
                (now + timedelta(minutes=35)).timestamp(),
                "minutes",
                50,
                t("preset.break.message"),
            )
            create(
                self.conn, "Zahnarzttermin", (now + timedelta(days=2, hours=3)).timestamp(), "once"
            )
            create(
                self.conn, "Wochenbericht senden", (now + timedelta(days=4)).timestamp(), "weekly"
            )
            create(self.conn, "Pflanzen gießen", (now + timedelta(days=1)).timestamp(), "weekdays")
        self.refresh()
