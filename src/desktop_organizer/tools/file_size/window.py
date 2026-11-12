"""Folder sizes window: drill-down folder table, largest files and file types."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QTabWidget

from desktop_organizer.app.components import (
    DATA_ROLE,
    BarDelegate,
    FolderPicker,
    Table,
    copy_text,
    item,
    open_file,
    show_in_explorer,
)
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.app.widgets import Meter
from desktop_organizer.core.formatting import format_bytes, format_datetime, format_number
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.tools.file_size import SETTINGS
from desktop_organizer.tools.file_size.logic import Analysis, Node, analyze, find_node

TOOL = "file_size"
FILES_ENTRY = "__files__"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class FileSizeWindow(ToolWindow):
    tool_id = TOOL
    icon = "chart-pie"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._analysis: Analysis | None = None
        self._current: Node | None = None

        self.folder = FolderPicker()
        self.folder.changed.connect(self._folder_changed)
        self.analyze_button = QPushButton()
        self.analyze_button.setProperty("role", "primary")
        self.analyze_button.clicked.connect(self.start)
        self.toolbar.addWidget(self.folder, 1)
        self.toolbar.addWidget(self.analyze_button)

        self.up_button = QPushButton()
        self.up_button.setIcon(context.theme.icon("chevron-up"))
        self.up_button.clicked.connect(self.go_up)
        self.location = QLabel()
        self.location.setProperty("textStyle", "section")
        self.totals = QLabel()
        self.totals.setProperty("textStyle", "secondary")
        self.disk = Meter(context.theme)
        nav = QHBoxLayout()
        nav.setSpacing(12)
        nav.addWidget(self.up_button)
        nav.addWidget(self.location, 1)
        nav.addWidget(self.totals)
        nav.addSpacing(16)
        nav.addWidget(self.disk)
        self.content.addLayout(nav)

        self.tabs = QTabWidget()
        self.folders_table = Table(5)
        self.folders_table.setItemDelegateForColumn(2, BarDelegate(context.theme, self))
        self.folders_table.setColumnWidth(1, 110)
        self.folders_table.setColumnWidth(2, 220)
        self.folders_table.setColumnWidth(3, 100)
        self.folders_table.setColumnWidth(4, 150)
        self.folders_table.doubleClicked.connect(self._open_row)
        self.folders_table.context_requested.connect(self._folder_menu)
        self.files_table = Table(4)
        self.files_table.setColumnWidth(1, 110)
        self.files_table.setColumnWidth(2, 150)
        self.files_table.setColumnWidth(3, 380)
        self.files_table.doubleClicked.connect(
            lambda i: open_file(self._file_path(self.files_table.source_row(i)))
        )
        self.files_table.context_requested.connect(self._file_menu)
        self.types_table = Table(4)
        self.types_table.setItemDelegateForColumn(3, BarDelegate(context.theme, self))
        self.types_table.setColumnWidth(1, 120)
        self.types_table.setColumnWidth(2, 120)
        self.types_table.setColumnWidth(3, 260)
        self.tabs.addTab(self.folders_table, "")
        self.tabs.addTab(self.files_table, "")
        self.tabs.addTab(self.types_table, "")
        self.content.addWidget(self.tabs, 1)

        self.hint = QLabel()
        self.hint.setProperty("textStyle", "caption")
        self.footer.addWidget(self.hint, 1)

        last = context.settings.tool_values(TOOL).get("last_folder")
        if isinstance(last, str) and Path(last).is_dir():
            self.folder.set_path(last)
        self.retranslate()

    def retranslate(self) -> None:
        self.folder.retranslate()
        self.analyze_button.setText(t("analyze"))
        self.up_button.setText(t("up"))
        self.tabs.setTabText(0, t("tab.folders"))
        self.tabs.setTabText(1, t("tab.files"))
        self.tabs.setTabText(2, t("tab.types"))
        self.folders_table.set_headers([t("col.name"), t("col.size"), t("col.share"), t("col.files"), t("col.modified")])
        self.files_table.set_headers([t("col.file"), t("col.size"), t("col.modified"), t("col.folder")])
        self.types_table.set_headers([t("col.type"), t("col.count"), t("col.size"), t("col.share")])
        self.hint.setText(t("hint"))
        self._show()

    def _folder_changed(self, path: str) -> None:
        self.context.settings.set_tool_value(TOOL, "last_folder", path)

    def start(self) -> None:
        folder = self.folder.path()
        if not folder:
            self.folder.browse()
            folder = self.folder.path()
            if not folder:
                return
        opts = self.options()

        def work(job: Job) -> Analysis:
            return analyze(Path(folder), opts["include_hidden"], opts["top_files"], job)

        self.run_task(work, self._done, t("analyzing"))

    def _done(self, analysis: Any) -> None:
        assert isinstance(analysis, Analysis)
        self._analysis = analysis
        self._current = analysis.root
        if analysis.errors:
            self.info.show_message("info", t("errors", count=analysis.errors))
        self._show()

    def _show(self) -> None:
        lang = self.context.translator.language
        analysis, node = self._analysis, self._current
        self.up_button.setEnabled(bool(analysis and node and node is not analysis.root))
        if analysis is None or node is None:
            self.location.setText(t("empty"))
            self.totals.clear()
            self.disk.hide()
            return
        self.location.setText(str(node.path))
        self.totals.setText(
            t("totals", size=format_bytes(node.size, lang), files=format_number(node.files, lang))
        )
        if analysis.disk_total:
            used = analysis.disk_total - analysis.disk_free
            self.disk.set_reading(
                t("disk"),
                t("disk.value", free=format_bytes(analysis.disk_free, lang)),
                used / analysis.disk_total,
            )
            self.disk.show()

        table = self.folders_table
        table.setSortingEnabled(False)
        table.clear_rows()
        total = node.size or 1
        rows = [(child.name, child) for child in node.sorted_children()]
        for name, child in rows:
            share = item("", sort=child.size)
            share.setData(child.size / total, DATA_ROLE)
            table.source.appendRow(
                [
                    item(name, data=str(child.path)),
                    item(format_bytes(child.size, lang), sort=child.size),
                    share,
                    item(format_number(child.files, lang), sort=child.files),
                    item(format_datetime(child.modified, lang) if child.modified else "", sort=child.modified),
                ]
            )
        if self.option("show_files_entry") and node.own_files_size:
            share = item("", sort=node.own_files_size)
            share.setData(node.own_files_size / total, DATA_ROLE)
            own_count = node.files - sum(c.files for c in node.children)
            table.source.appendRow(
                [
                    item(t("own_files"), data=FILES_ENTRY),
                    item(format_bytes(node.own_files_size, lang), sort=node.own_files_size),
                    share,
                    item(format_number(own_count, lang), sort=own_count),
                    item(""),
                ]
            )
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        files = self.files_table
        files.setSortingEnabled(False)
        files.clear_rows()
        for size, path, modified in analysis.largest:
            p = Path(path)
            files.source.appendRow(
                [
                    item(p.name, data=path),
                    item(format_bytes(size, lang), sort=size),
                    item(format_datetime(modified, lang), sort=modified),
                    item(str(p.parent)),
                ]
            )
        files.setSortingEnabled(True)

        types = self.types_table
        types.setSortingEnabled(False)
        types.clear_rows()
        all_size = sum(size for _count, size in analysis.types.values()) or 1
        for suffix, (count, size) in sorted(analysis.types.items(), key=lambda kv: -kv[1][1]):
            share = item("", sort=size)
            share.setData(size / all_size, DATA_ROLE)
            label = suffix if suffix != "-" else t("no_extension")
            types.source.appendRow(
                [
                    item(label),
                    item(format_number(count, lang), sort=count),
                    item(format_bytes(size, lang), sort=size),
                    share,
                ]
            )
        types.setSortingEnabled(True)

    def _row_path(self, row: int) -> str:
        return str(self.folders_table.source.item(row, 0).data(DATA_ROLE))

    def _file_path(self, row: int) -> str:
        return str(self.files_table.source.item(row, 0).data(DATA_ROLE))

    def _open_row(self, index: Any) -> None:
        path = self._row_path(self.folders_table.source_row(index))
        if path == FILES_ENTRY or self._analysis is None:
            return
        node = find_node(self._analysis.root, Path(path))
        if node is not None:
            self._current = node
            self._show()

    def go_up(self) -> None:
        if self._analysis is None or self._current is None:
            return
        parent = find_node(self._analysis.root, self._current.path.parent)
        if parent is not None:
            self._current = parent
            self._show()

    def _folder_menu(self, row: int, pos: QPoint) -> None:
        path = self._row_path(row)
        if path == FILES_ENTRY:
            return
        menu = QMenu(self)
        menu.addAction(t("open_folder"), lambda: self._open_row(self.folders_table.proxy.mapFromSource(self.folders_table.source.index(row, 0))))
        menu.addAction(tr("common.show_in_explorer"), lambda: show_in_explorer(path))
        menu.addAction(tr("common.copy_path"), lambda: copy_text(path))
        menu.exec(pos)

    def _file_menu(self, row: int, pos: QPoint) -> None:
        path = self._file_path(row)
        menu = QMenu(self)
        menu.addAction(tr("common.open"), lambda: open_file(path))
        menu.addAction(tr("common.show_in_explorer"), lambda: show_in_explorer(path))
        menu.addAction(tr("common.copy_path"), lambda: copy_text(path))
        menu.exec(pos)

    def set_busy(self, busy: bool) -> None:
        for widget in (self.folder, self.analyze_button, self.tabs):
            widget.setEnabled(not busy)

    def settings_changed(self) -> None:
        self._show()

    def theme_changed(self) -> None:
        self.up_button.setIcon(self.context.theme.icon("chevron-up"))

    def screenshot_prepare(self) -> None:
        self.start()
