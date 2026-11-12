"""Folder sizes: shows which folders, files and file types use the most space."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("include_hidden", "bool", False),
    SettingField("top_files", "int", 200, minimum=10, maximum=5000),
    SettingField("show_files_entry", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.file_size.window import FileSizeWindow

    return FileSizeWindow(context)


SPEC = ToolSpec(
    "file_size",
    Category.FILES,
    "chart-pie",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
