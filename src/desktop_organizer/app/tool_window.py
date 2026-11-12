"""Base class for every tool window, so all tools share one layout and behavior.

Layout (see docs/design-system.md, "Tool window"):

    header   icon tile, title, one-line description
    toolbar  primary inputs and actions (self.toolbar)
    content  main area, usually a table inside a card (self.content)
    footer   result message, progress, final actions (self.footer)

Esc closes the window and the window geometry is remembered per tool.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.widgets import IconTile
from desktop_organizer.core.i18n import tr


class ToolWindow(QWidget):
    tool_id: str = ""
    icon: str = "layout-grid"

    def __init__(self, context: AppContext) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.context = context
        self.setObjectName("ToolRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.heading = QLabel()
        self.heading.setProperty("textStyle", "title")
        self.description = QLabel()
        self.description.setProperty("textStyle", "secondary")
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.heading)
        titles.addWidget(self.description)
        header = QHBoxLayout()
        header.setSpacing(16)
        header.addWidget(IconTile(context.theme, self.icon, size=48))
        header.addLayout(titles, 1)

        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)
        self.content = QVBoxLayout()
        self.content.setSpacing(12)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)
        root.addLayout(header)
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
        self.description.setText(tr(f"tool.{self.tool_id}.description"))
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
            self.resize(960, 640)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        geometry = dict(self.context.settings.get("window_geometry"))
        geometry[self.tool_id] = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self.context.settings.set("window_geometry", geometry)
        self.context.translator.unsubscribe(self._retranslate)
        super().closeEvent(event)
