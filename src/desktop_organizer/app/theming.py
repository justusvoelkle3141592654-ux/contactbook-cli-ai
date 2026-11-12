"""Applies the design tokens to Qt and follows the Windows light/dark setting."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from desktop_organizer.core.paths import resources_dir
from desktop_organizer.core.theme import FONT_FAMILIES, Tokens, build_stylesheet, tokens_for


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self, app: QApplication, mode: str) -> None:
        super().__init__()
        self._app = app
        self._mode = mode
        self._tokens = tokens_for(False)
        if app.style().name().lower() != "fusion":
            app.setStyle("Fusion")
        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(14)
        app.setFont(font)
        app.styleHints().colorSchemeChanged.connect(self._on_system_change)
        self.apply()

    @property
    def tokens(self) -> Tokens:
        return self._tokens

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.apply()

    def _on_system_change(self, _scheme: Qt.ColorScheme) -> None:
        if self._mode == "system":
            self.apply()

    def _is_dark(self) -> bool:
        if self._mode == "dark":
            return True
        if self._mode == "light":
            return False
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def apply(self) -> None:
        hints = self._app.styleHints()
        # Qt 6.8: an explicit scheme also switches the native title bar on Windows.
        requested = {
            "dark": Qt.ColorScheme.Dark,
            "light": Qt.ColorScheme.Light,
        }.get(self._mode, Qt.ColorScheme.Unknown)
        hints.setColorScheme(requested)
        self._tokens = tokens_for(self._is_dark())
        self._app.setPalette(_palette(self._tokens))
        self._app.setStyleSheet(
            build_stylesheet(self._tokens) + _arrow_rules(self._tokens.text_secondary)
        )
        tinted_icon.cache_clear()
        self.changed.emit()

    def icon(self, name: str, secondary: bool = False) -> QIcon:
        color = self._tokens.text_secondary if secondary else self._tokens.text
        return tinted_icon(name, color)

    def accent_icon(self, name: str) -> QIcon:
        return tinted_icon(name, self._tokens.accent)

    def on_change(self, callback: Callable[[], None]) -> None:
        self.changed.connect(callback)


def _arrow_rules(color: str) -> str:
    """Style sheets can only reference image files, so write the tinted chevron to disk."""
    folder = Path(tempfile.gettempdir()) / "DesktopOrganizer-ui"
    folder.mkdir(exist_ok=True)
    target = folder / f"chevron-down-{color.lstrip('#')}.svg"
    if not target.exists():
        svg = (resources_dir() / "icons" / "chevron-down.svg").read_text(encoding="utf-8")
        target.write_text(svg.replace("currentColor", color), encoding="utf-8")
    url = target.as_posix()
    return (
        f"QComboBox::down-arrow {{ image: url({url}); width: 16px; height: 16px; }}\n"
        "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right;"
        " width: 28px; border: none; }\n"
    )


def _palette(t: Tokens) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(t.window))
    p.setColor(role.WindowText, QColor(t.text))
    p.setColor(role.Base, QColor(t.surface))
    p.setColor(role.AlternateBase, QColor(t.surface_alt))
    p.setColor(role.Text, QColor(t.text))
    p.setColor(role.Button, QColor(t.surface))
    p.setColor(role.ButtonText, QColor(t.text))
    p.setColor(role.Highlight, QColor(t.accent))
    p.setColor(role.HighlightedText, QColor(t.on_accent))
    p.setColor(role.ToolTipBase, QColor(t.surface))
    p.setColor(role.ToolTipText, QColor(t.text))
    p.setColor(role.PlaceholderText, QColor(t.text_secondary))
    p.setColor(role.Link, QColor(t.accent))
    p.setColor(role.Mid, QColor(t.control_border))
    for r in (role.Text, role.WindowText, role.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, r, QColor(t.text_disabled))
    return p


@lru_cache(maxsize=256)
def tinted_icon(name: str, color: str) -> QIcon:
    """Render a Lucide SVG in the given color at the sizes the UI uses."""
    svg = (resources_dir() / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", color).encode("utf-8")))
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48):
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon
