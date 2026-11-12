"""Text replacer: replaces terms across many files, with preview, backup and undo."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField(
        "patterns", "text", "*.txt; *.md; *.csv; *.html; *.htm; *.xml; *.json; *.ini; *.cfg; *.log"
    ),
    SettingField("recursive", "bool", True),
    SettingField("skip_hidden", "bool", True),
    SettingField("max_file_mb", "int", 20, minimum=1, maximum=2048),
    SettingField("backup", "bool", True),
    SettingField("confirm_before_replace", "bool", True),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.text_replacer.window import TextReplacerWindow

    return TextReplacerWindow(context)


SPEC = ToolSpec(
    "text_replacer",
    Category.FILES,
    "replace",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
