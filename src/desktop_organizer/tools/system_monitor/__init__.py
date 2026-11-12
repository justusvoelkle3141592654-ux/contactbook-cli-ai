"""System monitor: live CPU, memory, disks, network, battery and processes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("refresh_seconds", "int", 2, minimum=1, maximum=30),
    SettingField("process_count", "int", 30, minimum=5, maximum=300),
    SettingField("process_sort", "choice", "cpu", choices=("cpu", "memory")),
    SettingField("show_cores", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.system_monitor.window import SystemMonitorWindow

    return SystemMonitorWindow(context)


SPEC = ToolSpec(
    "system_monitor",
    Category.SYSTEM,
    "activity",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
