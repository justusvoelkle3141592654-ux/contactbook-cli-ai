"""Services shared by the shell and every tool window."""

from __future__ import annotations

from dataclasses import dataclass

from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.core.i18n import Translator
from desktop_organizer.core.paths import AppPaths
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database


@dataclass
class AppContext:
    paths: AppPaths
    settings: Settings
    translator: Translator
    database: Database
    theme: ThemeManager
    log_file: str
