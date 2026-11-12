"""Standard dialogs used by every window, so confirmations look and behave the same."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from desktop_organizer.core.i18n import tr

log = logging.getLogger(__name__)


def confirm_destructive(
    parent: QWidget | None, title: str, body: str, confirm: str, cancel: str
) -> bool:
    """Ask before an irreversible action. The safe choice is the default; Esc cancels."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    confirm_button = QPushButton(confirm)
    confirm_button.setProperty("role", "destructive")
    cancel_button = QPushButton(cancel)
    box.addButton(confirm_button, QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(cancel_button, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.setEscapeButton(cancel_button)
    box.exec()
    return box.clickedButton() is confirm_button


def confirm(parent: QWidget | None, title: str, body: str, confirm: str, cancel: str) -> bool:
    """Ask a yes/no question where confirming is not destructive."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    confirm_button = QPushButton(confirm)
    confirm_button.setProperty("role", "primary")
    cancel_button = QPushButton(cancel)
    box.addButton(confirm_button, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(cancel_button, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(confirm_button)
    box.setEscapeButton(cancel_button)
    box.exec()
    return box.clickedButton() is confirm_button


def message(parent: QWidget | None, icon: QMessageBox.Icon, title: str, body: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(body)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def inform(parent: QWidget | None, title: str, body: str) -> None:
    message(parent, QMessageBox.Icon.Information, title, body)


def warn(parent: QWidget | None, title: str, body: str) -> None:
    message(parent, QMessageBox.Icon.Warning, title, body)


def critical(parent: QWidget | None, title: str, body: str) -> None:
    message(parent, QMessageBox.Icon.Critical, title, body)


def shortcut(
    key: QKeySequence | QKeySequence.StandardKey | str, parent: QWidget, slot: Callable[[], object]
) -> QShortcut:
    sc = QShortcut(QKeySequence(key), parent)
    sc.activated.connect(slot)
    return sc


def open_folder(parent: QWidget | None, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
        log.warning("Could not open folder %s", folder)
        warn(parent, tr("error.open_folder_title"), tr("error.open_folder", path=str(folder)))
