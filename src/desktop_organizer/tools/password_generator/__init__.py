"""Password generator: strong passwords and passphrases from a secure random source."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.tool_settings import SettingField
from desktop_organizer.tools.registry import Category, ToolSpec

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

SETTINGS = (
    SettingField("default_length", "int", 20, minimum=4, maximum=128),
    SettingField("clear_clipboard_seconds", "int", 30, minimum=0, maximum=600),
    SettingField("passphrase_language", "choice", "ui", choices=("ui", "de", "en")),
    SettingField("symbol_set", "text", "!#$%&*+-=?@^_~.,:;()[]{}<>/"),
    SettingField("batch_count", "int", 10, minimum=2, maximum=200),
)


def _window(context: AppContext) -> ToolWindow:
    from desktop_organizer.tools.password_generator.window import PasswordWindow

    return PasswordWindow(context)


SPEC = ToolSpec(
    "password_generator",
    Category.SAFETY,
    "key-round",
    factory=_window,
    settings=SETTINGS,
    package_dir=Path(__file__).parent,
)
