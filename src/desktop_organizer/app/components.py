"""Composite widgets used by the tool windows: info bar, progress panel, folder
pickers, empty states and the per-tool settings form."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QModelIndex,
    QPoint,
    QProcess,
    QRectF,
    QSortFilterProxyModel,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QGuiApplication,
    QPainter,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.app.widgets import IconTile
from desktop_organizer.core import safety
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.tool_settings import SettingField, set_value, values

log = logging.getLogger(__name__)

SEVERITY_ICONS = {
    "info": "info",
    "success": "circle-check",
    "warning": "triangle-alert",
    "error": "circle-alert",
}


class InfoBar(QFrame):
    """Inline message with severity colors, as in Windows 11 apps."""

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self._theme = theme
        self.setObjectName("InfoBar")
        self.icon = QLabel()
        self.icon.setFixedSize(16, 16)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.action = QPushButton()
        self.action.hide()
        self.close_button = QPushButton()
        self.close_button.setIcon(theme.icon("x"))
        self.close_button.setFixedWidth(32)
        self.close_button.setAccessibleName(tr("common.close"))
        self.close_button.setFlat(True)
        self.close_button.clicked.connect(self.hide)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 8, 8)
        row.setSpacing(12)
        row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.text, 1)
        row.addWidget(self.action)
        row.addWidget(self.close_button)
        self._severity = "info"
        self._action_slot: Any = None
        theme.on_change(self._refresh_icon)
        self.hide()

    def _refresh_icon(self) -> None:
        t = self._theme.tokens
        color = {
            "info": t.accent,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
        }[self._severity]
        from desktop_organizer.app.theming import tinted_icon

        self.icon.setPixmap(tinted_icon(SEVERITY_ICONS[self._severity], color).pixmap(16, 16))
        self.close_button.setIcon(self._theme.icon("x"))

    def show_message(
        self, severity: str, text: str, action_text: str = "", action: Any = None
    ) -> None:
        self._severity = severity
        self.setProperty("severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)
        self.text.setText(text)
        self._refresh_icon()
        if self._action_slot is not None:
            self.action.clicked.disconnect(self._action_slot)
            self._action_slot = None
        if action_text and action is not None:
            self.action.setText(action_text)
            self._action_slot = action
            self.action.clicked.connect(action)
            self.action.show()
        else:
            self.action.hide()
        self.show()


class ProgressPanel(QWidget):
    """Progress bar, status text and cancel button for background work."""

    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.label = QLabel()
        self.label.setProperty("textStyle", "caption")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.cancel_button = QPushButton(tr("common.cancel"))
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        column = QVBoxLayout()
        column.setSpacing(6)
        column.addWidget(self.label)
        column.addWidget(self.bar)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addLayout(column, 1)
        row.addWidget(self.cancel_button)
        self.hide()

    def start(self, text: str) -> None:
        self.label.setText(text)
        self.bar.setRange(0, 0)
        self.cancel_button.setEnabled(True)
        self.show()

    def update_progress(self, done: int, total: int, message: str) -> None:
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(min(done, total))
        else:
            self.bar.setRange(0, 0)
        if message:
            self.label.setText(message)

    def finish(self) -> None:
        self.hide()


class EmptyState(QWidget):
    def __init__(self, theme: ThemeManager, icon: str) -> None:
        super().__init__()
        self.title = QLabel()
        self.title.setProperty("textStyle", "subtitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel()
        self.text.setProperty("textStyle", "secondary")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        column = QVBoxLayout(self)
        column.addStretch(1)
        tile = IconTile(theme, icon, size=48)
        column.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(8)
        column.addWidget(self.title)
        column.addWidget(self.text)
        column.addStretch(2)

    def set_texts(self, title: str, text: str) -> None:
        self.title.setText(title)
        self.text.setText(text)


def guard_folder(parent: QWidget | None, path: str) -> bool:
    """Refuse protected folders; ask before using a whole drive."""
    if not path:
        return False
    if not Path(path).is_dir():
        dialogs.warn(parent, tr("guard.title"), tr("guard.missing", path=path))
        return False
    verdict = safety.classify(path)
    if verdict is safety.PathVerdict.SYSTEM:
        dialogs.warn(parent, tr("guard.title"), tr("guard.system", path=path))
        return False
    if verdict is safety.PathVerdict.OTHER_USER:
        dialogs.warn(parent, tr("guard.title"), tr("guard.other_user", path=path))
        return False
    if verdict is safety.PathVerdict.DRIVE_ROOT:
        return dialogs.confirm(
            parent,
            tr("guard.drive_root.title"),
            tr("guard.drive_root.body", path=path),
            tr("guard.drive_root.confirm"),
            tr("common.cancel"),
        )
    return True


class FolderPicker(QWidget):
    """Read-only path field with a browse button; validates the chosen folder."""

    changed = Signal(str)

    def __init__(self, placeholder_key: str = "common.no_folder") -> None:
        super().__init__()
        self._placeholder_key = placeholder_key
        self.field = QLineEdit()
        self.field.setReadOnly(True)
        self.button = QPushButton()
        self.button.clicked.connect(self.browse)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.field, 1)
        row.addWidget(self.button)
        self.retranslate()

    def retranslate(self) -> None:
        self.field.setPlaceholderText(tr(self._placeholder_key))
        self.button.setText(tr("common.choose_folder"))

    def path(self) -> str:
        return self.field.text()

    def set_path(self, path: str) -> None:
        self.field.setText(path)
        self.changed.emit(path)

    def browse(self) -> None:
        start = self.path() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, tr("common.choose_folder"), start)
        if chosen and guard_folder(self, chosen):
            self.set_path(os.path.normpath(chosen))


class FolderList(QWidget):
    """Several folders with add and remove buttons (duplicate finder, backup)."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.list = QListWidget()
        self.list.setMinimumHeight(110)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.add_button = QPushButton()
        self.remove_button = QPushButton()
        self.add_button.clicked.connect(self.add)
        self.remove_button.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.add_button, 1)
        buttons.addWidget(self.remove_button)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(self.list, 1)
        column.addLayout(buttons)
        self.retranslate()

    def retranslate(self) -> None:
        self.add_button.setText(tr("common.add_folder"))
        self.remove_button.setText(tr("common.remove"))

    def folders(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def set_folders(self, folders: list[str]) -> None:
        self.list.clear()
        for folder in folders:
            self._append(folder)
        self.changed.emit()

    def _append(self, folder: str) -> None:
        self.list.addItem(folder)
        self.list.item(self.list.count() - 1).setToolTip(folder)

    def add(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("common.add_folder"), str(Path.home()))
        if not chosen or not guard_folder(self, chosen):
            return
        chosen = os.path.normpath(chosen)
        if chosen not in self.folders():
            self._append(chosen)
            self.changed.emit()

    def remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.changed.emit()


class ToolSettingsForm(QWidget):
    """Form generated from a tool's ``SettingField`` declaration. Saves on change."""

    def __init__(self, settings: Settings, tool_id: str, fields: tuple[SettingField, ...]) -> None:
        super().__init__()
        self._settings = settings
        self._tool_id = tool_id
        self._fields = fields
        self._editors: dict[str, QWidget] = {}
        form = QFormLayout(self)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        current = values(settings, tool_id, fields)
        for field in fields:
            editor = self._editor(field, current[field.key])
            self._editors[field.key] = editor
            label = QLabel(tr(field.label_key(tool_id)))
            label.setWordWrap(True)
            description_key = field.description_key(tool_id)
            description = tr(description_key)
            column = QVBoxLayout()
            column.setSpacing(2)
            column.addWidget(editor)
            if description != description_key:
                hint = QLabel(description)
                hint.setProperty("textStyle", "caption")
                hint.setWordWrap(True)
                column.addWidget(hint)
            form.addRow(label, column)

    def _editor(self, field: SettingField, value: Any) -> QWidget:
        tool = self._tool_id
        if field.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(value))
            box.setAccessibleName(tr(field.label_key(tool)))
            box.toggled.connect(lambda v, f=field: self._save(f, bool(v)))
            return box
        if field.kind == "int":
            spin = QSpinBox()
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setRange(field.minimum, field.maximum)
            spin.setValue(int(value))
            spin.setMinimumWidth(140)
            spin.setAccessibleName(tr(field.label_key(tool)))
            spin.valueChanged.connect(lambda v, f=field: self._save(f, int(v)))
            return spin
        if field.kind == "choice":
            combo = QComboBox()
            combo.setMinimumWidth(220)
            for choice in field.choices:
                combo.addItem(tr(field.choice_key(tool, choice)), choice)
            combo.setCurrentIndex(field.choices.index(value))
            combo.setAccessibleName(tr(field.label_key(tool)))
            combo.currentIndexChanged.connect(
                lambda _i, f=field, c=combo: self._save(f, c.currentData())
            )
            return combo
        line = QLineEdit(str(value))
        line.setMinimumWidth(260)
        line.setAccessibleName(tr(field.label_key(tool)))
        line.editingFinished.connect(lambda f=field, w=line: self._save(f, w.text()))
        return line

    def _save(self, field: SettingField, value: Any) -> None:
        set_value(self._settings, self._tool_id, field, value)

    def reset_to_defaults(self) -> None:
        for field in self._fields:
            editor = self._editors[field.key]
            if isinstance(editor, QCheckBox):
                editor.setChecked(bool(field.default))
            elif isinstance(editor, QSpinBox):
                editor.setValue(int(field.default))
            elif isinstance(editor, QComboBox):
                editor.setCurrentIndex(field.choices.index(field.default))
            elif isinstance(editor, QLineEdit):
                editor.setText(str(field.default))
                self._save(field, str(field.default))


class ToolSettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        tool_id: str,
        fields: tuple[SettingField, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("toolsettings.title", tool=tr(f"tool.{tool_id}.title")))
        self.setMinimumWidth(560)
        heading = QLabel(tr("toolsettings.title", tool=tr(f"tool.{tool_id}.title")))
        heading.setProperty("textStyle", "subtitle")
        hint = QLabel(tr("toolsettings.hint"))
        hint.setProperty("textStyle", "caption")
        hint.setWordWrap(True)
        self.form = ToolSettingsForm(settings, tool_id, fields)
        reset = QPushButton(tr("toolsettings.reset"))
        reset.clicked.connect(self.form.reset_to_defaults)
        close = QPushButton(tr("common.close"))
        close.setProperty("role", "primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addWidget(hint)
        layout.addSpacing(8)
        layout.addWidget(self.form)
        layout.addSpacing(8)
        layout.addLayout(buttons)


def show_in_explorer(path: str) -> None:
    """Open Explorer with the file selected (Windows) or open the containing folder."""
    target = Path(path)
    if sys.platform == "win32" and target.exists():
        QProcess.startDetached("explorer.exe", [f"/select,{target}"])
        return
    folder = target if target.is_dir() else target.parent
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def open_file(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def copy_text(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def save_file_dialog(parent: QWidget, title: str, suggested: str, filter_text: str) -> Path | None:
    target, _ = QFileDialog.getSaveFileName(parent, title, suggested, filter_text)
    return Path(target) if target else None


SORT_ROLE = Qt.ItemDataRole.UserRole + 10
DATA_ROLE = Qt.ItemDataRole.UserRole + 11


def item(
    text: str, sort: object = None, data: object = None, checkable: bool = False
) -> QStandardItem:
    cell = QStandardItem(text)
    cell.setEditable(False)
    cell.setData(text.casefold() if sort is None else sort, SORT_ROLE)
    if data is not None:
        cell.setData(data, DATA_ROLE)
    if checkable:
        cell.setCheckable(True)
        cell.setCheckState(Qt.CheckState.Checked)
    return cell


class Table(QTableView):
    """Sortable table on a QStandardItemModel, styled per the design system."""

    context_requested = Signal(int, QPoint)  # source row, global position

    def __init__(self, columns: int) -> None:
        super().__init__()
        self.source = QStandardItemModel(0, columns, self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.source)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context)

    def set_headers(self, labels: list[str]) -> None:
        self.source.setHorizontalHeaderLabels(labels)

    def clear_rows(self) -> None:
        self.source.removeRows(0, self.source.rowCount())

    def source_row(self, proxy_index: QModelIndex) -> int:
        return self.proxy.mapToSource(proxy_index).row()

    def selected_rows(self) -> list[int]:
        rows = {self.source_row(i) for i in self.selectionModel().selectedRows()}
        return sorted(rows)

    def checked_rows(self, column: int = 0) -> list[int]:
        return [
            r
            for r in range(self.source.rowCount())
            if self.source.item(r, column).checkState() == Qt.CheckState.Checked
        ]

    def set_all_checked(self, checked: bool, column: int = 0, visible_only: bool = True) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        if visible_only:
            for proxy_row in range(self.proxy.rowCount()):
                row = self.proxy.mapToSource(self.proxy.index(proxy_row, 0)).row()
                self.source.item(row, column).setCheckState(state)
        else:
            for row in range(self.source.rowCount()):
                self.source.item(row, column).setCheckState(state)

    def _context(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if index.isValid():
            self.context_requested.emit(self.source_row(index), self.viewport().mapToGlobal(pos))


class BarDelegate(QStyledItemDelegate):
    """Table cell that shows a share as a thin bar with the percentage next to it.

    The cell's DATA_ROLE holds a fraction between 0 and 1.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Any) -> None:
        super().paint(painter, option, index)
        fraction = index.data(DATA_ROLE)
        if not isinstance(fraction, float | int):
            return
        t = self._theme.tokens
        rect = option.rect.adjusted(8, 0, -8, 0)  # type: ignore[attr-defined]
        text = f"{fraction * 100:.0f} %"
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text_width = 44
        bar_width = max(0, rect.width() - text_width - 8)
        bar = QRectF(rect.x(), rect.center().y() - 3, bar_width, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.nav_selected))
        painter.drawRoundedRect(bar, 3, 3)
        painter.setBrush(QColor(t.accent))
        painter.drawRoundedRect(
            QRectF(bar.x(), bar.y(), bar.width() * min(1.0, float(fraction)), 6), 3, 3
        )
        painter.setPen(QColor(t.text_secondary))
        painter.drawText(
            QRectF(rect.right() - text_width, rect.y(), text_width, rect.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            text,
        )
        painter.restore()
