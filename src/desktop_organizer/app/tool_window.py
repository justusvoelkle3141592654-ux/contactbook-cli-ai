"""Base class for every tool window, so all tools share one layout and behavior.

Each tool runs as its own process and its own top-level window (taskbar entry grouped
under Desktop Organizer). Layout (see docs/design-system.md, "Tool window"):

    header   icon tile, title, one-line description, settings button
    info     inline message bar (self.info)
    toolbar  primary inputs and actions (self.toolbar)
    content  main area (self.content)
    footer   progress panel, status text, final actions (self.footer)

Esc closes the window; geometry is remembered per tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from desktop_organizer.app import dialogs, worker
from desktop_organizer.app.components import InfoBar, ProgressPanel, ToolSettingsDialog
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.widgets import IconTile
from desktop_organizer.core import tool_settings
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.jobs import Job
from desktop_organizer.core.tool_settings import SettingField


class ToolWindow(QWidget):
    tool_id: str = ""
    icon: str = "layout-grid"
    settings_fields: tuple[SettingField, ...] = ()

    def __init__(self, context: AppContext) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.context = context
        self.setObjectName("ToolRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._worker: worker.Worker | None = None

        self.heading = QLabel()
        self.heading.setProperty("textStyle", "title")
        self.description = QLabel()
        self.description.setProperty("textStyle", "secondary")
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.heading)
        titles.addWidget(self.description)
        self.settings_button = QPushButton()
        self.settings_button.setIcon(context.theme.icon("settings"))
        self.settings_button.clicked.connect(self.open_settings)
        self.settings_button.setVisible(bool(self.settings_fields))
        self.settings_button.setToolTip("Ctrl+,")
        header = QHBoxLayout()
        header.setSpacing(16)
        header.addWidget(IconTile(context.theme, self.icon, size=48))
        header.addLayout(titles, 1)
        header.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignTop)

        self.info = InfoBar(context.theme)
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)
        self.content = QVBoxLayout()
        self.content.setSpacing(12)
        self.progress = ProgressPanel()
        self.progress.cancel_requested.connect(self.cancel_task)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)
        root.addLayout(header)
        root.addWidget(self.info)
        root.addLayout(self.toolbar)
        root.addLayout(self.content, 1)
        root.addWidget(self.progress)
        root.addLayout(self.footer)

        dialogs.shortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        dialogs.shortcut("Ctrl+,", self, self.open_settings)
        # Start without a focused control, so no focus ring shows until Tab is used.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._first_show = True
        context.translator.subscribe(self._retranslate)
        context.theme.on_change(self._on_theme_change)
        context.settings.subscribe(self._settings_changed)
        self._restore_geometry()

    # -- texts and theme -----------------------------------------------------------------

    def _retranslate(self) -> None:
        title = tr(f"tool.{self.tool_id}.title")
        self.setWindowTitle(f"{title} – {tr('app.name')}")
        self.heading.setText(title)
        self.description.setText(tr(f"tool.{self.tool_id}.description"))
        self.settings_button.setText(tr("common.settings"))
        self.progress.cancel_button.setText(tr("common.cancel"))
        self.retranslate()

    def retranslate(self) -> None:
        """Subclasses update their own texts here; called on language change."""

    def _on_theme_change(self) -> None:
        self.settings_button.setIcon(self.context.theme.icon("settings"))
        self.theme_changed()

    def theme_changed(self) -> None:
        """Subclasses repaint custom elements here."""

    # -- settings ------------------------------------------------------------------------

    def option(self, key: str) -> Any:
        return tool_settings.values(self.context.settings, self.tool_id, self.settings_fields)[key]

    def options(self) -> dict[str, Any]:
        return tool_settings.values(self.context.settings, self.tool_id, self.settings_fields)

    def open_settings(self) -> None:
        dialog = ToolSettingsDialog(
            self.context.settings, self.tool_id, self.settings_fields, self
        )
        dialog.exec()

    def _settings_changed(self, key: str, _value: object) -> None:
        if key == "tools":
            self.settings_changed()

    def settings_changed(self) -> None:
        """Subclasses react to changed tool options here."""

    # -- background work -----------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def run_task(
        self,
        function: Callable[[Job], Any],
        on_done: Callable[[Any], None],
        start_text: str,
        on_cancelled: Callable[[], None] | None = None,
    ) -> None:
        """Run ``function`` in a worker thread with progress panel and cancel button."""
        if self._worker is not None:
            return
        self.info.hide()
        task = worker.Worker(function)
        self._worker = task
        self.progress.start(start_text)
        self.set_busy(True)

        def finished(result: object) -> None:
            self._end_task()
            on_done(result)

        def failed(message: str) -> None:
            self._end_task()
            self.info.show_message("error", tr("common.failed", error=message))

        def cancelled() -> None:
            self._end_task()
            self.info.show_message("info", tr("common.cancelled"))
            if on_cancelled is not None:
                on_cancelled()

        task.signals.progress.connect(self.progress.update_progress)
        task.signals.finished.connect(finished)
        task.signals.failed.connect(failed)
        task.signals.cancelled.connect(cancelled)
        worker.start(task)

    def _end_task(self) -> None:
        self._worker = None
        self.progress.finish()
        self.set_busy(False)

    def cancel_task(self) -> None:
        if self._worker is not None:
            self._worker.job.cancel()
            self.progress.cancel_button.setEnabled(False)

    def set_busy(self, busy: bool) -> None:
        """Subclasses disable inputs while a task runs."""

    # -- window lifecycle ----------------------------------------------------------------

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt naming
        self._retranslate()
        super().showEvent(event)  # type: ignore[arg-type]
        if self._first_show:
            self._first_show = False
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _restore_geometry(self) -> None:
        saved = self.context.settings.get("window_geometry").get(self.tool_id)
        if isinstance(saved, str):
            self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
        else:
            self.resize(1040, 700)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        if self._worker is not None:
            self._worker.job.cancel()
        geometry = dict(self.context.settings.get("window_geometry"))
        geometry[self.tool_id] = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self.context.settings.set("window_geometry", geometry)
        self.context.translator.unsubscribe(self._retranslate)
        self.context.settings.unsubscribe(self._settings_changed)
        super().closeEvent(event)
