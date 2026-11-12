"""File cleaner window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QComboBox, QLabel, QMenu, QPushButton

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import (
    DATA_ROLE,
    FolderPicker,
    Table,
    copy_text,
    item,
    open_file,
    show_in_explorer,
)
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_bytes, format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.tools.file_cleaner import SETTINGS
from desktop_organizer.tools.file_cleaner.logic import (
    CATEGORY_ORDER,
    Move,
    Options,
    Plan,
    execute,
    journal_info,
    make_plan,
    undo,
)

TOOL = "file_cleaner"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class FileCleanerWindow(ToolWindow):
    tool_id = TOOL
    icon = "folder-tree"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._plan: Plan | None = None
        self.journal = context.paths.data_dir / TOOL / "last_run.json"

        self.folder = FolderPicker()
        self.folder.changed.connect(self._folder_changed)
        self.preview_button = QPushButton()
        self.preview_button.setProperty("role", "primary")
        self.preview_button.clicked.connect(self.create_preview)
        self.toolbar.addWidget(self.folder, 1)
        self.toolbar.addWidget(self.preview_button)

        self.summary = QLabel()
        self.summary.setProperty("textStyle", "secondary")
        self.filter = QComboBox()
        self.filter.setMinimumWidth(200)
        self.filter.currentIndexChanged.connect(self._apply_filter)
        self.select_all = QPushButton()
        self.select_all.clicked.connect(lambda: self.table.set_all_checked(True))
        self.select_none = QPushButton()
        self.select_none.clicked.connect(lambda: self.table.set_all_checked(False))
        from PySide6.QtWidgets import QHBoxLayout

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.summary, 1)
        row.addWidget(self.select_all)
        row.addWidget(self.select_none)
        row.addWidget(self.filter)
        self.content.addLayout(row)

        self.table = Table(5)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 240)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 150)
        self.table.context_requested.connect(self._context_menu)
        self.table.doubleClicked.connect(
            lambda index: open_file(str(self._move(self.table.source_row(index)).source))
        )
        self.table.source.itemChanged.connect(lambda _i: self._update_footer())
        self.content.addWidget(self.table, 1)

        self.hint = QLabel()
        self.hint.setProperty("textStyle", "caption")
        self.hint.setWordWrap(True)
        self.undo_button = QPushButton()
        self.undo_button.clicked.connect(self.undo_last_run)
        self.move_button = QPushButton()
        self.move_button.setProperty("role", "primary")
        self.move_button.clicked.connect(self.move_files)
        self.footer.addWidget(self.hint, 1)
        self.footer.addWidget(self.undo_button)
        self.footer.addWidget(self.move_button)

        last = context.settings.tool_values(TOOL).get("last_folder")
        if isinstance(last, str) and Path(last).is_dir():
            self.folder.set_path(last)
        self.retranslate()

    # -- texts ---------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.folder.retranslate()
        self.preview_button.setText(t("preview"))
        self.select_all.setText(tr("common.select_all"))
        self.select_none.setText(tr("common.select_none"))
        self.table.set_headers([t("col.file"), t("col.category"), t("col.target"), t("col.size"), t("col.modified")])
        current = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem(t("filter.all"), "")
        for category in CATEGORY_ORDER:
            self.filter.addItem(t(f"category.{category}"), category)
        index = self.filter.findData(current) if current else 0
        self.filter.setCurrentIndex(max(index, 0))
        self.filter.blockSignals(False)
        self.undo_button.setText(t("undo"))
        if self._plan is not None:
            self._fill(self._plan)
        self._update_footer()

    # -- actions -------------------------------------------------------------------------

    def _folder_changed(self, path: str) -> None:
        self.context.settings.set_tool_value(TOOL, "last_folder", path)
        self._plan = None
        self.table.clear_rows()
        self._update_footer()

    def _options(self) -> Options:
        opts = self.options()
        language = opts["folder_language"]
        if language == "ui":
            language = self.context.translator.language
        return Options(
            folder_language=language,
            move_other=opts["move_other"],
            date_subfolders=opts["date_subfolders"],
            include_hidden=opts["include_hidden"],
            skip_recent_minutes=opts["skip_recent_minutes"],
            on_conflict=opts["on_conflict"],
        )

    def create_preview(self) -> None:
        folder = self.folder.path()
        if not folder:
            self.folder.browse()
            folder = self.folder.path()
            if not folder:
                return
        options = self._options()

        def work(job: Job) -> Plan:
            return make_plan(Path(folder), options, job)

        self.run_task(work, self._preview_ready, t("scanning"))

    def _preview_ready(self, plan: Any) -> None:
        assert isinstance(plan, Plan)
        self._plan = plan
        self._fill(plan)
        if not plan.moves:
            self.info.show_message("info", t("nothing_to_do", skipped=len(plan.skipped)))
        elif plan.skipped:
            self.info.show_message("info", t("skipped_note", count=len(plan.skipped)))
        self._update_footer()

    def _fill(self, plan: Plan) -> None:
        lang = self.context.translator.language
        self.table.setSortingEnabled(False)
        self.table.clear_rows()
        for index, move in enumerate(plan.moves):
            relative = str(move.target.relative_to(plan.folder).parent)
            self.table.source.appendRow(
                [
                    item(move.source.name, data=index, checkable=True),
                    item(t(f"category.{move.category}"), data=move.category),
                    item(relative + "\\"),
                    item(format_bytes(move.size, lang), sort=move.size),
                    item(format_datetime(move.modified, lang), sort=move.modified),
                ]
            )
        self.table.setSortingEnabled(True)
        self._apply_filter()

    def _apply_filter(self) -> None:
        category = self.filter.currentData() or ""
        self.table.proxy.setFilterKeyColumn(1)
        self.table.proxy.setFilterRole(DATA_ROLE)
        self.table.proxy.setFilterFixedString(category)

    def _move(self, row: int) -> Move:
        assert self._plan is not None
        index = self.table.source.item(row, 0).data(DATA_ROLE)
        return self._plan.moves[int(index)]

    def _selected_moves(self) -> list[Move]:
        return [self._move(row) for row in self.table.checked_rows()]

    def move_files(self) -> None:
        moves = self._selected_moves()
        if not moves:
            return
        if self.option("confirm_before_move") and not dialogs.confirm(
            self,
            t("confirm.title", count=len(moves)),
            t("confirm.body", count=len(moves), folder=self.folder.path()),
            t("confirm.ok"),
            tr("common.cancel"),
        ):
            return
        journal = self.journal

        def work(job: Job) -> object:
            return execute(moves, journal, job)

        self.run_task(work, self._moved, t("moving"))

    def _moved(self, result: Any) -> None:
        self._plan = None
        self.table.clear_rows()
        if result.failed:
            names = ", ".join(p.name for p, _ in result.failed[:5])
            self.info.show_message(
                "warning", t("moved_with_errors", moved=result.moved, failed=len(result.failed), names=names)
            )
        else:
            self.info.show_message(
                "success", t("moved", count=result.moved), t("undo"), self.undo_last_run
            )
        self._update_footer()

    def undo_last_run(self) -> None:
        info = journal_info(self.journal)
        if info is None:
            return
        if not dialogs.confirm(
            self, t("undo.title"), t("undo.body", count=info[0]), t("undo"), tr("common.cancel")
        ):
            return
        journal = self.journal

        def work(job: Job) -> object:
            return undo(journal, job)

        self.run_task(work, self._undone, t("undoing"))

    def _undone(self, result: Any) -> None:
        if result.failed:
            self.info.show_message(
                "warning", t("undone_with_errors", restored=result.restored, failed=len(result.failed))
            )
        else:
            self.info.show_message("success", t("undone", count=result.restored))
        self._plan = None
        self.table.clear_rows()
        self._update_footer()

    def _context_menu(self, row: int, pos: QPoint) -> None:
        move = self._move(row)
        menu = QMenu(self)
        menu.addAction(tr("common.open"), lambda: open_file(str(move.source)))
        menu.addAction(tr("common.show_in_explorer"), lambda: show_in_explorer(str(move.source)))
        menu.addAction(tr("common.copy_path"), lambda: copy_text(str(move.source)))
        menu.exec(pos)

    # -- state ---------------------------------------------------------------------------

    def _update_footer(self) -> None:
        lang = self.context.translator.language
        checked = self._selected_moves() if self._plan is not None else []
        total = sum(m.size for m in checked)
        if self._plan is None:
            self.summary.setText(t("summary.empty"))
        else:
            folders = len({m.target.parent for m in checked})
            self.summary.setText(
                t("summary", files=len(checked), folders=folders, size=format_bytes(total, lang))
            )
        self.move_button.setText(t("move", count=len(checked)))
        self.move_button.setEnabled(bool(checked) and not self.busy)
        info = journal_info(self.journal)
        self.undo_button.setEnabled(info is not None and not self.busy)
        if info is not None:
            self.hint.setText(t("last_run", count=info[0], time=format_datetime(info[1], lang)))
        else:
            self.hint.setText(t("hint"))
        self.preview_button.setProperty("role", "primary" if self._plan is None else "")
        self.preview_button.style().unpolish(self.preview_button)
        self.preview_button.style().polish(self.preview_button)

    def set_busy(self, busy: bool) -> None:
        for widget in (self.folder, self.preview_button, self.filter, self.table):
            widget.setEnabled(not busy)
        self._update_footer()

    def settings_changed(self) -> None:
        self._update_footer()

    def screenshot_prepare(self) -> None:
        """Used by build/screenshots_tools.py to show a filled window."""
        self.context.settings.set_tool_value(TOOL, "skip_recent_minutes", 0)
        self.create_preview()


