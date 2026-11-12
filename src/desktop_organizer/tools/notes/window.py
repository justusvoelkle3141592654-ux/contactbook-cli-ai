"""Notes window: list with search and tag filter on the left, editor on the right."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs
from desktop_organizer.app.components import EmptyState, save_file_dialog
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_datetime
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.notes import SETTINGS
from desktop_organizer.tools.notes.logic import (
    Note,
    all_tags,
    create,
    delete,
    get,
    parse_tags,
    search,
    set_pinned,
    to_markdown,
    update,
)

TOOL = "notes"
SAVE_DELAY_MS = 600


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class NotesWindow(ToolWindow):
    tool_id = TOOL
    icon = "notebook-pen"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.conn = context.database.connection
        self._current: int | None = None
        self._loading = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save_current)

        # List side -------------------------------------------------------------------------
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            context.theme.icon("search", secondary=True), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.textChanged.connect(lambda _t: self.refresh_list())
        self.tag_filter = QComboBox()
        self.tag_filter.currentIndexChanged.connect(lambda _i: self.refresh_list())
        self.new_button = QPushButton()
        self.new_button.setProperty("role", "primary")
        self.new_button.setIcon(context.theme.icon("plus"))
        self.new_button.clicked.connect(self.new_note)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.currentItemChanged.connect(self._select)
        self.count_label = QLabel()
        self.count_label.setProperty("textStyle", "caption")

        left = QFrame()
        left.setObjectName("Panel")
        left.setMinimumWidth(300)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.new_button)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.tag_filter)
        left_layout.addWidget(self.list, 1)
        left_layout.addWidget(self.count_label)

        # Editor side --------------------------------------------------------------------------
        self.title = QLineEdit()
        self.title.setProperty("noteTitle", True)
        title_font = QFont(self.title.font())
        title_font.setPixelSize(20)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(title_font)
        self.title.setMinimumHeight(44)
        self.title.textEdited.connect(lambda _t: self._changed())
        self.tags = QLineEdit()
        self.tags.textEdited.connect(lambda _t: self._changed())
        self.body = QPlainTextEdit()
        self.body.textChanged.connect(self._changed)
        self.pin_button = QPushButton()
        self.pin_button.setCheckable(True)
        self.pin_button.toggled.connect(self._toggle_pin)
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self.export_note)
        self.delete_button = QPushButton()
        self.delete_button.setProperty("role", "danger")
        self.delete_button.clicked.connect(self.delete_note)
        self.status = QLabel()
        self.status.setProperty("textStyle", "caption")
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.status, 1)
        actions.addWidget(self.pin_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.delete_button)

        self.editor = QWidget()
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)
        editor_layout.addWidget(self.title)
        editor_layout.addWidget(self.tags)
        editor_layout.addWidget(self.body, 1)
        editor_layout.addLayout(actions)
        self.empty = EmptyState(context.theme, "notebook-pen")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.editor, 1)
        right_layout.addWidget(self.empty, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([320, 780])
        splitter.setChildrenCollapsible(False)
        self.content.addWidget(splitter, 1)

        from desktop_organizer.app import dialogs as d

        d.shortcut("Ctrl+N", self, self.new_note)
        d.shortcut("Ctrl+F", self, self._focus_search)
        d.shortcut("Ctrl+S", self, self.save_current)
        self._apply_editor_font()
        self.retranslate()

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    # -- texts and settings ----------------------------------------------------------------

    def retranslate(self) -> None:
        self.search.setPlaceholderText(t("search"))
        self.new_button.setText(t("new"))
        self.title.setPlaceholderText(t("field.title"))
        self.tags.setPlaceholderText(t("field.tags"))
        self.body.setPlaceholderText(t("field.body"))
        self.pin_button.setText(t("unpin") if self.pin_button.isChecked() else t("pin"))
        self.export_button.setText(t("export"))
        self.delete_button.setText(tr("common.delete"))
        self.empty.set_texts(t("empty.title"), t("empty.text"))
        self.refresh_tags()
        self.refresh_list()

    def _apply_editor_font(self) -> None:
        font = (
            QFont("Cascadia Mono, Consolas, monospace")
            if self.option("monospace")
            else QFont(self.font())
        )
        font.setPixelSize(self.option("editor_font_size"))
        self.body.setFont(font)
        self.body.setStyleSheet(
            f"QPlainTextEdit {{ font-size: {self.option('editor_font_size')}px;"
            + (
                ' font-family: "Cascadia Mono", "Consolas", monospace;'
                if self.option("monospace")
                else ""
            )
            + " }"
        )

    def settings_changed(self) -> None:
        self._apply_editor_font()
        self.refresh_list()

    # -- list ------------------------------------------------------------------------------

    def refresh_tags(self) -> None:
        current = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem(t("all_tags"), "")
        for tag in all_tags(self.conn):
            self.tag_filter.addItem(f"#{tag}", tag)
        index = self.tag_filter.findData(current) if current else 0
        self.tag_filter.setCurrentIndex(max(index, 0))
        self.tag_filter.blockSignals(False)

    def refresh_list(self, select: int | None = None) -> None:
        lang = self.context.translator.language
        keep = select if select is not None else self._current
        notes = search(
            self.conn, self.search.text(), self.tag_filter.currentData() or "", self.option("sort")
        )
        self.list.blockSignals(True)
        self.list.clear()
        selected_item = None
        for note in notes:
            preview = " ".join(note.body.split())[:90]
            title = note.display_title or t("untitled")
            marker = "● " if note.pinned else ""
            when = format_datetime(note.updated, lang)
            text = f"{marker}{title}\n{when}  ·  {preview}"
            entry = QListWidgetItem(text)
            entry.setData(Qt.ItemDataRole.UserRole, note.id)
            entry.setToolTip(title)
            self.list.addItem(entry)
            if note.id == keep:
                selected_item = entry
        self.list.blockSignals(False)
        total = self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        self.count_label.setText(t("count", shown=len(notes), total=total))
        if selected_item is not None:
            self.list.setCurrentItem(selected_item)
        elif self._current is not None and get(self.conn, self._current) is None:
            self._show(None)
        self._show_editor(self._current is not None)

    def _select(self, current: QListWidgetItem | None, _previous: object) -> None:
        self.save_current()
        if current is None:
            return
        self._show(get(self.conn, int(current.data(Qt.ItemDataRole.UserRole))))

    def _show(self, note: Note | None) -> None:
        self._loading = True
        self._current = note.id if note else None
        self.title.setText(note.title if note else "")
        self.tags.setText(", ".join(note.tags) if note else "")
        self.body.setPlainText(note.body if note else "")
        self.pin_button.setChecked(bool(note and note.pinned))
        self.pin_button.setText(t("unpin") if note and note.pinned else t("pin"))
        if note:
            self.status.setText(
                t("updated", time=format_datetime(note.updated, self.context.translator.language))
            )
        self._loading = False
        self._show_editor(note is not None)

    def _show_editor(self, visible: bool) -> None:
        self.editor.setVisible(visible)
        self.empty.setVisible(not visible)

    # -- editing ---------------------------------------------------------------------------

    def _changed(self) -> None:
        if self._loading or self._current is None:
            return
        self.status.setText(t("saving"))
        self._save_timer.start()

    def save_current(self) -> None:
        if self._current is None or self._loading:
            return
        self._save_timer.stop()
        note = get(self.conn, self._current)
        if note is None:
            return
        tags = parse_tags(self.tags.text())
        if (note.title, note.body, note.tags) == (self.title.text(), self.body.toPlainText(), tags):
            return
        update(self.conn, self._current, self.title.text(), self.body.toPlainText(), tags)
        self.status.setText(t("saved"))
        self.refresh_tags()
        self.refresh_list()

    def new_note(self) -> None:
        self.save_current()
        self.search.clear()
        self.tag_filter.setCurrentIndex(0)
        note_id = create(self.conn)
        self.refresh_list(select=note_id)
        self.title.setFocus()

    def _toggle_pin(self, pinned: bool) -> None:
        if self._loading or self._current is None:
            return
        set_pinned(self.conn, self._current, pinned)
        self.pin_button.setText(t("unpin") if pinned else t("pin"))
        self.refresh_list()

    def delete_note(self) -> None:
        if self._current is None:
            return
        note = get(self.conn, self._current)
        name = (note.display_title if note else "") or t("untitled")
        if self.option("confirm_delete") and not dialogs.confirm_destructive(
            self,
            t("delete.title", name=name),
            t("delete.body"),
            tr("common.delete"),
            tr("common.cancel"),
        ):
            return
        delete(self.conn, self._current)
        self._current = None
        self._show(None)
        self.refresh_tags()
        self.refresh_list()

    def export_note(self) -> None:
        if self._current is None:
            return
        self.save_current()
        note = get(self.conn, self._current)
        if note is None:
            return
        name = "".join(c for c in (note.display_title or "Notiz") if c not in '\\/:*?"<>|')[:60]
        target = save_file_dialog(
            self,
            t("export"),
            str(Path.home() / f"{name or date.today().isoformat()}.md"),
            t("export.filter"),
        )
        if target is None:
            return
        target.write_text(to_markdown(note), encoding="utf-8")
        self.info.show_message("success", tr("common.saved_to", path=str(target)))

    def handle_message(self, text: str) -> None:
        if text == "new":
            self.new_note()
        elif text.startswith("open:"):
            try:
                note_id = int(text.removeprefix("open:"))
            except ValueError:
                return
            self.search.clear()
            self.refresh_list(select=note_id)

    def closeEvent(self, event: object) -> None:  # noqa: N802
        self.save_current()
        super().closeEvent(event)  # type: ignore[arg-type]

    def screenshot_prepare(self) -> None:
        if self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0:
            create(
                self.conn,
                "Einkauf Wochenende",
                "Milch, Brot, Kaffee\nFür Sonntag: Kuchen bestellen",
                ["privat"],
            )
            create(
                self.conn,
                "Projekt Q4",
                "Ziele:\n- Angebot bis Freitag\n- Termin mit Team festlegen",
                ["arbeit", "projekt"],
            )
            create(
                self.conn,
                "Ideen",
                "Desktop aufräumen\nBackup auf externe Platte einrichten",
                ["privat"],
            )
        self.refresh_tags()
        self.refresh_list()
        if self.list.count():
            self.list.setCurrentRow(1)
