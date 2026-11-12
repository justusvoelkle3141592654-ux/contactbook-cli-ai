"""Text replacer window: search options, file list and a line-by-line preview."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTextBrowser,
)

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
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.tools.text_replacer import SETTINGS
from desktop_organizer.tools.text_replacer.logic import (
    ApplyResult,
    FileMatches,
    Options,
    Preview,
    apply,
    compile_pattern,
    latest_journal,
    parse_patterns,
    preview,
    undo,
)

TOOL = "text_replacer"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class TextReplacerWindow(ToolWindow):
    tool_id = TOOL
    icon = "replace"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._preview: Preview | None = None
        self.backup_root = context.paths.data_dir / TOOL / "backups"

        self.folder = FolderPicker()
        self.folder.changed.connect(
            lambda p: context.settings.set_tool_value(TOOL, "last_folder", p)
        )
        self.find_label = QLabel()
        self.find = QLineEdit()
        self.replace_label = QLabel()
        self.replace = QLineEdit()
        self.case = QCheckBox()
        self.word = QCheckBox()
        self.regex = QCheckBox()
        self.preview_button = QPushButton()
        self.preview_button.setProperty("role", "primary")
        self.preview_button.clicked.connect(self.create_preview)
        self.find.returnPressed.connect(self.create_preview)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.addWidget(self.folder, 0, 0, 1, 4)
        grid.addWidget(self.find_label, 1, 0)
        grid.addWidget(self.find, 1, 1)
        grid.addWidget(self.replace_label, 1, 2)
        grid.addWidget(self.replace, 1, 3)
        options_row = QGridLayout()
        options_row.setHorizontalSpacing(24)
        options_row.addWidget(self.case, 0, 0)
        options_row.addWidget(self.word, 0, 1)
        options_row.addWidget(self.regex, 0, 2)
        options_row.setColumnStretch(3, 1)
        options_row.addWidget(self.preview_button, 0, 4)
        grid.addLayout(options_row, 2, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.toolbar.addLayout(grid)

        self.files = Table(3)
        self.files.setColumnWidth(1, 110)
        self.files.setColumnWidth(2, 110)
        self.files.selectionModel().currentRowChanged.connect(lambda *_: self._show_details())
        self.files.source.itemChanged.connect(lambda _i: self._update_footer())
        self.files.context_requested.connect(self._context_menu)
        self.details = QTextBrowser()
        self.details.setOpenLinks(False)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.files)
        splitter.addWidget(self.details)
        splitter.setSizes([480, 560])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        self.summary = QLabel()
        self.summary.setProperty("textStyle", "secondary")
        self.undo_button = QPushButton()
        self.undo_button.clicked.connect(self.undo_last)
        self.replace_button = QPushButton()
        self.replace_button.setProperty("role", "primary")
        self.replace_button.clicked.connect(self.replace_selected)
        self.footer.addWidget(self.summary, 1)
        self.footer.addWidget(self.undo_button)
        self.footer.addWidget(self.replace_button)

        stored = context.settings.tool_values(TOOL)
        last = stored.get("last_folder")
        if isinstance(last, str) and Path(last).is_dir():
            self.folder.set_path(last)
        for box, key in ((self.case, "case"), (self.word, "word"), (self.regex, "regex")):
            box.setChecked(bool(stored.get(key, False)))
            box.toggled.connect(lambda v, k=key: context.settings.set_tool_value(TOOL, k, bool(v)))
        self.retranslate()

    def retranslate(self) -> None:
        self.folder.retranslate()
        self.find_label.setText(t("find"))
        self.replace_label.setText(t("replace"))
        self.find.setPlaceholderText(t("find.placeholder"))
        self.replace.setPlaceholderText(t("replace.placeholder"))
        self.case.setText(t("case"))
        self.word.setText(t("word"))
        self.regex.setText(t("regex"))
        self.preview_button.setText(t("preview"))
        self.files.set_headers([t("col.file"), t("col.matches"), t("col.encoding")])
        self.undo_button.setText(t("undo"))
        self._update_footer()
        self._show_details()

    def _options(self) -> Options:
        opts = self.options()
        return Options(
            find=self.find.text(),
            replace=self.replace.text(),
            case_sensitive=self.case.isChecked(),
            whole_word=self.word.isChecked(),
            regex=self.regex.isChecked(),
            patterns=parse_patterns(opts["patterns"]),
            recursive=opts["recursive"],
            skip_hidden=opts["skip_hidden"],
            max_file_size=opts["max_file_mb"] * 1024 * 1024,
        )

    def create_preview(self) -> None:
        folder = self.folder.path()
        if not folder:
            self.folder.browse()
            folder = self.folder.path()
            if not folder:
                return
        options = self._options()
        try:
            compile_pattern(options)
        except (ValueError, re.error) as exc:
            message = t("empty_search") if isinstance(exc, ValueError) else t("bad_regex", error=str(exc))
            self.info.show_message("error", message)
            return

        def work(job: Job) -> Preview:
            return preview(Path(folder), options, job)

        self._options_used = options
        self.run_task(work, self._preview_ready, t("searching"))

    def _preview_ready(self, result: Any) -> None:
        assert isinstance(result, Preview)
        self._preview = result
        self.files.setSortingEnabled(False)
        self.files.clear_rows()
        base = Path(self.folder.path())
        for index, matches in enumerate(result.files):
            try:
                shown = str(matches.path.relative_to(base))
            except ValueError:
                shown = str(matches.path)
            cell = item(shown, data=index, checkable=True)
            cell.setToolTip(str(matches.path))
            self.files.source.appendRow(
                [
                    cell,
                    item(str(matches.count), sort=matches.count),
                    item(matches.encoding.upper()),
                ]
            )
        self.files.setSortingEnabled(True)
        if result.files:
            self.files.selectRow(0)
        skipped = result.skipped_binary + result.skipped_unreadable
        if not result.files:
            self.info.show_message("info", t("no_matches"))
        elif skipped:
            self.info.show_message("info", t("skipped", count=skipped))
        self._update_footer()
        self._show_details()

    def _matches(self, row: int) -> FileMatches:
        assert self._preview is not None
        return self._preview.files[int(self.files.source.item(row, 0).data(DATA_ROLE))]

    def _selected(self) -> list[FileMatches]:
        if self._preview is None:
            return []
        return [self._matches(row) for row in self.files.checked_rows()]

    def _show_details(self) -> None:
        rows = self.files.selected_rows()
        if self._preview is None or not rows:
            self.details.setHtml(f"<p style='color:gray'>{html.escape(t('details.empty'))}</p>")
            return
        matches = self._matches(rows[0])
        tokens = self.context.theme.tokens
        parts = [
            f"<p><b>{html.escape(matches.path.name)}</b> &nbsp; "
            f"<span style='color:{tokens.text_secondary}'>{html.escape(t('details.count', count=matches.count))}</span></p>"
        ]
        for change in matches.lines:
            parts.append(
                "<table width='100%' cellspacing='0' cellpadding='4' style='margin-bottom:6px'>"
                f"<tr><td width='48' style='color:{tokens.text_secondary}'>{change.number}</td>"
                f"<td style='background:{tokens.error_subtle};font-family:Consolas,monospace'>− {html.escape(change.before)}</td></tr>"
                f"<tr><td></td><td style='background:{tokens.success_subtle};font-family:Consolas,monospace'>+ {html.escape(change.after)}</td></tr>"
                "</table>"
            )
        if matches.count > len(matches.lines):
            parts.append(f"<p style='color:{tokens.text_secondary}'>{html.escape(t('details.more'))}</p>")
        self.details.setHtml("".join(parts))

    def replace_selected(self) -> None:
        files = self._selected()
        if not files:
            return
        total = sum(f.count for f in files)
        options = getattr(self, "_options_used", self._options())
        backup = bool(self.option("backup"))
        if self.option("confirm_before_replace") and not dialogs.confirm(
            self,
            t("confirm.title", count=total, files=len(files)),
            t("confirm.body.backup") if backup else t("confirm.body.nobackup"),
            t("confirm.ok"),
            tr("common.cancel"),
        ):
            return
        root = self.backup_root

        def work(job: Job) -> ApplyResult:
            return apply(files, options, root, backup, job)

        self.run_task(work, self._applied, t("replacing"))

    def _applied(self, result: Any) -> None:
        assert isinstance(result, ApplyResult)
        if result.failed:
            known = {
                "changed": t("reason.changed"),
                "read-only": t("reason.read-only"),
                "binary": t("reason.binary"),
            }
            reasons = ", ".join(f"{p.name} ({known.get(r, r)})" for p, r in result.failed[:4])
            self.info.show_message(
                "warning", t("done.partial", files=result.files, count=result.replacements, failed=reasons)
            )
        else:
            self.info.show_message("success", t("done", files=result.files, count=result.replacements))
        self._preview = None
        self.files.clear_rows()
        self._update_footer()
        self._show_details()

    def undo_last(self) -> None:
        journal = latest_journal(self.backup_root)
        if journal is None:
            return
        if not dialogs.confirm(self, t("undo.title"), t("undo.body"), t("undo"), tr("common.cancel")):
            return
        restored, failed = undo(journal)
        if failed:
            self.info.show_message("warning", t("undo.partial", count=restored, failed=len(failed)))
        else:
            self.info.show_message("success", t("undo.done", count=restored))
        self._update_footer()

    def _context_menu(self, row: int, pos: QPoint) -> None:
        path = str(self._matches(row).path)
        menu = QMenu(self)
        menu.addAction(tr("common.open"), lambda: open_file(path))
        menu.addAction(tr("common.show_in_explorer"), lambda: show_in_explorer(path))
        menu.addAction(tr("common.copy_path"), lambda: copy_text(path))
        menu.exec(pos)

    def _update_footer(self) -> None:
        files = self._selected()
        total = sum(f.count for f in files)
        self.summary.setText(
            t("summary", count=total, files=len(files)) if self._preview else t("summary.empty")
        )
        self.replace_button.setText(t("replace_button", count=total))
        self.replace_button.setEnabled(bool(files) and not self.busy)
        self.undo_button.setEnabled(latest_journal(self.backup_root) is not None and not self.busy)

    def set_busy(self, busy: bool) -> None:
        for widget in (self.folder, self.find, self.replace, self.preview_button, self.files):
            widget.setEnabled(not busy)
        self._update_footer()

    def theme_changed(self) -> None:
        self._show_details()

    def screenshot_prepare(self) -> None:
        self.find.setText("Notizen")
        self.replace.setText("Notizbuch")
        self.create_preview()
