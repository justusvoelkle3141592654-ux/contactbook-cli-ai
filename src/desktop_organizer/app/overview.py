"""Overview window: search, the list of tools, and a slim status line."""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.settings_dialog import SettingsDialog
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core import system_info
from desktop_organizer.core.formatting import format_bytes, format_percent
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.registry import CATEGORY_ORDER, ToolSpec

log = logging.getLogger(__name__)

KIND_ROLE = Qt.ItemDataRole.UserRole + 1
SPEC_ROLE = Qt.ItemDataRole.UserRole + 2
DESC_ROLE = Qt.ItemDataRole.UserRole + 3

GROUP_ROW_HEIGHT = 36
TOOL_ROW_HEIGHT = 56
STATUS_INTERVAL_MS = 2000

AnyIndex = QModelIndex | QPersistentModelIndex


def matches(spec: ToolSpec, query: str) -> bool:
    if not query:
        return True
    needle = query.casefold()
    return needle in tr(spec.title_key).casefold() or needle in tr(spec.description_key).casefold()


class ToolDelegate(QStyledItemDelegate):
    def __init__(self, context: AppContext, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._context = context

    def sizeHint(self, option: QStyleOptionViewItem, index: AnyIndex) -> QSize:  # noqa: N802
        height = GROUP_ROW_HEIGHT if index.data(KIND_ROLE) == "group" else TOOL_ROW_HEIGHT
        return QSize(option.rect.width(), height)  # type: ignore[attr-defined]

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: AnyIndex) -> None:
        t = self._context.theme.tokens
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRect(option.rect)  # type: ignore[attr-defined]
        base = QFont(option.font)  # type: ignore[attr-defined]

        if index.data(KIND_ROLE) == "group":
            font = QFont(base)
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(t.text_secondary))
            text_rect = rect.adjusted(16, 0, -16, -4)
            painter.drawText(
                text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, index.data()
            )
            painter.restore()
            return

        spec: ToolSpec = index.data(SPEC_ROLE)
        state = option.state  # type: ignore[attr-defined]
        row = rect.adjusted(4, 2, -4, -2)
        selected = bool(state & QStyle.StateFlag.State_Selected)
        hovered = bool(state & QStyle.StateFlag.State_MouseOver)
        focused = bool(state & QStyle.StateFlag.State_HasFocus)

        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.selection))
            painter.drawRoundedRect(row, 4, 4)
            painter.setBrush(QColor(t.accent))
            marker = QRect(row.left(), row.center().y() - 8, 3, 16)
            painter.drawRoundedRect(marker, 1.5, 1.5)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.surface_alt))
            painter.drawRoundedRect(row, 4, 4)
        if focused and selected and option.widget is not None and option.widget.hasFocus():  # type: ignore[attr-defined]
            pen = painter.pen()
            pen.setColor(QColor(t.accent))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(row.adjusted(1, 1, -1, -1), 4, 4)

        icon = self._context.theme.icon(spec.icon, secondary=not spec.available)
        icon_rect = QRect(row.left() + 16, row.center().y() - 10, 20, 20)
        icon.paint(painter, icon_rect)

        right_reserved = 0
        if not spec.available:
            status_font = QFont(base)
            status_font.setPixelSize(12)
            painter.setFont(status_font)
            painter.setPen(QColor(t.text_secondary))
            status = tr("overview.not_available")
            width = QFontMetrics(status_font).horizontalAdvance(status)
            right_reserved = width + 24
            painter.drawText(
                QRect(row.right() - width - 16, row.top(), width, row.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                status,
            )
        else:
            chevron = self._context.theme.icon("chevron-right", secondary=True)
            chevron.paint(painter, QRect(row.right() - 32, row.center().y() - 8, 16, 16))
            right_reserved = 40

        text_left = icon_rect.right() + 16
        text_width = row.right() - right_reserved - text_left
        title_font = QFont(base)
        title_font.setPixelSize(14)
        title_font.setWeight(QFont.Weight.DemiBold)
        desc_font = QFont(base)
        desc_font.setPixelSize(12)
        title_metrics = QFontMetrics(title_font)
        desc_metrics = QFontMetrics(desc_font)
        block = title_metrics.height() + 2 + desc_metrics.height()
        top = row.center().y() - block // 2

        painter.setFont(title_font)
        painter.setPen(QColor(t.text))
        painter.drawText(
            QRect(text_left, top, text_width, title_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title_metrics.elidedText(index.data(), Qt.TextElideMode.ElideRight, text_width),
        )
        painter.setFont(desc_font)
        painter.setPen(QColor(t.text_secondary))
        painter.drawText(
            QRect(text_left, top + title_metrics.height() + 2, text_width, desc_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            desc_metrics.elidedText(index.data(DESC_ROLE), Qt.TextElideMode.ElideRight, text_width),
        )
        painter.restore()


class OverviewWindow(QMainWindow):
    def __init__(self, context: AppContext, tools: list[ToolSpec]) -> None:
        super().__init__()
        self._context = context
        self._tools = tools
        self._open_windows: dict[str, ToolWindow] = {}
        self._settings_dialog: SettingsDialog | None = None

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self._search_action = self.search.addAction(
            context.theme.icon("search", secondary=True), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.textChanged.connect(self._rebuild)
        self.search.installEventFilter(self)

        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_settings)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.search, 1)
        header.addWidget(self.settings_button)

        self.model = QStandardItemModel(self)
        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setItemDelegate(ToolDelegate(context, self.list))
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(False)
        self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.activated.connect(self._activate)
        self.list.clicked.connect(self._activate)

        self.empty = QLabel()
        self.empty.setProperty("textStyle", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty.setWordWrap(True)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.empty)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)
        body_layout.addLayout(header)
        body_layout.addWidget(self.stack, 1)

        self.status_label = QLabel()
        self.status_label.setProperty("textStyle", "caption")
        status = QWidget()
        status.setObjectName("StatusLine")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(16, 6, 16, 6)
        status_layout.addWidget(self.status_label)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(body, 1)
        layout.addWidget(status)
        self.setCentralWidget(central)

        dialogs.shortcut(QKeySequence.StandardKey.Find, self, self._focus_search)
        dialogs.shortcut("Ctrl+,", self, self.open_settings)

        system_info.prime()
        self._timer = QTimer(self)
        self._timer.setInterval(STATUS_INTERVAL_MS)
        self._timer.timeout.connect(self._update_status)
        self._timer.start()

        context.translator.subscribe(self.retranslate)
        context.theme.on_change(self._on_theme_change)
        self._restore_geometry()
        self._on_theme_change()
        self.retranslate()

    # -- texts -----------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.setWindowTitle(tr("app.name"))
        self.search.setPlaceholderText(tr("overview.search.placeholder"))
        self.search.setAccessibleName(tr("overview.search.placeholder"))
        self.settings_button.setText(tr("overview.settings"))
        self.settings_button.setToolTip(f"{tr('overview.settings')} (Ctrl+,)")
        self.list.setAccessibleName(tr("overview.list.accessible"))
        self._rebuild()
        self._update_status()

    def _on_theme_change(self) -> None:
        self.settings_button.setIcon(self._context.theme.icon("settings"))
        self._search_action.setIcon(self._context.theme.icon("search", secondary=True))
        self.list.viewport().update()

    # -- list ------------------------------------------------------------------------------

    def _rebuild(self) -> None:
        query = self.search.text().strip()
        current = self._current_spec()
        self.model.clear()
        first_tool: QModelIndex | None = None
        for category in CATEGORY_ORDER:
            specs = [s for s in self._tools if s.category is category and matches(s, query)]
            if not specs:
                continue
            group = QStandardItem(tr(f"category.{category.value}"))
            group.setData("group", KIND_ROLE)
            group.setFlags(Qt.ItemFlag.NoItemFlags)
            group.setData(tr(f"category.{category.value}"), Qt.ItemDataRole.AccessibleTextRole)
            self.model.appendRow(group)
            for spec in specs:
                item = QStandardItem(tr(spec.title_key))
                item.setData("tool", KIND_ROLE)
                item.setData(spec, SPEC_ROLE)
                item.setData(tr(spec.description_key), DESC_ROLE)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                description = tr(spec.description_key)
                if not spec.available:
                    description = f"{description} {tr('overview.not_available')}."
                    item.setToolTip(tr("overview.not_available.tooltip"))
                item.setData(description, Qt.ItemDataRole.AccessibleDescriptionRole)
                self.model.appendRow(item)
                if first_tool is None:
                    first_tool = item.index()
                if current is not None and spec.id == current.id:
                    self.list.setCurrentIndex(item.index())
        if first_tool is None:
            self.empty.setText(tr("overview.empty", query=query))
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.list)
            if not self.list.currentIndex().isValid():
                self.list.setCurrentIndex(first_tool)

    def _current_spec(self) -> ToolSpec | None:
        index = self.list.currentIndex() if hasattr(self, "list") else QModelIndex()
        spec = index.data(SPEC_ROLE) if index.isValid() else None
        return spec if isinstance(spec, ToolSpec) else None

    def visible_tool_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self.model.rowCount()):
            spec = self.model.item(row).data(SPEC_ROLE)
            if isinstance(spec, ToolSpec):
                ids.append(spec.id)
        return ids

    def _activate(self, index: QModelIndex) -> None:
        spec = index.data(SPEC_ROLE)
        if isinstance(spec, ToolSpec):
            self.open_tool(spec)

    def open_tool(self, spec: ToolSpec) -> None:
        if spec.factory is None:
            return
        window = self._open_windows.get(spec.id)
        if window is None:
            window = spec.factory(self._context)
            window.destroyed.connect(lambda _=None, i=spec.id: self._open_windows.pop(i, None))
            self._open_windows[spec.id] = window
        window.show()
        window.raise_()
        window.activateWindow()

    # -- search keyboard handling ------------------------------------------------------

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            watched is self.search
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            key = event.key()
            if key == Qt.Key.Key_Down and self.stack.currentWidget() is self.list:
                self.list.setFocus()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                spec = self._current_spec()
                if spec is not None:
                    self.open_tool(spec)
                return True
            if key == Qt.Key.Key_Escape and self.search.text():
                self.search.clear()
                return True
        return super().eventFilter(watched, event)

    # -- status line ---------------------------------------------------------------------

    def _update_status(self) -> None:
        lang = self._context.translator.language
        try:
            snap = system_info.snapshot()
        except Exception:
            log.exception("Reading system information failed")
            self.status_label.clear()
            return
        parts = [
            tr("status.cpu", value=format_percent(snap.cpu_percent, lang)),
            tr(
                "status.memory",
                used=format_bytes(snap.memory_used, lang),
                total=format_bytes(snap.memory_total, lang),
            ),
        ]
        if snap.battery_percent is not None:
            key = "status.battery.charging" if snap.battery_charging else "status.battery"
            parts.append(tr(key, value=format_percent(snap.battery_percent, lang)))
        self.status_label.setText("  ·  ".join(parts))

    # -- settings and window state -------------------------------------------------------

    def open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self._context, self)
            self._settings_dialog.finished.connect(self._settings_closed)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _settings_closed(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.deleteLater()
            self._settings_dialog = None

    def _restore_geometry(self) -> None:
        saved = self._context.settings.get("window_geometry").get("overview")
        if isinstance(saved, str):
            self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
        else:
            self.resize(760, 640)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        geometry = dict(self._context.settings.get("window_geometry"))
        geometry["overview"] = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self._context.settings.set("window_geometry", geometry)
        self._timer.stop()
        super().closeEvent(event)
        QApplication.quit()
