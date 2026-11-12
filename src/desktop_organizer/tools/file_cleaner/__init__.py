"""File cleaner: sorts a folder into subfolders by file type, with preview and undo."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("folder_language", "choice", "ui", choices=("ui", "de", "en")),
    SettingField("move_other", "bool", True),
    SettingField("date_subfolders", "choice", "none", choices=("none", "year", "year_month")),
    SettingField("skip_recent_minutes", "int", 10, minimum=0, maximum=1440),
    SettingField("on_conflict", "choice", "rename", choices=("rename", "skip")),
    SettingField("include_hidden", "bool", False),
    SettingField("confirm_before_move", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.file_cleaner.window import FileCleanerWindow

    return FileCleanerWindow(context)


SPEC = ToolSpec(
    "file_cleaner",
    Category.FILES,
    "folder-tree",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
