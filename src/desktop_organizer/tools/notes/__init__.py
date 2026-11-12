"""Notes: quick capture, tags and full-text search."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.notes.logic import MIGRATIONS
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("sort", "choice", "updated", choices=("updated", "created", "title")),
    SettingField("editor_font_size", "int", 15, minimum=10, maximum=32),
    SettingField("monospace", "bool", False),
    SettingField("confirm_delete", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.notes.window import NotesWindow

    return NotesWindow(context)


SPEC = ToolSpec(
    "notes",
    Category.EVERYDAY,
    "notebook-pen",
    factory=_window,
    settings=SETTINGS,
    migrations=MIGRATIONS,
    package_dir=Path(__file__).parent,
)
