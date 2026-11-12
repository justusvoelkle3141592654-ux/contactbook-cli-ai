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
        self._app.setStyleSheet(build_stylesheet(self._tokens) + _image_rules(self._tokens))
        tinted_icon.cache_clear()
        self.changed.emit()

    def icon(self, name: str, secondary: bool = False) -> QIcon:
        color = self._tokens.text_secondary if secondary else self._tokens.text
        return tinted_icon(name, color)

    def accent_icon(self, name: str) -> QIcon:
        return tinted_icon(name, self._tokens.accent)

    def on_change(self, callback: Callable[[], None]) -> None:
        self.changed.connect(callback)


def _icon_file(name: str, color: str, stroke: str | None = None) -> str:
    """Style sheets can only reference image files, so write tinted icons to disk."""
    folder = Path(tempfile.gettempdir()) / "DesktopOrganizer-ui"
    folder.mkdir(exist_ok=True)
    suffix = f"-{stroke}" if stroke else ""
    target = folder / f"{name}-{color.lstrip('#')}{suffix}.svg"
    if not target.exists():
        svg = (resources_dir() / "icons" / f"{name}.svg").read_text(encoding="utf-8")
        svg = svg.replace("currentColor", color)
        if stroke:
            svg = svg.replace('stroke-width="2"', f'stroke-width="{stroke}"')
        target.write_text(svg, encoding="utf-8")
    return target.as_posix()


def _image_rules(t: Tokens) -> str:
    arrow = _icon_file("chevron-down", t.text_secondary)
    check = _icon_file("check", t.on_accent, stroke="3")
    indicator = (
        "QCheckBox::indicator, QTableView::indicator, QTreeView::indicator, QListView::indicator"
    )
    return f"""
QComboBox::down-arrow {{ image: url({arrow}); width: 16px; height: 16px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none;
}}
{indicator} {{
    width: 16px; height: 16px;
    border: 1px solid {t.control_border}; border-radius: 4px; background: {t.surface};
}}
QCheckBox::indicator:hover, QTableView::indicator:hover, QTreeView::indicator:hover {{
    border-color: {t.text_secondary};
}}
QCheckBox::indicator:checked, QTableView::indicator:checked, QTreeView::indicator:checked,
QListView::indicator:checked {{
    background: {t.accent}; border-color: {t.accent}; image: url({check});
}}
QCheckBox::indicator:disabled {{ border-color: {t.divider}; background: {t.surface_alt}; }}
QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 9px;
    border: 1px solid {t.control_border}; background: {t.surface};
}}
QRadioButton::indicator:checked {{ border: 5px solid {t.accent}; background: {t.on_accent}; }}
"""


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
