"""Duplicate finder: finds identical files by content and removes extra copies safely."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("method", "choice", "content", choices=("content", "fast", "name_size")),
    SettingField("min_size_kb", "int", 4, minimum=0, maximum=10_000_000),
    SettingField("max_size_mb", "int", 0, minimum=0, maximum=10_000_000),
    SettingField("include_extensions", "text", ""),
    SettingField("exclude_extensions", "text", "tmp, log, lnk"),
    SettingField("exclude_folders", "text", ".git, node_modules, $Recycle.Bin, __pycache__"),
    SettingField("skip_hidden", "bool", True),
    SettingField(
        "default_rule",
        "choice",
        "oldest",
        choices=("oldest", "newest", "shortest_path", "longest_path", "first_folder"),
    ),
    SettingField("auto_select", "bool", True),
    SettingField("confirm_before_delete", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.duplicate_finder.window import DuplicateFinderWindow

    return DuplicateFinderWindow(context)


SPEC = ToolSpec(
    "duplicate_finder",
    Category.FILES,
    "copy",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
