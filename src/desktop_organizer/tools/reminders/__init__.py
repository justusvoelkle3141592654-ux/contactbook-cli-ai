"""Reminders: one-off and recurring reminders as Windows notifications."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec
from desktop_organizer.tools.reminders.logic import MIGRATIONS

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("show_missed", "bool", True),
    SettingField("default_lead_minutes", "int", 15, minimum=1, maximum=1440),
    SettingField("break_interval_minutes", "int", 50, minimum=5, maximum=600),
    SettingField("confirm_delete", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.reminders.window import RemindersWindow

    return RemindersWindow(context)


SPEC = ToolSpec(
    "reminders",
    Category.EVERYDAY,
    "bell",
    factory=_window,
    settings=SETTINGS,
    migrations=MIGRATIONS,
    package_dir=Path(__file__).parent,
)
