"""Settings: language, theme, data location, export and deletion."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer import __version__
from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.core import data_management, logging_setup
from desktop_organizer.core.i18n import resolve_language, tr
from desktop_organizer.core.settings import LANGUAGES, THEMES

log = logging.getLogger(__name__)


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    return line


def _label(style: str) -> QLabel:
    label = QLabel()
    label.setProperty("textStyle", style)
    return label


class SettingsDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setMinimumWidth(560)

        self.general_heading = _label("subtitle")
        self.language_label = QLabel()
        self.language = QComboBox()
        self.theme_label = QLabel()
        self.theme = QComboBox()
        for combo in (self.language, self.theme):
            combo.setMinimumWidth(240)
        self.language_label.setBuddy(self.language)
        self.theme_label.setBuddy(self.theme)
        general = QFormLayout()
        general.setHorizontalSpacing(16)
        general.setVerticalSpacing(8)
        general.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        general.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        general.addRow(self.language_label, self.language)
        general.addRow(self.theme_label, self.theme)

        self.data_heading = _label("subtitle")
        self.location_label = _label("secondary")
        self.location_value = QLabel(str(context.paths.data_dir))
        self.location_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location_value.setWordWrap(True)
        self.portable_note = _label("caption")
        self.portable_note.setWordWrap(True)
        self.portable_note.setVisible(context.paths.portable)
        self.open_data = QPushButton()
        self.open_logs = QPushButton()
        self.export_button = QPushButton()
        self.delete_button = QPushButton()
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.open_data)
        folder_row.addWidget(self.open_logs)
        folder_row.addStretch(1)
        data_row = QHBoxLayout()
        data_row.setSpacing(8)
        data_row.addWidget(self.export_button)
        data_row.addWidget(self.delete_button)
        data_row.addStretch(1)

        self.about_heading = _label("subtitle")
        self.version_label = QLabel()
        self.license_label = _label("caption")

        self.close_button = QPushButton()
        self.close_button.setProperty("role", "primary")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(self.general_heading)
        layout.addLayout(general)
        layout.addSpacing(16)
        layout.addWidget(_divider())
        layout.addSpacing(16)
        layout.addWidget(self.data_heading)
        layout.addWidget(self.location_label)
        layout.addWidget(self.location_value)
        layout.addWidget(self.portable_note)
        layout.addSpacing(4)
        layout.addLayout(folder_row)
        layout.addLayout(data_row)
        layout.addSpacing(16)
        layout.addWidget(_divider())
        layout.addSpacing(16)
        layout.addWidget(self.about_heading)
        layout.addWidget(self.version_label)
        layout.addWidget(self.license_label)
        layout.addSpacing(16)
        layout.addLayout(footer)

        self.language.currentIndexChanged.connect(self._language_changed)
        self.theme.currentIndexChanged.connect(self._theme_changed)
        self.open_data.clicked.connect(lambda: dialogs.open_folder(self, context.paths.data_dir))
        self.open_logs.clicked.connect(lambda: dialogs.open_folder(self, context.paths.log_dir))
        self.export_button.clicked.connect(self.export_data)
        self.delete_button.clicked.connect(self.delete_all_data)

        context.translator.subscribe(self.retranslate)
        self.finished.connect(lambda _code: context.translator.unsubscribe(self.retranslate))
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("settings.title"))
        self.general_heading.setText(tr("settings.section.general"))
        self.language_label.setText(tr("settings.language"))
        self.theme_label.setText(tr("settings.theme"))
        self._fill(self.language, LANGUAGES, "settings.language", "language")
        self._fill(self.theme, THEMES, "settings.theme", "theme")
        self.data_heading.setText(tr("settings.section.data"))
        self.location_label.setText(tr("settings.data.location"))
        self.portable_note.setText(tr("settings.data.portable"))
        self.open_data.setText(tr("settings.data.open_folder"))
        self.open_logs.setText(tr("settings.data.open_logs"))
        self.export_button.setText(tr("settings.data.export"))
        self.delete_button.setText(tr("settings.data.delete"))
        self.about_heading.setText(tr("settings.section.about"))
        self.version_label.setText(tr("settings.about.version", version=__version__))
        self.license_label.setText(tr("settings.about.license"))
        self.close_button.setText(tr("settings.close"))

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
