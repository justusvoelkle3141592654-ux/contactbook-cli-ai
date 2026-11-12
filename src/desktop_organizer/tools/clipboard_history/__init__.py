"""Clipboard history: remembers copied text, searchable, pin and copy again."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.clipboard_history.logic import DEFAULT_EXCLUDED, MIGRATIONS
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("max_entries", "int", 200, minimum=10, maximum=5000),
    SettingField("max_length_kb", "int", 256, minimum=1, maximum=10_000),
    SettingField("excluded_apps", "text", DEFAULT_EXCLUDED),
    SettingField("ignore_sensitive", "bool", True),
    SettingField("close_after_copy", "bool", False),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.clipboard_history.window import ClipboardWindow

    return ClipboardWindow(context)


SPEC = ToolSpec(
    "clipboard_history",
    Category.SYSTEM,
    "clipboard-list",
    factory=_window,
    settings=SETTINGS,
    migrations=MIGRATIONS,
    package_dir=Path(__file__).parent,
)
