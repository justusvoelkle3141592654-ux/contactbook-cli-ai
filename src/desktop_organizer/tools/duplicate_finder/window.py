"""Duplicate finder window: scan area on the left, grouped results on the right."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import (
    EmptyState,
    FolderList,
    copy_text,
    open_file,
    save_file_dialog,
    show_in_explorer,
)
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_bytes, format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.core.tool_settings import set_value
from desktop_organizer.tools.duplicate_finder import SETTINGS
from desktop_organizer.tools.duplicate_finder.logic import (
    RULES,
    FileEntry,
    Group,
    Options,
    ScanResult,
    export_csv,
    files_to_remove,
    groups_fully_selected,
    move_to,
    parse_extensions,
    recycle,
    scan,
)

TOOL = "duplicate_finder"
ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
GROUP_ROLE = Qt.ItemDataRole.UserRole + 2
SORTS = ("wasted", "size", "count", "path")


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


def _field(key: str) -> Any:
    return next(f for f in SETTINGS if f.key == key)


class DuplicateFinderWindow(ToolWindow):
    tool_id = TOOL
    icon = "copy"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._result: ScanResult | None = None
        self._updating = False

        # Left: scan area ------------------------------------------------------------------
        self.folders_label = QLabel()
        self.folders_label.setProperty("textStyle", "section")
        self.folders = FolderList()
        self.folders.changed.connect(self._folders_changed)
        self.method_label = QLabel()
        self.method = QComboBox()
        self.method.currentIndexChanged.connect(self._quick_option_changed)
        self.min_size_label = QLabel()
        self.min_size = QSpinBox()
        self.min_size.setRange(0, 10_000_000)
        self.min_size.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.min_size.valueChanged.connect(self._quick_option_changed)
        self.types_label = QLabel()
        self.types = QLineEdit()
        self.types.editingFinished.connect(self._quick_option_changed)
        self.more_options = QPushButton()
        self.more_options.clicked.connect(self.open_settings)
        self.scan_button = QPushButton()
        self.scan_button.setProperty("role", "primary")
        self.scan_button.clicked.connect(self.start_scan)
        self.stats = QLabel()
        self.stats.setProperty("textStyle", "caption")
        self.stats.setWordWrap(True)

        left = QFrame()
        left.setObjectName("Panel")
        left.setMinimumWidth(320)
        side = QVBoxLayout(left)
        side.setContentsMargins(16, 16, 16, 16)
        side.setSpacing(8)
        side.addWidget(self.folders_label)
        side.addWidget(self.folders)
        side.addSpacing(8)
        for label, editor in (
            (self.method_label, self.method),
            (self.min_size_label, self.min_size),
            (self.types_label, self.types),
        ):
            side.addWidget(label)
            side.addWidget(editor)
        side.addWidget(self.more_options)
        side.addStretch(1)
        side.addWidget(self.stats)
        side.addWidget(self.scan_button)

        # Right: results ------------------------------------------------------------------
        self.filter = QLineEdit()
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        self.sort = QComboBox()
        self.sort.currentIndexChanged.connect(self._fill_tree)
        self.auto_button = QPushButton()
        self.auto_menu = QMenu(self)
        self.auto_button.setMenu(self.auto_menu)
        self.filter.setMinimumWidth(220)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        tools_row.addWidget(self.filter, 1)
        tools_row.addWidget(self.sort)
        tools_row.addWidget(self.auto_button)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0, 380)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 150)
        self.empty = EmptyState(context.theme, "copy")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addLayout(tools_row)
        right_layout.addWidget(self.tree, 1)
        right_layout.addWidget(self.empty, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        # Footer ----------------------------------------------------------------------------
        self.selection_label = QLabel()
        self.selection_label.setProperty("textStyle", "secondary")
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self.export_report)
        self.move_button = QPushButton()
        self.move_button.clicked.connect(self.move_selected)
        self.recycle_button = QPushButton()
        self.recycle_button.setProperty("role", "primary")
        self.recycle_button.clicked.connect(self.recycle_selected)
        self.footer.addWidget(self.selection_label, 1)
        self.footer.addWidget(self.export_button)
        self.footer.addWidget(self.move_button)
        self.footer.addWidget(self.recycle_button)

        saved = context.settings.tool_values(TOOL).get("folders")
        if isinstance(saved, list):
            self.folders.set_folders([f for f in saved if isinstance(f, str) and Path(f).is_dir()])
        self._load_quick_options()
        self.retranslate()

    # -- texts ---------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.folders_label.setText(t("folders"))
        self.folders.retranslate()
        self.method_label.setText(tr("tool.duplicate_finder.setting.method"))
        self.min_size_label.setText(tr("tool.duplicate_finder.setting.min_size_kb"))
        self.types_label.setText(tr("tool.duplicate_finder.setting.include_extensions"))
        self.types.setPlaceholderText(t("types.placeholder"))
        self.more_options.setText(t("more_options"))
        self.scan_button.setText(t("scan"))
        self.filter.setPlaceholderText(t("filter"))
        self.auto_button.setText(t("auto_select"))
        self.export_button.setText(tr("common.export_csv"))
        self.move_button.setText(t("move"))
        self.tree.setHeaderLabels([t("col.file"), t("col.size"), t("col.modified"), t("col.folder")])
        self.empty.set_texts(t("empty.title"), t("empty.text"))
        self._load_quick_options()
        current = self.sort.currentData()
        self.sort.blockSignals(True)
        self.sort.clear()
        for key in SORTS:
            self.sort.addItem(t(f"sort.{key}"), key)
        self.sort.setCurrentIndex(max(self.sort.findData(current), 0) if current else 0)
        self.sort.blockSignals(False)
        self.auto_menu.clear()
        for rule in RULES:
            self.auto_menu.addAction(
                tr(f"tool.duplicate_finder.setting.default_rule.{rule}"),
                lambda r=rule: self.apply_rule(r),
            )
        self.auto_menu.addSeparator()
        self.auto_menu.addAction(t("select_all_but_first"), lambda: self.apply_rule("first_listed"))
        self.auto_menu.addAction(tr("common.select_none"), lambda: self._set_all_checked(False))
        self.auto_menu.addSeparator()
        self.auto_menu.addAction(t("expand_all"), self._toggle_expand)
        self._fill_tree()

    def _load_quick_options(self) -> None:
        opts = self.options()
        self._updating = True
        self.method.clear()
        for choice in _field("method").choices:
            self.method.addItem(tr(f"tool.duplicate_finder.setting.method.{choice}"), choice)
        self.method.setCurrentIndex(self.method.findData(opts["method"]))
        self.min_size.setValue(opts["min_size_kb"])
        self.min_size.setSuffix(" KB")
        self.types.setText(opts["include_extensions"])
        self._updating = False

    def _quick_option_changed(self) -> None:
        if self._updating:
            return
        settings = self.context.settings
        set_value(settings, TOOL, _field("method"), self.method.currentData())
        set_value(settings, TOOL, _field("min_size_kb"), self.min_size.value())
        set_value(settings, TOOL, _field("include_extensions"), self.types.text())

    def settings_changed(self) -> None:
        self._load_quick_options()

    def _folders_changed(self) -> None:
        self.context.settings.set_tool_value(TOOL, "folders", self.folders.folders())

    # -- scanning ------------------------------------------------------------------------

    def _scan_options(self) -> Options:
        opts = self.options()
        return Options(
            method=opts["method"],
            min_size=max(1, opts["min_size_kb"] * 1024),
            max_size=opts["max_size_mb"] * 1024 * 1024,
            include_extensions=parse_extensions(opts["include_extensions"]),
            exclude_extensions=parse_extensions(opts["exclude_extensions"]),
            exclude_folders=frozenset(
                p.strip().lower() for p in opts["exclude_folders"].split(",") if p.strip()
            ),
            skip_hidden=opts["skip_hidden"],
        )

    def start_scan(self) -> None:
        folders = [Path(f) for f in self.folders.folders()]
        if not folders:
            self.folders.add()
            folders = [Path(f) for f in self.folders.folders()]
            if not folders:
                return
        options = self._scan_options()
        labels = {"partial": t("stage.partial"), "full": t("stage.full"), "compare": t("stage.compare")}

        def work(job: Job) -> ScanResult:
            return scan(folders, options, job, labels)

        self.run_task(work, self._scan_done, t("stage.collect"))

    def _scan_done(self, result: Any) -> None:
        assert isinstance(result, ScanResult)
        self._result = result
        if self.option("auto_select"):
            self.apply_rule(self.option("default_rule"), refill=False)
        self._fill_tree()
        lang = self.context.translator.language
        self.stats.setText(
            t(
                "stats",
                files=f"{result.scanned_files:,}".replace(",", "." if lang == "de" else ","),
                groups=len(result.groups),
                wasted=format_bytes(result.wasted, lang),
                skipped=result.skipped,
            )
        )
        if not result.groups:
            self.info.show_message("success", t("none_found"))

    # -- tree ----------------------------------------------------------------------------

    def _selected(self) -> set[Path]:
        if not hasattr(self, "_checked"):
            self._checked: set[Path] = set()
        return self._checked

    def _sorted_groups(self) -> list[Group]:
        if self._result is None:
            return []
        key = self.sort.currentData() or "wasted"
        groups = list(self._result.groups)
        if key == "size":
            groups.sort(key=lambda g: -g.size)
        elif key == "count":
            groups.sort(key=lambda g: -len(g.files))
        elif key == "path":
            groups.sort(key=lambda g: str(g.files[0].path).casefold())
        return groups

    def _fill_tree(self) -> None:
        lang = self.context.translator.language
        has = bool(self._result and self._result.groups)
        self.tree.setVisible(has)
        self.empty.setVisible(not has)
        self._updating = True
        self.tree.clear()
        selected = self._selected()
        for number, group in enumerate(self._sorted_groups(), start=1):
            head = QTreeWidgetItem(
                [
                    t(
                        "group",
                        number=number,
                        count=len(group.files),
                        name=group.files[0].path.name,
                    ),
                    format_bytes(group.size, lang),
                    t("group.wasted", size=format_bytes(group.wasted, lang)),
                    "",
                ]
            )
            head.setData(0, GROUP_ROLE, group)
            font = head.font(0)
            font.setWeight(font.Weight.DemiBold)
            head.setFont(0, font)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for entry in group.files:
                child = QTreeWidgetItem(
                    [
                        entry.path.name,
                        format_bytes(entry.size, lang),
                        format_datetime(entry.modified, lang),
                        str(entry.path.parent),
                    ]
                )
                child.setData(0, ENTRY_ROLE, entry)
                child.setToolTip(0, str(entry.path))
                child.setToolTip(3, str(entry.path.parent))
                child.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                child.setCheckState(
                    0, Qt.CheckState.Checked if entry.path in selected else Qt.CheckState.Unchecked
                )
                head.addChild(child)
            self.tree.addTopLevelItem(head)
            head.setExpanded(number <= 200)
        self._updating = False
        self._apply_filter()
        self._update_footer()

    def _apply_filter(self) -> None:
        needle = self.filter.text().casefold()
        for index in range(self.tree.topLevelItemCount()):
            head = self.tree.topLevelItem(index)
            group: Group = head.data(0, GROUP_ROLE)
            match = not needle or any(needle in str(e.path).casefold() for e in group.files)
            head.setHidden(not match)

    def _item_changed(self, tree_item: QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0:
            return
        entry = tree_item.data(0, ENTRY_ROLE)
        if not isinstance(entry, FileEntry):
            return
        if tree_item.checkState(0) == Qt.CheckState.Checked:
            self._selected().add(entry.path)
        else:
            self._selected().discard(entry.path)
        self._update_footer()

    def _set_all_checked(self, checked: bool) -> None:
        if not checked:
            self._selected().clear()
        self._fill_tree()

    def apply_rule(self, rule: str, refill: bool = True) -> None:
        if self._result is None:
            return
        selected = self._selected()
        selected.clear()
        for group in self._result.groups:
            if rule == "first_listed":
                remove = group.files[1:]
            else:
                remove = files_to_remove(group, rule)
            selected.update(e.path for e in remove)
        if refill:
            self._fill_tree()

    def _toggle_expand(self) -> None:
        expand = not any(
            self.tree.topLevelItem(i).isExpanded() for i in range(self.tree.topLevelItemCount())
        )
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(expand)

    def _double_clicked(self, tree_item: QTreeWidgetItem, _column: int) -> None:
        entry = tree_item.data(0, ENTRY_ROLE)
        if isinstance(entry, FileEntry):
            open_file(str(entry.path))

    def _context_menu(self, pos: QPoint) -> None:
        tree_item = self.tree.itemAt(pos)
        if tree_item is None:
            return
        entry = tree_item.data(0, ENTRY_ROLE)
        menu = QMenu(self)
        if isinstance(entry, FileEntry):
            group: Group = tree_item.parent().data(0, GROUP_ROLE)
            menu.addAction(tr("common.open"), lambda: open_file(str(entry.path)))
            menu.addAction(tr("common.show_in_explorer"), lambda: show_in_explorer(str(entry.path)))
            menu.addAction(tr("common.copy_path"), lambda: copy_text(str(entry.path)))
            menu.addSeparator()
            menu.addAction(t("keep_only_this"), lambda: self._keep_only(group, entry))
            menu.addAction(t("exclude_folder"), lambda: self._select_in_folder(entry.path.parent, False))
            menu.addAction(t("select_folder"), lambda: self._select_in_folder(entry.path.parent, True))
        else:
            group = tree_item.data(0, GROUP_ROLE)
            menu.addAction(t("group.unselect"), lambda: self._group_select(group, False))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _keep_only(self, group: Group, keep: FileEntry) -> None:
        selected = self._selected()
        for entry in group.files:
            if entry is keep:
                selected.discard(entry.path)
            else:
                selected.add(entry.path)
        self._fill_tree()

    def _group_select(self, group: Group, checked: bool) -> None:
        for entry in group.files:
            self._selected().discard(entry.path)
        self._fill_tree()

    def _select_in_folder(self, folder: Path, checked: bool) -> None:
        """Select (or unselect) every copy that lies in ``folder``, keeping one per group."""
        if self._result is None:
            return
        selected = self._selected()
        for group in self._result.groups:
            for entry in group.files:
                if entry.path.parent == folder:
                    if checked:
                        selected.add(entry.path)
                    else:
                        selected.discard(entry.path)
        self._fill_tree()

    # -- footer and actions -----------------------------------------------------------------

    def _selected_entries(self) -> list[FileEntry]:
        if self._result is None:
            return []
        selected = self._selected()
        return [e for g in self._result.groups for e in g.files if e.path in selected]

    def _update_footer(self) -> None:
        lang = self.context.translator.language
        entries = self._selected_entries()
        size = sum(e.size for e in entries)
        self.selection_label.setText(
            t("selection", count=len(entries), size=format_bytes(size, lang))
        )
        self.recycle_button.setText(t("recycle", count=len(entries)))
        enabled = bool(entries) and not self.busy
        for button in (self.recycle_button, self.move_button):
            button.setEnabled(enabled)
        self.export_button.setEnabled(bool(self._result and self._result.groups) and not self.busy)

    def _check_complete_groups(self) -> bool:
        assert self._result is not None
        complete = groups_fully_selected(self._result.groups, self._selected())
        if complete:
            self.info.show_message("error", t("all_copies_selected", count=len(complete)))
            return False
        return True

    def recycle_selected(self) -> None:
        entries = self._selected_entries()
        if not entries or not self._check_complete_groups():
            return
        lang = self.context.translator.language
        size = format_bytes(sum(e.size for e in entries), lang)
        if self.option("confirm_before_delete") and not dialogs.confirm_destructive(
            self,
            t("recycle.title", count=len(entries)),
            t("recycle.body", count=len(entries), size=size),
            t("recycle.ok"),
            tr("common.cancel"),
        ):
            return

        def work(job: Job) -> object:
            return recycle(entries, job)

        self.run_task(work, self._action_done, t("recycling"))

    def move_selected(self) -> None:
        entries = self._selected_entries()
        if not entries or not self._check_complete_groups():
            return
        destination = QFileDialog.getExistingDirectory(self, t("move.choose"), str(Path.home()))
        if not destination:
            return
        target = Path(destination)

        def work(job: Job) -> object:
            return move_to(entries, target, job)

        self.run_task(work, self._action_done, t("moving"))

    def _action_done(self, result: Any) -> None:
        lang = self.context.translator.language
        if result.failed:
            self.info.show_message(
                "warning",
                t("action.partial", done=result.done, failed=len(result.failed), first=result.failed[0][1]),
            )
        else:
            self.info.show_message(
                "success", t("action.done", count=result.done, size=format_bytes(result.freed, lang))
            )
        self._remove_missing()

    def _remove_missing(self) -> None:
        """Drop files that no longer exist and groups with fewer than two copies."""
        if self._result is None:
            return
        groups = []
        for group in self._result.groups:
            files = [e for e in group.files if e.path.exists()]
            if len(files) > 1:
                groups.append(Group(group.size, files))
        self._result.groups = groups
        self._selected().intersection_update(e.path for g in groups for e in g.files)
        self._fill_tree()

    def export_report(self) -> None:
        if self._result is None:
            return
        suggested = str(Path.home() / f"{t('report_name')}-{date.today().isoformat()}.csv")
        target = save_file_dialog(self, tr("common.export_csv"), suggested, tr("common.csv_filter"))
        if target is None:
            return
        export_csv(self._result.groups, target, self._selected())
        self.info.show_message("success", tr("common.saved_to", path=str(target)))

    def set_busy(self, busy: bool) -> None:
        for widget in (self.folders, self.scan_button, self.method, self.min_size, self.types, self.tree):
            widget.setEnabled(not busy)
        self._update_footer()

    def screenshot_prepare(self) -> None:
        """Used by build/screenshots_tools.py to show a filled window."""
        self.start_scan()

    def handle_message(self, _text: str) -> None:
        """Brought to the front by a second start; nothing else to do."""


