"""Custom-painted building blocks shared by all windows (see docs/design-system.md).

They paint with the current design tokens so light and dark themes stay exact, and they
expose accessible names so screen readers announce them like standard controls.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.core.theme import Tokens


def _font(base: QFont, size: int, semibold: bool = False) -> QFont:
    font = QFont(base)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if semibold else QFont.Weight.Normal)
    return font


def _focus_ring(painter: QPainter, rect: QRectF, t: Tokens, radius: float) -> None:
    pen = QPen(QColor(t.accent))
    pen.setWidthF(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)


class KeyboardFocusMixin:
    """Show the focus ring only when focus arrived by keyboard, as Windows 11 does."""

    _keyboard_focus = False

    def _track_focus_in(self, event: QFocusEvent) -> None:
        self._keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )

    def show_focus_ring(self) -> bool:
        return self._keyboard_focus and self.hasFocus()  # type: ignore[attr-defined]


class NavButton(KeyboardFocusMixin, QAbstractButton):
    """Sidebar entry: icon, label, optional count, selection marker."""

    HEIGHT = 36

    def __init__(self, theme: ThemeManager, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon = icon
        self._count: int | None = None
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        self._track_focus_in(event)
        super().focusInEvent(event)

    def set_count(self, count: int | None) -> None:
        self._count = count
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, self.HEIGHT)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        t = self._theme.tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self.isChecked() or self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.nav_selected if self.isChecked() else t.nav_hover))
            p.drawRoundedRect(rect, 4, 4)
        if self.isChecked():
            p.setBrush(QColor(t.accent))
            p.drawRoundedRect(QRectF(0, rect.center().y() - 8, 3, 16), 1.5, 1.5)
        if self.show_focus_ring():
            _focus_ring(p, rect, t, 4)

        self._theme.icon(self._icon).paint(p, QRect(12, int(rect.center().y()) - 8, 16, 16))
        p.setPen(QColor(t.text))
        p.setFont(_font(self.font(), 14, semibold=self.isChecked()))
        right = 12
        if self._count is not None:
            count_font = _font(self.font(), 12)
            text = str(self._count)
            width = QFontMetrics(count_font).horizontalAdvance(text)
            p.setFont(count_font)
            p.setPen(QColor(t.text_secondary))
            p.drawText(
                QRect(self.width() - 12 - width, 0, width, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                text,
            )
            right += width + 8
            p.setPen(QColor(t.text))
            p.setFont(_font(self.font(), 14, semibold=self.isChecked()))
        p.drawText(
            QRect(40, 0, self.width() - 40 - right, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
        p.end()


class ToolCard(KeyboardFocusMixin, QAbstractButton):
    """One tool in the overview: icon tile, title, description, status or chevron."""

    HEIGHT = 76
    arrow_pressed = Signal(str)  # "left", "right", "up" or "down", for grid navigation

    def __init__(
        self,
        theme: ThemeManager,
        icon: str,
        available: bool,
        badge_text: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon = icon
        self._available = available
        self._badge_text = badge_text
        self._description = ""
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        if available:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(320)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        self._track_focus_in(event)
        super().focusInEvent(event)

    @property
    def available(self) -> bool:
        return self._available

    def set_description(self, text: str) -> None:
        self._description = text
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(420, self.HEIGHT)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            return
        directions = {
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
        }
        if key in directions:
            self.arrow_pressed.emit(directions[Qt.Key(key)])
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        t = self._theme.tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hovered = self.underMouse() and self._available
        p.setPen(QPen(QColor(t.card_border), 1))
        p.setBrush(QColor(t.card_hover if hovered or self.isDown() else t.card))
        p.drawRoundedRect(rect, 8, 8)
        if self.show_focus_ring():
            _focus_ring(p, QRectF(self.rect()), t, 8)

        cy = self.height() // 2
        tile = QRectF(16, cy - 20, 40, 40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.accent_subtle))
        p.drawRoundedRect(tile, 8, 8)
        icon = self._theme.accent_icon(self._icon)
        icon.paint(p, QRect(int(tile.x()) + 10, int(tile.y()) + 10, 20, 20))

        base = self.font()
        title_font = _font(base, 14, semibold=True)
        desc_font = _font(base, 12)
        badge_font = _font(base, 12)
        tm, dm, bm = QFontMetrics(title_font), QFontMetrics(desc_font), QFontMetrics(badge_font)

        right = self.width() - 16
        if self._available:
            chevron = self._theme.icon("arrow-up-right", secondary=True)
            chevron.paint(p, QRect(right - 16, cy - 8, 16, 16))
            right -= 16 + 12
        else:
            text = self._badge_text()
            width = bm.horizontalAdvance(text) + 16
            badge = QRectF(right - width, cy - 11, width, 22)
            p.setBrush(QColor(t.nav_selected))
            p.drawRoundedRect(badge, 11, 11)
            p.setFont(badge_font)
            p.setPen(QColor(t.text_secondary))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
            right = int(badge.left()) - 12

        left = 72
        width = max(0, right - left)
        block = tm.height() + 2 + dm.height()
        top = cy - block // 2
        p.setFont(title_font)
        p.setPen(QColor(t.text))
        p.drawText(
            QRect(left, top, width, tm.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tm.elidedText(self.text(), Qt.TextElideMode.ElideRight, width),
        )
        p.setFont(desc_font)
        p.setPen(QColor(t.text_secondary))
        p.drawText(
            QRect(left, top + tm.height() + 2, width, dm.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            dm.elidedText(self._description, Qt.TextElideMode.ElideRight, width),
        )
        p.end()


class Meter(QWidget):
    """Compact reading for the status line: label, thin bar, value."""

    BAR_WIDTH = 56

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._label = ""
        self._value = ""
        self._fraction: float | None = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_reading(self, label: str, value: str, fraction: float | None) -> None:
        self._label, self._value = label, value
        self._fraction = None if fraction is None else min(max(fraction, 0.0), 1.0)
        self.setAccessibleName(f"{label} {value}")
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(_font(self.font(), 12))
        width = fm.horizontalAdvance(self._label) + 8 + self.BAR_WIDTH + 8
        width += fm.horizontalAdvance(self._value)
        return QSize(width, 20)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        t = self._theme.tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = _font(self.font(), 12)
        fm = QFontMetrics(font)
        p.setFont(font)
        p.setPen(QColor(t.text_secondary))
        label_w = fm.horizontalAdvance(self._label)
        p.drawText(QRect(0, 0, label_w, self.height()), Qt.AlignmentFlag.AlignVCenter, self._label)
        x = label_w + 8
        bar = QRectF(x, self.height() / 2 - 2, self.BAR_WIDTH, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.nav_selected))
        p.drawRoundedRect(bar, 2, 2)
        if self._fraction:
            p.setBrush(QColor(t.accent))
            p.drawRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * self._fraction, 4), 2, 2)
        p.setPen(QColor(t.text))
        p.drawText(
            QRect(int(bar.right()) + 8, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignVCenter,
            self._value,
        )
        p.end()


class IconTile(QLabel):
    """Accent-tinted square with an icon, used in settings cards and tool headers."""

    def __init__(self, theme: ThemeManager, icon: str, size: int = 32) -> None:
        super().__init__()
        self._theme = theme
        self._icon = icon
        self._size = size
        self.setObjectName("IconTile")
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme.on_change(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        inner = 16 if self._size <= 32 else 20
        self.setPixmap(self._theme.accent_icon(self._icon).pixmap(inner, inner))


class SettingsCard(QFrame):
    """Row in the style of Windows 11 Settings: icon, title, description, controls."""

    def __init__(self, theme: ThemeManager, icon: str) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.title = QLabel()
        self.title.setProperty("textStyle", "cardTitle")
        self.description = QLabel()
        self.description.setProperty("textStyle", "caption")
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.title)
        text.addWidget(self.description)
        self.controls = QHBoxLayout()
        self.controls.setSpacing(8)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(16)
        row.addWidget(IconTile(theme, icon), 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(text, 1)
        row.addLayout(self.controls)
        self.setMinimumHeight(68)


class SearchField(QLineEdit):
    """Search box with a leading icon and a keyboard hint that hides while typing."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setClearButtonEnabled(True)
        self._action = self.addAction(
            theme.icon("search", secondary=True), QLineEdit.ActionPosition.LeadingPosition
        )
        self.hint = QLabel(self)
        self.hint.setObjectName("KeyHint")
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.textChanged.connect(lambda text: self.hint.setVisible(not text))
        theme.on_change(self._refresh_icon)

    def _refresh_icon(self) -> None:
        self._action.setIcon(self._theme.icon("search", secondary=True))

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.adjustSize()
        self._place_hint()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._place_hint()

    def _place_hint(self) -> None:
        self.hint.move(
            self.width() - self.hint.width() - 8, (self.height() - self.hint.height()) // 2
        )

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FontChange:
            self._place_hint()
        return super().event(event)
