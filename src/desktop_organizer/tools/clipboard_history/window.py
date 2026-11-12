"""Clipboard history window: recording switch, searchable list and preview."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import EmptyState
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.app.widgets import IconTile, ToggleSwitch
from desktop_organizer.core import dpapi
from desktop_organizer.core.formatting import format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.clipboard_history import SETTINGS
from desktop_organizer.tools.clipboard_history.logic import (
    ClipEntry,
    add,
    clear,
    delete,
    entries,
    set_pinned,
    state,
)

TOOL = "clipboard_history"
ID_ROLE = Qt.ItemDataRole.UserRole


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class ClipboardWindow(ToolWindow):
    tool_id = TOOL
    icon = "clipboard-list"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.conn = context.database.connection
        self._state: tuple[int, float] | None = None
        self._entries: dict[int, ClipEntry] = {}

        # Recording card ------------------------------------------------------------------------
        self.status_title = QLabel()
        self.status_title.setProperty("textStyle", "cardTitle")
        self.status_text = QLabel()
        self.status_text.setProperty("textStyle", "caption")
        self.status_text.setWordWrap(True)
        self.switch = ToggleSwitch(context.theme)
        self.switch.setChecked(bool(context.settings.get("clipboard_monitoring")))
        self.switch.toggled.connect(
            lambda on: context.settings.set("clipboard_monitoring", bool(on))
        )
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(16)
        self.status_tile = IconTile(context.theme, "history")
        card_layout.addWidget(self.status_tile)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(self.status_title)
        texts.addWidget(self.status_text)
        card_layout.addLayout(texts, 1)
        card_layout.addWidget(self.switch)
        self.content.addWidget(card)

        # List and preview ------------------------------------------------------------------------
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            context.theme.icon("search", secondary=True), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.textChanged.connect(lambda _t: self.refresh(force=True))
        self.list = QListWidget()
        self.list.setWordWrap(False)
        self.list.currentItemChanged.connect(lambda *_: self._show_selected())
        self.list.itemActivated.connect(lambda _i: self.copy_selected())
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.empty = EmptyState(context.theme, "clipboard-list")
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.list, 1)
        left_layout.addWidget(self.empty, 1)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.meta = QLabel()
        self.meta.setProperty("textStyle", "caption")
        self.copy_button = QPushButton()
        self.copy_button.setProperty("role", "primary")
        self.copy_button.clicked.connect(self.copy_selected)
        self.pin_button = QPushButton()
        self.pin_button.clicked.connect(self.toggle_pin)
        self.delete_button = QPushButton()
        self.delete_button.clicked.connect(self.delete_selected)
        actions = QHBoxLayout()
        actions.addWidget(self.meta, 1)
        actions.addWidget(self.delete_button)
        actions.addWidget(self.pin_button)
        actions.addWidget(self.copy_button)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.preview, 1)
        right_layout.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([460, 600])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        self.privacy = QLabel()
        self.privacy.setProperty("textStyle", "caption")
        self.privacy.setWordWrap(True)
        self.clear_button = QPushButton()
        self.clear_button.setProperty("role", "danger")
        self.clear_button.clicked.connect(self.clear_history)
        self.footer.addWidget(self.privacy, 1)
        self.footer.addWidget(self.clear_button)

        dialogs.shortcut("Delete", self, self.delete_selected)
        dialogs.shortcut("Ctrl+F", self, lambda: self.search.setFocus())
        self._poll = QTimer(self)
        self._poll.timeout.connect(self.refresh)
        self._poll.start(1500)
        self.retranslate()

    def retranslate(self) -> None:
        self.switch.set_labels(tr("common.off"), tr("common.on"))
        self.search.setPlaceholderText(t("search"))
        self.copy_button.setText(tr("common.copy"))
        self.delete_button.setText(tr("common.delete"))
        self.clear_button.setText(t("clear"))
        self.empty.set_texts(t("empty.title"), t("empty.text"))
        self.privacy.setText(t("privacy.encrypted") if dpapi.AVAILABLE else t("privacy.plain"))
        self._update_status()
        self.refresh(force=True)

    def settings_changed(self) -> None:
        self.refresh(force=True)

    def _settings_changed(self, key: str, value: object) -> None:  # type: ignore[override]
        super()._settings_changed(key, value)
        if key == "clipboard_monitoring":
            self.switch.blockSignals(True)
            self.switch.setChecked(bool(value))
            self.switch.blockSignals(False)
            self._update_status()

    def _update_status(self) -> None:
        on = bool(self.context.settings.get("clipboard_monitoring"))
        self.status_title.setText(t("status.on") if on else t("status.off"))
        self.status_text.setText(t("status.on.text") if on else t("status.off.text"))

    # -- list --------------------------------------------------------------------------------

    def refresh(self, force: bool = False) -> None:
        current_state = state(self.conn)
        if not force and current_state == self._state:
            return
        self._state = current_state
        lang = self.context.translator.language
        selected = self._selected_id()
        found = entries(self.conn, self.search.text())
        self._entries = {e.id: e for e in found}
        self.list.blockSignals(True)
        self.list.clear()
        for entry in found:
            first = " ".join(entry.text.split())[:120]
            label = f"{'● ' if entry.pinned else ''}{first}\n{format_datetime(entry.created, lang)}"
            if entry.source:
                label += f"  ·  {entry.source}"
            row = QListWidgetItem(label)
            row.setData(ID_ROLE, entry.id)
            self.list.addItem(row)
            if entry.id == selected:
                self.list.setCurrentItem(row)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        has = bool(found)
        self.list.setVisible(has)
        self.empty.setVisible(not has)
        self._show_selected()

    def _selected_id(self) -> int | None:
        current = self.list.currentItem()
        return int(current.data(ID_ROLE)) if current is not None else None

    def _selected(self) -> ClipEntry | None:
        entry_id = self._selected_id()
        return self._entries.get(entry_id) if entry_id is not None else None

    def _show_selected(self) -> None:
        entry = self._selected()
        for button in (self.copy_button, self.pin_button, self.delete_button):
            button.setEnabled(entry is not None)
        if entry is None:
            self.preview.clear()
            self.meta.clear()
            self.pin_button.setText(t("pin"))
            return
        self.preview.setPlainText(entry.text)
        self.meta.setText(t("meta", chars=len(entry.text), lines=entry.text.count("\n") + 1))
        self.pin_button.setText(t("unpin") if entry.pinned else t("pin"))

    # -- actions -------------------------------------------------------------------------------

    def copy_selected(self) -> None:
        entry = self._selected()
        clipboard = QGuiApplication.clipboard()
        if entry is None or clipboard is None:
            return
        clipboard.setText(entry.text)
        add(self.conn, entry.text, self.option("max_entries"))  # moves it to the top
        self.info.show_message("success", t("copied"))
        if self.option("close_after_copy"):
            self.close()
        else:
            self.refresh(force=True)

    def toggle_pin(self) -> None:
        entry = self._selected()
        if entry is not None:
            set_pinned(self.conn, entry.id, not entry.pinned)
            self.refresh(force=True)

    def delete_selected(self) -> None:
        entry = self._selected()
        if entry is not None:
            delete(self.conn, entry.id)
            self.refresh(force=True)

    def clear_history(self) -> None:
        if not dialogs.confirm_destructive(
            self, t("clear.title"), t("clear.body"), t("clear.ok"), tr("common.cancel")
        ):
            return
        removed = clear(self.conn, keep_pinned=True)
        self.info.show_message("success", t("cleared", count=removed))
        self.refresh(force=True)

    def _menu(self, pos: QPoint) -> None:
        if self.list.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction(tr("common.copy"), self.copy_selected)
        menu.addAction(self.pin_button.text(), self.toggle_pin)
        menu.addAction(tr("common.delete"), self.delete_selected)
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def handle_message(self, _text: str) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def screenshot_prepare(self) -> None:
        if not entries(self.conn):
            for text, source in (
                ("Rechnungsnummer 2026-1187", "Outlook.exe"),
                ("https://www.example.org/handbuch/kapitel-3", "msedge.exe"),
                ("Treffen am Donnerstag um 14:30 im Raum 2.14", "Teams.exe"),
                (
                    "SELECT name, size FROM files WHERE size > 1048576 ORDER BY size DESC;",
                    "Code.exe",
                ),
            ):
                add(self.conn, text, source=source)
        self.refresh(force=True)
