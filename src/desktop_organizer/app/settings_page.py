"""Settings page in the main window, built from Windows 11 style settings cards."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer import __version__
from desktop_organizer.app import dialogs
from desktop_organizer.app.components import ToolSettingsDialog
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.widgets import SettingsCard, ToggleSwitch
from desktop_organizer.core import autostart, data_management, logging_setup
from desktop_organizer.core.i18n import resolve_language, tr
from desktop_organizer.core.settings import LANGUAGES, THEMES
from desktop_organizer.core.tool_settings import SettingField

HOTKEYS = ("hotkey_quick_note", "hotkey_clipboard", "hotkey_password")

log = logging.getLogger(__name__)


def _section_label() -> QLabel:
    label = QLabel()
    label.setProperty("textStyle", "section")
    return label


class SettingsPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("PageBody")
        self._context = context
        self.services: object = None
        theme = context.theme

        self.title = QLabel()
        self.title.setProperty("textStyle", "display")
        self.subtitle = QLabel()
        self.subtitle.setProperty("textStyle", "secondary")

        # Appearance
        self.appearance_label = _section_label()
        self.language_card = SettingsCard(theme, "languages")
        self.language = QComboBox()
        self.language.setMinimumWidth(220)
        self.language_card.controls.addWidget(self.language)
        self.theme_card = SettingsCard(theme, "sun-moon")
        self.theme = QComboBox()
        self.theme.setMinimumWidth(220)
        self.theme_card.controls.addWidget(self.theme)

        # Data
        self.data_label = _section_label()
        self.location_card = SettingsCard(theme, "database")
        self.open_data = QPushButton()
        self.location_card.controls.addWidget(self.open_data)
        self.logs_card = SettingsCard(theme, "file-text")
        self.open_logs = QPushButton()
        self.logs_card.controls.addWidget(self.open_logs)
        self.export_card = SettingsCard(theme, "archive")
        self.export_button = QPushButton()
        self.export_card.controls.addWidget(self.export_button)
        self.delete_card = SettingsCard(theme, "trash-2")
        self.delete_button = QPushButton()
        self.delete_button.setProperty("role", "danger")
        self.delete_card.controls.addWidget(self.delete_button)

        # System
        self.system_label = _section_label()
        self.background_card = SettingsCard(theme, "layout-grid")
        self.background_switch = ToggleSwitch(theme)
        self.background_card.controls.addWidget(self.background_switch)
        self.autostart_card = SettingsCard(theme, "play")
        self.autostart_switch = ToggleSwitch(theme)
        self.autostart_card.controls.addWidget(self.autostart_switch)
        self.clipboard_card = SettingsCard(theme, "clipboard-list")
        self.clipboard_switch = ToggleSwitch(theme)
        self.clipboard_card.controls.addWidget(self.clipboard_switch)
        self.hotkeys_card = SettingsCard(theme, "sparkles")
        self.hotkeys_switch = ToggleSwitch(theme)
        self.hotkeys_card.controls.addWidget(self.hotkeys_switch)
        self.hotkey_editors: dict[str, QKeySequenceEdit] = {}
        self.hotkey_labels: dict[str, QLabel] = {}
        self.hotkey_errors: dict[str, QLabel] = {}
        hotkey_grid = QGridLayout()
        hotkey_grid.setContentsMargins(64, 0, 16, 12)
        hotkey_grid.setHorizontalSpacing(16)
        hotkey_grid.setVerticalSpacing(8)
        for row, key in enumerate(HOTKEYS):
            label = QLabel()
            editor = QKeySequenceEdit(QKeySequence(str(context.settings.get(key))))
            editor.setMaximumSequenceLength(1)
            editor.setMinimumWidth(200)
            editor.editingFinished.connect(lambda k=key, e=editor: self._hotkey_changed(k, e))
            error = QLabel()
            error.setProperty("textStyle", "error")
            hotkey_grid.addWidget(label, row, 0)
            hotkey_grid.addWidget(editor, row, 1)
            hotkey_grid.addWidget(error, row, 2)
            self.hotkey_labels[key] = label
            self.hotkey_editors[key] = editor
            self.hotkey_errors[key] = error
        hotkey_grid.setColumnStretch(2, 1)
        self.hotkeys_box = QFrame()
        self.hotkeys_box.setObjectName("Card")
        box_layout = QVBoxLayout(self.hotkeys_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)
        self.hotkeys_card.setObjectName("")
        box_layout.addWidget(self.hotkeys_card)
        box_layout.addLayout(hotkey_grid)
        for switch, key in (
            (self.background_switch, "run_in_background"),
            (self.autostart_switch, "autostart"),
            (self.clipboard_switch, "clipboard_monitoring"),
            (self.hotkeys_switch, "hotkeys_enabled"),
        ):
            switch.setChecked(bool(context.settings.get(key)))
            switch.toggled.connect(lambda on, k=key: self._switch_changed(k, on))
        self.autostart_switch.setEnabled(autostart.supported())
        context.settings.subscribe(self._external_change)

        # Tools
        self.tools_label = _section_label()
        self.tool_cards: list[tuple[SettingsCard, QPushButton, str]] = []
        for spec in context.tools:
            if not spec.settings:
                continue
            card = SettingsCard(theme, spec.icon)
            button = QPushButton()
            button.clicked.connect(
                lambda _=False, s=spec: self._open_tool_settings(s.id, s.settings)
            )
            card.controls.addWidget(button)
            self.tool_cards.append((card, button, spec.id))

        # About
        self.about_label = _section_label()
        self.about_card = SettingsCard(theme, "info")

        body = QWidget()
        body.setObjectName("PageBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        for index, block in enumerate(
            (
                (self.appearance_label, self.language_card, self.theme_card),
                (
                    self.data_label,
                    self.location_card,
                    self.logs_card,
                    self.export_card,
                    self.delete_card,
                ),
                (
                    self.system_label,
                    self.background_card,
                    self.autostart_card,
                    self.clipboard_card,
                    self.hotkeys_box,
                ),
                (self.tools_label, *[card for card, _b, _i in self.tool_cards]),
                (self.about_label, self.about_card),
            )
        ):
            if index:
                column.addSpacing(20)
            heading, *rows = block
            column.addWidget(heading)
            column.addSpacing(4)
            for row_widget in rows:
                column.addWidget(row_widget)
        column.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(20)
        layout.addWidget(scroll, 1)

        self.language.currentIndexChanged.connect(self._language_changed)
        self.theme.currentIndexChanged.connect(self._theme_changed)
        self.open_data.clicked.connect(lambda: dialogs.open_folder(self, context.paths.data_dir))
        self.open_logs.clicked.connect(lambda: dialogs.open_folder(self, context.paths.log_dir))
        self.export_button.clicked.connect(self.export_data)
        self.delete_button.clicked.connect(self.delete_all_data)

        context.translator.subscribe(self.retranslate)
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(tr("settings.title"))
        self.subtitle.setText(tr("settings.subtitle"))
        self.appearance_label.setText(tr("settings.section.appearance"))
        self.language_card.title.setText(tr("settings.language"))
        self.language_card.description.setText(tr("settings.language.description"))
        self.language.setAccessibleName(tr("settings.language"))
        self.theme_card.title.setText(tr("settings.theme"))
        self.theme_card.description.setText(tr("settings.theme.description"))
        self.theme.setAccessibleName(tr("settings.theme"))
        self._fill(self.language, LANGUAGES, "settings.language", "language")
        self._fill(self.theme, THEMES, "settings.theme", "theme")

        self.data_label.setText(tr("settings.section.data"))
        location = str(self._context.paths.data_dir)
        if self._context.paths.portable:
            location = f"{location}\n{tr('settings.data.portable')}"
        self.location_card.title.setText(tr("settings.data.location"))
        self.location_card.description.setText(location)
        self.open_data.setText(tr("settings.data.open_folder"))
        self.logs_card.title.setText(tr("settings.data.logs.title"))
        self.logs_card.description.setText(tr("settings.data.logs.description"))
        self.open_logs.setText(tr("settings.data.open_logs"))
        self.export_card.title.setText(tr("settings.data.export.title"))
        self.export_card.description.setText(tr("settings.data.export.description"))
        self.export_button.setText(tr("settings.data.export.button"))
        self.delete_card.title.setText(tr("settings.data.delete.title"))
        self.delete_card.description.setText(tr("settings.data.delete.description"))
        self.delete_button.setText(tr("settings.data.delete.button"))

        self.system_label.setText(tr("settings.section.system"))
        for card, switch, key in (
            (self.background_card, self.background_switch, "background"),
            (self.autostart_card, self.autostart_switch, "autostart"),
            (self.clipboard_card, self.clipboard_switch, "clipboard"),
            (self.hotkeys_card, self.hotkeys_switch, "hotkeys"),
        ):
            card.title.setText(tr(f"settings.{key}.title"))
            card.description.setText(tr(f"settings.{key}.description"))
            switch.set_labels(tr("common.off"), tr("common.on"))
            switch.setAccessibleName(tr(f"settings.{key}.title"))
        if not autostart.supported():
            self.autostart_card.description.setText(
                f"{tr('settings.autostart.description')} {tr('settings.autostart.unavailable')}"
            )
        from desktop_organizer.app.hotkeys import HotkeyManager

        if not HotkeyManager.supported():
            self.hotkeys_card.description.setText(tr("settings.hotkeys.unsupported"))
        for key, label in self.hotkey_labels.items():
            label.setText(tr(f"settings.hotkey.{key.removeprefix('hotkey_')}"))
        self._show_hotkey_errors()
        self.tools_label.setText(tr("settings.section.tools"))
        for card, button, tool_id in self.tool_cards:
            card.title.setText(tr(f"tool.{tool_id}.title"))
            card.description.setText(tr(f"tool.{tool_id}.description"))
            button.setText(tr("settings.tools.button"))
        self.about_label.setText(tr("settings.section.about"))
        self.about_card.title.setText(tr("app.name"))
        self.about_card.description.setText(
            f"{tr('settings.about.version', version=__version__)} · {tr('settings.about.license')}"
        )

    # -- system and tool settings ---------------------------------------------------------------

    def _switch_changed(self, key: str, on: bool) -> None:
        self._context.settings.set(key, bool(on))
        if key == "hotkeys_enabled":
            QTimer.singleShot(200, self._show_hotkey_errors)

    def _external_change(self, key: str, value: object) -> None:
        switches = {
            "run_in_background": self.background_switch,
            "autostart": self.autostart_switch,
            "clipboard_monitoring": self.clipboard_switch,
            "hotkeys_enabled": self.hotkeys_switch,
        }
        switch = switches.get(key)
        if switch is not None and switch.isChecked() != bool(value):
            switch.blockSignals(True)
            switch.setChecked(bool(value))
            switch.blockSignals(False)

    def _hotkey_changed(self, key: str, editor: QKeySequenceEdit) -> None:
        from desktop_organizer.app.hotkeys import normalize, parse

        text = normalize(editor.keySequence())
        if not text or parse(text) is None:
            self.hotkey_errors[key].setText(tr("settings.hotkey.error.invalid"))
            return
        self._context.settings.set(key, text)
        QTimer.singleShot(200, self._show_hotkey_errors)

    def _show_hotkey_errors(self) -> None:
        errors = getattr(self.services, "hotkey_errors", {}) if self.services else {}
        enabled = bool(self._context.settings.get("hotkeys_enabled"))
        for key, label in self.hotkey_errors.items():
            code = errors.get(key) if enabled else None
            label.setText(
                tr(f"settings.hotkey.error.{code}") if code in ("taken", "invalid") else ""
            )
            self.hotkey_editors[key].setEnabled(enabled)

    def _open_tool_settings(self, tool_id: str, fields: tuple[SettingField, ...]) -> None:
        ToolSettingsDialog(self._context.settings, tool_id, fields, self).exec()

    def _fill(self, combo: QComboBox, values: tuple[str, ...], prefix: str, key: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem(tr(f"{prefix}.{value}"), value)
        combo.setCurrentIndex(values.index(self._context.settings.get(key)))
        combo.blockSignals(False)

    def _language_changed(self, _index: int) -> None:
        value = self.language.currentData()
        self._context.settings.set("language", value)
        locale_name = QApplication.instance().property("systemLocale") or ""  # type: ignore[union-attr]
        self._context.translator.set_language(resolve_language(value, str(locale_name)))

    def _theme_changed(self, _index: int) -> None:
        value = self.theme.currentData()
        self._context.settings.set("theme", value)
        self._context.theme.set_mode(value)

    def export_data(self) -> None:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        suggested = Path(documents) / tr("export.default_name", date=date.today().isoformat())
        target, _ = QFileDialog.getSaveFileName(
            self, tr("export.dialog_title"), str(suggested), tr("export.file_filter")
        )
        if not target:
            return
        path = Path(target)
        if path.suffix.lower() != ".zip":
            path = path.with_suffix(".zip")
        try:
            data_management.export_data(self._context.paths, self._context.database, path)
        except Exception as exc:
            log.exception("Export failed")
            dialogs.warn(self, tr("export.failed_title"), tr("export.failed", error=str(exc)))
            return
        log.info("Exported data to %s", path)
        dialogs.inform(self, tr("export.done_title"), tr("export.done", path=str(path)))

    def delete_all_data(self) -> None:
        confirmed = dialogs.confirm_destructive(
            self,
            tr("delete.title"),
            tr("delete.body"),
            tr("delete.confirm"),
            tr("delete.cancel"),
        )
        if not confirmed:
            return
        ctx = self._context
        log.info("Deleting all data on user request")
        ctx.settings.disable_saving()
        ctx.database.close()
        logging_setup.shutdown()
        try:
            data_management.delete_all_data(ctx.paths)
        except OSError as exc:
            dialogs.warn(
                self,
                tr("delete.failed_title"),
                tr("delete.failed", error=str(exc), path=str(ctx.paths.data_dir)),
            )
        else:
            dialogs.inform(self, tr("delete.done_title"), tr("delete.done"))
        QApplication.quit()
