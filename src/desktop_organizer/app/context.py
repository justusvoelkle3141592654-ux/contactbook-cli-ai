"""Services shared by the shell and every tool window."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.core.i18n import Translator
from desktop_organizer.core.paths import AppPaths
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database

if TYPE_CHECKING:
    from desktop_organizer.tools.registry import ToolSpec


@dataclass
class AppContext:
    paths: AppPaths
    settings: Settings
    translator: Translator
    database: Database
    theme: ThemeManager
    log_file: str
    tools: list[ToolSpec] = field(default_factory=list)
