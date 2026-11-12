"""Backup helper: copies chosen folders to a destination, only changed files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("verify", "choice", "size", choices=("none", "size", "hash")),
    SettingField("exclude", "text", "~$*; *.tmp; Thumbs.db; desktop.ini; .DS_Store"),
    SettingField("skip_hidden", "bool", False),
    SettingField("confirm_mirror", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.backup.window import BackupWindow

    return BackupWindow(context)


SPEC = ToolSpec(
    "backup",
    Category.SAFETY,
    "hard-drive-download",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
