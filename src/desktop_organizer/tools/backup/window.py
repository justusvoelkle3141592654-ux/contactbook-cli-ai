"""Backup window: profiles on the left, profile editor and results on the right."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import FolderList, FolderPicker, Table, item, open_file
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_bytes, format_datetime, format_number
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.tools.backup import SETTINGS
from desktop_organizer.tools.backup.logic import (
    BackupError,
    BackupPlan,
    Options,
    RunResult,
    load_history,
    make_plan,
    run,
    save_history,
    validate,
)

TOOL = "backup"
MODES = ("update", "mirror")


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class BackupWindow(ToolWindow):
    tool_id = TOOL
    icon = "hard-drive-download"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._plan: BackupPlan | None = None
        self._loading = False
        self.history_file = context.paths.data_dir / TOOL / "history.json"
        self.log_dir = context.paths.data_dir / TOOL / "logs"

        # Profiles --------------------------------------------------------------------------
        self.profiles_label = QLabel()
        self.profiles_label.setProperty("textStyle", "section")
        self.profiles = QListWidget()
        self.profiles.currentRowChanged.connect(self._load_profile)
        self.new_button = QPushButton()
        self.new_button.clicked.connect(self.new_profile)
        self.rename_button = QPushButton()
        self.rename_button.clicked.connect(self.rename_profile)
        self.delete_button = QPushButton()
        self.delete_button.clicked.connect(self.delete_profile)
        left = QFrame()
        left.setObjectName("Panel")
        left.setMinimumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.profiles_label)
        left_layout.addWidget(self.profiles, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.rename_button)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.delete_button)

        # Editor ----------------------------------------------------------------------------
        self.sources_label = QLabel()
        self.sources_label.setProperty("textStyle", "section")
        self.sources = FolderList()
        self.sources.changed.connect(self._save_profile)
        self.sources.list.setMaximumHeight(130)
        self.destination_label = QLabel()
        self.destination_label.setProperty("textStyle", "section")
        self.destination = FolderPicker("tool.backup.no_destination")
        self.destination.changed.connect(lambda _p: self._save_profile())
        self.mode_label = QLabel()
        self.mode = QComboBox()
        self.mode.currentIndexChanged.connect(lambda _i: self._save_profile())
        self.mode_hint = QLabel()
        self.mode_hint.setProperty("textStyle", "caption")
        self.mode_hint.setWordWrap(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode)
        mode_row.addWidget(self.mode_hint, 1)

        self.tabs = QTabWidget()
        self.preview_table = Table(4)
        self.preview_table.setColumnWidth(1, 110)
        self.preview_table.setColumnWidth(2, 110)
        self.preview_table.setColumnWidth(3, 380)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setProperty("mono", True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.history_table = Table(5)
        self.history_table.setColumnWidth(0, 160)
        self.history_table.doubleClicked.connect(self._open_history_log)
        self.tabs.addTab(self.preview_table, "")
        self.tabs.addTab(self.log_view, "")
        self.tabs.addTab(self.history_table, "")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.sources_label)
        right_layout.addWidget(self.sources)
        right_layout.addWidget(self.destination_label)
        right_layout.addWidget(self.destination)
        right_layout.addLayout(mode_row)
        right_layout.addSpacing(4)
        right_layout.addWidget(self.tabs, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([260, 840])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        self.summary = QLabel()
        self.summary.setProperty("textStyle", "secondary")
        self.preview_button = QPushButton()
        self.preview_button.clicked.connect(self.create_preview)
        self.start_button = QPushButton()
        self.start_button.setProperty("role", "primary")
        self.start_button.clicked.connect(self.start_backup)
        self.footer.addWidget(self.summary, 1)
        self.footer.addWidget(self.preview_button)
        self.footer.addWidget(self.start_button)

        self._fill_profiles()
        self.retranslate()

    # -- profiles ------------------------------------------------------------------------

    def _stored_profiles(self) -> list[dict[str, Any]]:
        stored = self.context.settings.tool_values(TOOL).get("profiles")
        return [p for p in stored if isinstance(p, dict)] if isinstance(stored, list) else []

    def _store_profiles(self, profiles: list[dict[str, Any]]) -> None:
        self.context.settings.set_tool_value(TOOL, "profiles", profiles)

    def _fill_profiles(self, select_id: str | None = None) -> None:
        profiles = self._stored_profiles()
        if not profiles:
            profiles = [{"id": uuid.uuid4().hex, "name": t("default_profile"), "sources": [], "destination": "", "mode": "update"}]
            self._store_profiles(profiles)
        self._loading = True
        self.profiles.clear()
        for profile in profiles:
            entry = QListWidgetItem(str(profile.get("name", "")))
            entry.setData(Qt.ItemDataRole.UserRole, profile.get("id"))
            self.profiles.addItem(entry)
        self._loading = False
        ids = [p.get("id") for p in profiles]
        self.profiles.setCurrentRow(ids.index(select_id) if select_id in ids else 0)

    def _current_profile(self) -> dict[str, Any] | None:
        row = self.profiles.currentRow()
        profiles = self._stored_profiles()
        return profiles[row] if 0 <= row < len(profiles) else None

    def _load_profile(self, _row: int) -> None:
        if self._loading:
            return
        profile = self._current_profile()
        if profile is None:
            return
        self._loading = True
        self.sources.set_folders([s for s in profile.get("sources", []) if isinstance(s, str)])
        self.destination.set_path(str(profile.get("destination", "")))
        self.mode.setCurrentIndex(max(0, self.mode.findData(profile.get("mode", "update"))))
        self._loading = False
        self._plan = None
        self.preview_table.clear_rows()
        self._update_mode_hint()
        self._update_footer()

    def _save_profile(self) -> None:
        self._update_mode_hint()
        if self._loading:
            return
        row = self.profiles.currentRow()
        profiles = self._stored_profiles()
        if not 0 <= row < len(profiles):
            return
        profiles[row] = {
            **profiles[row],
            "sources": self.sources.folders(),
            "destination": self.destination.path(),
            "mode": self.mode.currentData() or "update",
        }
        self._store_profiles(profiles)
        self._plan = None
        self.preview_table.clear_rows()
        self._update_footer()

    def new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, t("new_profile"), t("profile_name"))
        if not ok or not name.strip():
            return
        profile = {"id": uuid.uuid4().hex, "name": name.strip(), "sources": [], "destination": "", "mode": "update"}
        self._store_profiles([*self._stored_profiles(), profile])
        self._fill_profiles(profile["id"])

    def rename_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        name, ok = QInputDialog.getText(self, t("rename_profile"), t("profile_name"), QLineEdit.EchoMode.Normal, str(profile["name"]))
        if not ok or not name.strip():
            return
        profiles = self._stored_profiles()
        profiles[self.profiles.currentRow()]["name"] = name.strip()
        self._store_profiles(profiles)
        self._fill_profiles(profile["id"])

    def delete_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        if not dialogs.confirm_destructive(
            self, t("delete_profile.title", name=profile["name"]), t("delete_profile.body"), tr("common.delete"), tr("common.cancel")
        ):
            return
        profiles = [p for p in self._stored_profiles() if p.get("id") != profile.get("id")]
        self._store_profiles(profiles)
        self._fill_profiles()

    # -- texts ---------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.profiles_label.setText(t("profiles"))
        self.new_button.setText(tr("common.new"))
        self.rename_button.setText(t("rename"))
        self.delete_button.setText(tr("common.delete"))
        self.sources_label.setText(t("sources"))
        self.sources.retranslate()
        self.destination_label.setText(t("destination"))
        self.destination.retranslate()
        self.mode_label.setText(t("mode"))
        current = self.mode.currentData() or (self._current_profile() or {}).get("mode", "update")
        self._loading, was = True, self._loading
        self.mode.clear()
        for mode in MODES:
            self.mode.addItem(t(f"mode.{mode}"), mode)
        self.mode.setCurrentIndex(max(0, self.mode.findData(current)))
        self._loading = was
        self.tabs.setTabText(0, t("tab.preview"))
        self.tabs.setTabText(1, t("tab.log"))
        self.tabs.setTabText(2, t("tab.history"))
        self.preview_table.set_headers([t("col.file"), t("col.action"), t("col.size"), t("col.target")])
        self.history_table.set_headers([t("col.time"), t("col.profile"), t("col.copied"), t("col.result"), t("col.destination")])
        self.preview_button.setText(t("preview"))
        self.start_button.setText(t("start"))
        self._update_mode_hint()
        self._fill_history()
        self._update_footer()

    def _update_mode_hint(self) -> None:
        self.mode_hint.setText(t(f"mode.{self.mode.currentData() or 'update'}.hint"))

    # -- preview and run -----------------------------------------------------------------

    def _options(self) -> Options:
        opts = self.options()
        return Options(
            mirror=self.mode.currentData() == "mirror",
            verify=opts["verify"],
            exclude=tuple(p.strip() for p in opts["exclude"].split(";") if p.strip()),
            skip_hidden=opts["skip_hidden"],
        )

    def _inputs(self) -> tuple[list[Path], Path] | None:
        sources = [Path(s) for s in self.sources.folders()]
        destination = self.destination.path()
        if not sources:
            self.info.show_message("error", t("error.no_sources"))
            return None
        if not destination:
            self.info.show_message("error", t("error.no_destination"))
            return None
        try:
            validate(sources, Path(destination))
        except BackupError as exc:
            self.info.show_message("error", t(f"error.{exc}"))
            return None
        return sources, Path(destination)

    def create_preview(self, then_run: bool = False) -> None:
        inputs = self._inputs()
        if inputs is None:
            return
        sources, destination = inputs
        options = self._options()

        def work(job: Job) -> BackupPlan:
            return make_plan(sources, destination, options, job)

        self.run_task(work, lambda plan: self._preview_ready(plan, then_run), t("comparing"))

    def _preview_ready(self, plan: Any, then_run: bool) -> None:
        assert isinstance(plan, BackupPlan)
        self._plan = plan
        lang = self.context.translator.language
        table = self.preview_table
        table.setSortingEnabled(False)
        table.clear_rows()
        for copy in plan.copies[:20000]:
            table.source.appendRow(
                [
                    item(copy.source.name),
                    item(t(f"action.{copy.reason}")),
                    item(format_bytes(copy.size, lang), sort=copy.size),
                    item(str(copy.target.parent)),
                ]
            )
        for path in plan.deletions[:20000]:
            table.source.appendRow([item(path.name), item(t("action.remove")), item("", sort=0), item(str(path.parent))])
        table.setSortingEnabled(True)
        self.tabs.setCurrentIndex(0)
        if plan.errors:
            self.info.show_message("warning", t("read_errors", count=len(plan.errors)))
        elif not plan.copies and not plan.deletions:
            self.info.show_message("success", t("up_to_date", count=plan.unchanged))
        self._update_footer()
        if then_run:
            self._run_plan()

    def start_backup(self) -> None:
        if self._plan is None:
            self.create_preview(then_run=True)
        else:
            self._run_plan()

    def _run_plan(self) -> None:
        plan = self._plan
        if plan is None or (not plan.copies and not plan.deletions):
            return
        if plan.deletions and self.option("confirm_mirror") and not dialogs.confirm_destructive(
            self,
            t("mirror.title", count=len(plan.deletions)),
            t("mirror.body", count=len(plan.deletions)),
            t("mirror.ok"),
            tr("common.cancel"),
        ):
            return
        options = self._options()
        profile = self._current_profile() or {}
        destination = Path(self.destination.path())

        def work(job: Job) -> RunResult:
            return run(plan, options, job)

        def done(result: Any) -> None:
            assert isinstance(result, RunResult)
            log_path = save_history(self.history_file, str(profile.get("name", "")), destination, result, self.log_dir)
            self.log_view.setPlainText(log_path.read_text(encoding="utf-8"))
            self.tabs.setCurrentIndex(1)
            lang = self.context.translator.language
            if result.ok:
                self.info.show_message(
                    "success",
                    t("done", copied=format_number(result.copied, lang), size=format_bytes(result.copied_bytes, lang), verified=result.verified),
                )
            else:
                self.info.show_message(
                    "warning", t("done.errors", copied=result.copied, failed=len(result.failed), verify=len(result.verify_failed))
                )
            self._plan = None
            self.preview_table.clear_rows()
            self._fill_history()
            self._update_footer()

        self.run_task(work, done, t("copying"))

    # -- history and footer ----------------------------------------------------------------

    def _fill_history(self) -> None:
        lang = self.context.translator.language
        table = self.history_table
        table.setSortingEnabled(False)
        table.clear_rows()
        for entry in load_history(self.history_file):
            started = float(entry.get("started", 0) or 0)
            errors = int(entry.get("errors", 0) or 0)
            table.source.appendRow(
                [
                    item(format_datetime(started, lang), sort=started, data=entry.get("log")),
                    item(str(entry.get("profile", ""))),
                    item(t("history.copied", count=entry.get("copied", 0), size=format_bytes(int(entry.get("bytes", 0) or 0), lang))),
                    item(t("history.ok") if errors == 0 else t("history.errors", count=errors)),
                    item(str(entry.get("destination", ""))),
                ]
            )
        table.setSortingEnabled(True)

    def _open_history_log(self, index: Any) -> None:
        from desktop_organizer.app.components import DATA_ROLE

        log = self.history_table.source.item(self.history_table.source_row(index), 0).data(DATA_ROLE)
        if isinstance(log, str) and Path(log).exists():
            open_file(log)

    def _update_footer(self) -> None:
        lang = self.context.translator.language
        if self._plan is None:
            self.summary.setText(t("summary.empty"))
        else:
            self.summary.setText(
                t(
                    "summary",
                    copy=format_number(len(self._plan.copies), lang),
                    size=format_bytes(self._plan.bytes_to_copy, lang),
                    remove=len(self._plan.deletions),
                    unchanged=format_number(self._plan.unchanged, lang),
                )
            )
        ready = bool(self.sources.folders() and self.destination.path()) and not self.busy
        self.preview_button.setEnabled(ready)
        self.start_button.setEnabled(ready)

    def set_busy(self, busy: bool) -> None:
        for widget in (self.profiles, self.sources, self.destination, self.mode, self.new_button, self.rename_button, self.delete_button):
            widget.setEnabled(not busy)
        self._update_footer()

    def screenshot_prepare(self) -> None:
        import tempfile

        source = self.context.settings.tool_values("file_cleaner").get("last_folder")
        if isinstance(source, str):
            self.sources.set_folders([source])
            self.destination.set_path(str(Path(tempfile.mkdtemp()) / "Sicherung"))
            Path(self.destination.path()).mkdir()
            self.create_preview()
