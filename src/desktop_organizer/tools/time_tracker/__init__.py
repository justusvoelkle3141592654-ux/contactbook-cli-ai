"""Time tracker: start/stop timers per project, daily and weekly totals, CSV export."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec
from desktop_organizer.tools.time_tracker.logic import MIGRATIONS

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("week_start", "choice", "monday", choices=("monday", "sunday")),
    SettingField("round_minutes", "int", 0, minimum=0, maximum=60),
    SettingField("daily_goal_hours", "int", 8, minimum=0, maximum=24),
    SettingField("confirm_delete", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.time_tracker.window import TimeTrackerWindow

    return TimeTrackerWindow(context)


SPEC = ToolSpec(
    "time_tracker",
    Category.EVERYDAY,
    "timer",
    factory=_window,
    settings=SETTINGS,
    migrations=MIGRATIONS,
    package_dir=Path(__file__).parent,
)
