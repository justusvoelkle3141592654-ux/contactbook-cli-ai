"""Tasks: to-dos with due dates, priorities, lists and optional reminders."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec
from desktop_organizer.tools.tasks.logic import MIGRATIONS

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("default_filter", "choice", "open", choices=("open", "today", "upcoming")),
    SettingField("reminder_lead_minutes", "int", 15, minimum=0, maximum=10080),
    SettingField("default_due_hour", "int", 9, minimum=0, maximum=23),
    SettingField("confirm_delete", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.tasks.window import TasksWindow

    return TasksWindow(context)


SPEC = ToolSpec(
    "tasks",
    Category.EVERYDAY,
    "list-checks",
    factory=_window,
    settings=SETTINGS,
    migrations=MIGRATIONS,
    package_dir=Path(__file__).parent,
)
