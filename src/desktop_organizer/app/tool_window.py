"""Base class for every tool window, so all tools share one layout and behavior.

Layout: heading, toolbar row, content, result/progress row. Esc closes the window and
the window geometry is remembered per tool.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.core.i18n import tr


class ToolWindow(QWidget):
    tool_id: str = ""

    def __init__(self, context: AppContext) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.context = context
        self.setObjectName("ToolRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.heading = QLabel()
        self.heading.setProperty("textStyle", "title")
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)
        self.content = QVBoxLayout()
        self.content.setSpacing(12)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self.heading)
        root.addLayout(self.toolbar)
        root.addLayout(self.content, 1)
        root.addLayout(self.footer)

        dialogs.shortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        context.translator.subscribe(self._retranslate)
        self._restore_geometry()

    def _retranslate(self) -> None:
        title = tr(f"tool.{self.tool_id}.title")
        self.setWindowTitle(f"{title} – {tr('app.name')}")
        self.heading.setText(title)
        self.retranslate()

    def retranslate(self) -> None:
        """Subclasses update their own texts here; called on language change."""

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt naming
        self._retranslate()
        super().showEvent(event)  # type: ignore[arg-type]

    def _restore_geometry(self) -> None:
        saved = self.context.settings.get("window_geometry").get(self.tool_id)
        if isinstance(saved, str):
            self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
        else:
            self.resize(880, 600)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        geometry = dict(self.context.settings.get("window_geometry"))
        geometry[self.tool_id] = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self.context.settings.set("window_geometry", geometry)
        self.context.translator.unsubscribe(self._retranslate)
        super().closeEvent(event)
