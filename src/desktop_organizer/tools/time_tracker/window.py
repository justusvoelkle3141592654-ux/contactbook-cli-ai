"""Time tracker window: timer card, today's entries, week overview, projects."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDateTime, QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import DATA_ROLE, Table, item, save_file_dialog
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_datetime, format_duration
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.time_tracker import SETTINGS
from desktop_organizer.tools.time_tracker.logic import (
    Entry,
    add_entry,
    delete_entry,
    delete_project,
    ensure_project,
    entries_between,
    export_csv,
    get_entry,
    projects,
    rename_project,
    round_seconds,
    running,
    set_archived,
    split_by_day,
    start,
    stop,
    totals,
    update_entry,
    week_days,
)

TOOL = "time_tracker"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


def hours(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    return f"{minutes // 60}:{minutes % 60:02d}"


class EntryDialog(QDialog):
    def __init__(
        self, parent: QWidget, names: list[str], entry: Entry | None, language: str
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("entry.edit") if entry else t("entry.add"))
        self.setMinimumWidth(480)
        fmt = "dd.MM.yyyy HH:mm" if language == "de" else "yyyy-MM-dd HH:mm"
        self.project = QComboBox()
        self.project.setEditable(True)
        self.project.addItems(names)
        if entry:
            self.project.setCurrentText(entry.project)
        self.begin = QDateTimeEdit()
        self.end = QDateTimeEdit()
        for edit in (self.begin, self.end):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat(fmt)
        now = time.time()
        self.begin.setDateTime(
            QDateTime.fromSecsSinceEpoch(int(entry.start if entry else now - 3600))
        )
        self.end.setDateTime(
            QDateTime.fromSecsSinceEpoch(int(entry.end if entry and entry.end else now))
        )
        self.note = QLineEdit(entry.note if entry else "")
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        form.addRow(t("field.project"), self.project)
        form.addRow(t("field.start"), self.begin)
        form.addRow(t("field.end"), self.end)
        form.addRow(t("field.note"), self.note)
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

    def _accept(self) -> None:
        if not self.project.currentText().strip():
            self.error.setText(t("error.project"))
        elif self.end.dateTime() <= self.begin.dateTime():
            self.error.setText(t("error.order"))
        else:
            self.accept()

    def values(self) -> tuple[str, float, float, str]:
        return (
            self.project.currentText().strip(),
            float(self.begin.dateTime().toSecsSinceEpoch()),
            float(self.end.dateTime().toSecsSinceEpoch()),
            self.note.text().strip(),
        )


class TimeTrackerWindow(ToolWindow):
    tool_id = TOOL
    icon = "timer"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.conn = context.database.connection
        self._week_offset = 0

        # Timer card ---------------------------------------------------------------------------
        self.project = QComboBox()
        self.project.setEditable(True)
        self.project.setMinimumWidth(240)
        self.note = QLineEdit()
        self.elapsed = QLabel("0:00:00")
        self.elapsed.setProperty("textStyle", "display")
        self.elapsed.setMinimumWidth(160)
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.toggle_button = QPushButton()
        self.toggle_button.setProperty("role", "primary")
        self.toggle_button.setMinimumWidth(140)
        self.toggle_button.clicked.connect(self.toggle)
        self.running_label = QLabel()
        self.running_label.setProperty("textStyle", "caption")
        card = QFrame()
        card.setObjectName("Panel")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        inputs = QVBoxLayout()
        inputs.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.project)
        row.addWidget(self.note, 1)
        inputs.addLayout(row)
        inputs.addWidget(self.running_label)
        card_layout.addLayout(inputs, 1)
        card_layout.addWidget(self.elapsed)
        card_layout.addWidget(self.toggle_button)
        self.content.addWidget(card)

        # Tabs ----------------------------------------------------------------------------------
        self.tabs = QTabWidget()
        today_page = QWidget()
        today_layout = QVBoxLayout(today_page)
        today_layout.setContentsMargins(0, 12, 0, 0)
        today_head = QHBoxLayout()
        self.today_total = QLabel()
        self.today_total.setProperty("textStyle", "section")
        self.add_button = QPushButton()
        self.add_button.clicked.connect(self.add_manual)
        today_head.addWidget(self.today_total, 1)
        today_head.addWidget(self.add_button)
        today_layout.addLayout(today_head)
        self.today_table = Table(5)
        self.today_table.setColumnWidth(1, 120)
        self.today_table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.today_table.setColumnWidth(2, 120)
        self.today_table.setColumnWidth(3, 110)
        self.today_table.setColumnWidth(4, 320)
        self.today_table.doubleClicked.connect(
            lambda i: self.edit_entry(self._entry_id(self.today_table, i))
        )
        self.today_table.context_requested.connect(self._entry_menu)
        today_layout.addWidget(self.today_table, 1)

        week_page = QWidget()
        week_layout = QVBoxLayout(week_page)
        week_layout.setContentsMargins(0, 12, 0, 0)
        week_head = QHBoxLayout()
        self.prev_week = QPushButton()
        self.prev_week.clicked.connect(lambda: self._shift_week(-1))
        self.next_week = QPushButton()
        self.next_week.clicked.connect(lambda: self._shift_week(1))
        self.week_label = QLabel()
        self.week_label.setProperty("textStyle", "section")
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self.export_week)
        week_head.addWidget(self.prev_week)
        week_head.addWidget(self.week_label, 1, Qt.AlignmentFlag.AlignCenter)
        week_head.addWidget(self.next_week)
        week_head.addSpacing(16)
        week_head.addWidget(self.export_button)
        week_layout.addLayout(week_head)
        self.week_table = Table(9)
        for column in range(1, 9):
            self.week_table.setColumnWidth(column, 84)
        week_layout.addWidget(self.week_table, 1)

        projects_page = QWidget()
        projects_layout = QVBoxLayout(projects_page)
        projects_layout.setContentsMargins(0, 12, 0, 0)
        projects_head = QHBoxLayout()
        self.new_project = QPushButton()
        self.new_project.clicked.connect(self.add_project)
        projects_head.addStretch(1)
        projects_head.addWidget(self.new_project)
        projects_layout.addLayout(projects_head)
        self.projects_table = Table(3)
        self.projects_table.setColumnWidth(1, 140)
        self.projects_table.setColumnWidth(2, 140)
        self.projects_table.context_requested.connect(self._project_menu)
        projects_layout.addWidget(self.projects_table, 1)

        self.tabs.addTab(today_page, "")
        self.tabs.addTab(week_page, "")
        self.tabs.addTab(projects_page, "")
        self.content.addWidget(self.tabs, 1)

        self.goal = QLabel()
        self.goal.setProperty("textStyle", "caption")
        self.footer.addWidget(self.goal, 1)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_elapsed)
        self._tick.start(1000)
        self.retranslate()

    # -- texts -------------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.note.setPlaceholderText(t("note"))
        line = self.project.lineEdit()
        if line is not None:
            line.setPlaceholderText(t("project"))
        self.add_button.setText(t("entry.add"))
        self.prev_week.setText(t("week.prev"))
        self.next_week.setText(t("week.next"))
        self.export_button.setText(tr("common.export_csv"))
        self.new_project.setText(t("project.new"))
        self.tabs.setTabText(0, t("tab.today"))
        self.tabs.setTabText(1, t("tab.week"))
        self.tabs.setTabText(2, t("tab.projects"))
        self.today_table.set_headers(
            [t("col.project"), t("col.start"), t("col.end"), t("col.duration"), t("col.note")]
        )
        self.projects_table.set_headers([t("col.project"), t("col.week"), t("col.status")])
        self.refresh()

    def settings_changed(self) -> None:
        self.refresh()

    # -- timer -------------------------------------------------------------------------------

    def _fill_projects(self) -> None:
        current = self.project.currentText()
        self.project.blockSignals(True)
        self.project.clear()
        self.project.addItems([p.name for p in projects(self.conn)])
        self.project.setCurrentText(current)
        self.project.blockSignals(False)

    def toggle(self) -> None:
        if running(self.conn):
            stop(self.conn)
        else:
            name = self.project.currentText().strip()
            if not name:
                self.info.show_message("warning", t("error.project"))
                self.project.setFocus()
                return
            start(self.conn, ensure_project(self.conn, name), self.note.text().strip())
        self.refresh()

    def _update_elapsed(self) -> None:
        current = running(self.conn)
        if current is None:
            self.elapsed.setText("0:00:00")
            return
        self.elapsed.setText(format_duration(current.duration()))

    # -- refresh -----------------------------------------------------------------------------

    def refresh(self) -> None:
        lang = self.context.translator.language
        self._fill_projects()
        current = running(self.conn)
        self.toggle_button.setText(t("stop") if current else t("start"))
        self.toggle_button.setProperty("role", "destructive" if current else "primary")
        self.toggle_button.style().unpolish(self.toggle_button)
        self.toggle_button.style().polish(self.toggle_button)
        if current:
            self.project.setCurrentText(current.project)
            self.note.setText(current.note)
            self.running_label.setText(
                t("running", project=current.project, time=format_datetime(current.start, lang))
            )
        else:
            self.running_label.setText(t("idle"))
        self.project.setEnabled(current is None)
        self.note.setEnabled(current is None)
        self._update_elapsed()

        today = date.today()
        now = time.time()
        rounding = self.option("round_minutes")
        table = self.today_table
        table.setSortingEnabled(False)
        table.clear_rows()
        total = 0.0
        for entry in entries_between(self.conn, today, today):
            seconds = split_by_day(entry, now).get(today, 0.0)
            total += seconds
            end_text = (
                datetime.fromtimestamp(entry.end).strftime("%H:%M") if entry.end else t("now")
            )
            table.source.appendRow(
                [
                    item(entry.project, data=entry.id),
                    item(datetime.fromtimestamp(entry.start).strftime("%H:%M"), sort=entry.start),
                    item(end_text, sort=entry.end or now),
                    item(hours(round_seconds(seconds, rounding)), sort=seconds),
                    item(entry.note),
                ]
            )
        table.setSortingEnabled(True)
        self.today_total.setText(t("today_total", time=hours(round_seconds(total, rounding))))
        goal = self.option("daily_goal_hours")
        self.goal.setText(t("goal", done=hours(total), goal=goal) if goal else t("hint"))
        self._fill_week()
        self._fill_project_table()

    def _days(self) -> list[date]:
        return week_days(
            date.today() + timedelta(days=7 * self._week_offset), self.option("week_start")
        )

    def _shift_week(self, delta: int) -> None:
        self._week_offset = min(0, self._week_offset + delta)
        self._fill_week()

    def _fill_week(self) -> None:
        lang = self.context.translator.language
        days = self._days()
        rounding = self.option("round_minutes")
        fmt = "%a %d.%m." if lang == "de" else "%a %m/%d"
        names_de = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        labels = [
            (f"{names_de[d.weekday()]} {d:%d.%m.}" if lang == "de" else d.strftime(fmt))
            for d in days
        ]
        self.week_table.set_headers([t("col.project"), *labels, t("col.total")])
        self.week_label.setText(
            t(
                "week.range",
                first=format_datetime(
                    datetime.combine(days[0], datetime.min.time()).timestamp(), lang, False
                ),
                last=format_datetime(
                    datetime.combine(days[-1], datetime.min.time()).timestamp(), lang, False
                ),
            )
        )
        self.next_week.setEnabled(self._week_offset < 0)
        data = totals(self.conn, days)
        table = self.week_table
        table.setSortingEnabled(False)
        table.clear_rows()
        day_sums = [0.0] * 7
        for project in sorted(data, key=str.casefold):
            row = [item(project)]
            project_total = 0.0
            for index, day in enumerate(days):
                seconds = data[project].get(day, 0.0)
                project_total += seconds
                day_sums[index] += seconds
                row.append(
                    item(hours(round_seconds(seconds, rounding)) if seconds else "", sort=seconds)
                )
            row.append(item(hours(round_seconds(project_total, rounding)), sort=project_total))
            table.source.appendRow(row)
        if data:
            total_row = [item(t("col.total"), sort="~")]
            total_row += [
                item(hours(round_seconds(s, rounding)) if s else "", sort=s) for s in day_sums
            ]
            total_row.append(
                item(hours(round_seconds(sum(day_sums), rounding)), sort=sum(day_sums))
            )
            for cell in total_row:
                font = cell.font()
                font.setBold(True)
                cell.setFont(font)
            table.source.appendRow(total_row)
        table.setSortingEnabled(False)

    def _fill_project_table(self) -> None:
        data = totals(self.conn, week_days(date.today(), self.option("week_start")))
        table = self.projects_table
        table.setSortingEnabled(False)
        table.clear_rows()
        for project in projects(self.conn, include_archived=True):
            seconds = sum(data.get(project.name, {}).values())
            table.source.appendRow(
                [
                    item(project.name, data=project.id),
                    item(hours(seconds), sort=seconds),
                    item(
                        t("archived") if project.archived else t("active"),
                        sort=int(project.archived),
                    ),
                ]
            )
        table.setSortingEnabled(True)

    # -- entries and projects ------------------------------------------------------------------

    def _entry_id(self, table: Table, index: Any) -> int:
        return int(table.source.item(table.source_row(index), 0).data(DATA_ROLE))

    def _names(self) -> list[str]:
        return [p.name for p in projects(self.conn)]

    def add_manual(self) -> None:
        dialog = EntryDialog(self, self._names(), None, self.context.translator.language)
        if dialog.exec():
            name, begin, end, note = dialog.values()
            add_entry(self.conn, ensure_project(self.conn, name), begin, end, note)
            self.refresh()

    def edit_entry(self, entry_id: int) -> None:
        entry = get_entry(self.conn, entry_id)
        if entry is None:
            return
        if entry.end is None:
            self.info.show_message("info", t("stop_first"))
            return
        dialog = EntryDialog(self, self._names(), entry, self.context.translator.language)
        if dialog.exec():
            name, begin, end, note = dialog.values()
            update_entry(self.conn, entry_id, ensure_project(self.conn, name), begin, end, note)
            self.refresh()

    def _entry_menu(self, row: int, pos: QPoint) -> None:
        entry_id = int(self.today_table.source.item(row, 0).data(DATA_ROLE))
        menu = QMenu(self)
        menu.addAction(tr("common.edit"), lambda: self.edit_entry(entry_id))
        menu.addAction(tr("common.delete"), lambda: self._delete_entry(entry_id))
        menu.exec(pos)

    def _delete_entry(self, entry_id: int) -> None:
        if self.option("confirm_delete") and not dialogs.confirm_destructive(
            self,
            t("entry.delete.title"),
            t("entry.delete.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        delete_entry(self.conn, entry_id)
        self.refresh()

    def add_project(self) -> None:
        name, ok = QInputDialog.getText(self, t("project.new"), t("field.project"))
        if ok and name.strip():
            ensure_project(self.conn, name)
            self.refresh()

    def _project_menu(self, row: int, pos: QPoint) -> None:
        project_id = int(self.projects_table.source.item(row, 0).data(DATA_ROLE))
        project = next((p for p in projects(self.conn, True) if p.id == project_id), None)
        if project is None:
            return
        menu = QMenu(self)
        menu.addAction(t("project.rename"), lambda: self._rename(project_id, project.name))
        menu.addAction(
            t("project.restore") if project.archived else t("project.archive"),
            lambda: self._set_archived(project_id, not project.archived),
        )
        menu.addAction(tr("common.delete"), lambda: self._delete_project(project_id, project.name))
        menu.exec(pos)

    def _set_archived(self, project_id: int, archived: bool) -> None:
        set_archived(self.conn, project_id, archived)
        self.refresh()

    def _rename(self, project_id: int, name: str) -> None:
        new, ok = QInputDialog.getText(
            self, t("project.rename"), t("field.project"), QLineEdit.EchoMode.Normal, name
        )
        if ok and new.strip():
            rename_project(self.conn, project_id, new)
            self.refresh()

    def _delete_project(self, project_id: int, name: str) -> None:
        if not dialogs.confirm_destructive(
            self,
            t("project.delete.title", name=name),
            t("project.delete.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        delete_project(self.conn, project_id)
        self.refresh()

    def export_week(self) -> None:
        days = self._days()
        target = save_file_dialog(
            self,
            tr("common.export_csv"),
            str(Path.home() / f"{t('export_name')}-{days[0].isoformat()}.csv"),
            tr("common.csv_filter"),
        )
        if target is None:
            return
        export_csv(entries_between(self.conn, days[0], days[-1]), target)
        self.info.show_message("success", tr("common.saved_to", path=str(target)))

    def screenshot_prepare(self) -> None:
        if not projects(self.conn):
            today = datetime.now().replace(hour=8, minute=30, second=0, microsecond=0)
            web = ensure_project(self.conn, "Website-Relaunch")
            mail = ensure_project(self.conn, "Kundensupport")
            intern = ensure_project(self.conn, "Interne Planung")
            for back in range(0, 5):
                day = today - timedelta(days=back)
                add_entry(
                    self.conn,
                    web,
                    day.timestamp(),
                    (day + timedelta(hours=2, minutes=15)).timestamp(),
                    "Startseite",
                )
                add_entry(
                    self.conn,
                    mail,
                    (day + timedelta(hours=3)).timestamp(),
                    (day + timedelta(hours=4, minutes=10)).timestamp(),
                    "Tickets",
                )
            start(self.conn, intern, "Wochenplanung", time.time() - 47 * 60)
        self.refresh()
