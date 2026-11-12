"""Where the application keeps its data.

Installed builds store data in ``%APPDATA%\\DesktopOrganizer``. A portable build is
recognised by a folder named ``data`` next to the executable and keeps everything there,
so the whole folder can be moved to another drive.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from desktop_organizer import APP_ID

DATA_DIR_ENV = "DESKTOP_ORGANIZER_DATA_DIR"
PORTABLE_DIR_NAME = "data"


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    portable: bool

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "organizer.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def executable_dir() -> Path | None:
    """Folder of the packaged executable, or ``None`` when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def resolve_paths(
    environ: Mapping[str, str] | None = None,
    exe_dir: Path | None = None,
    platform: str | None = None,
) -> AppPaths:
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform

    override = env.get(DATA_DIR_ENV)
    if override:
        return AppPaths(Path(override), portable=False)

    if exe_dir is not None and (exe_dir / PORTABLE_DIR_NAME).is_dir():
        return AppPaths(exe_dir / PORTABLE_DIR_NAME, portable=True)

    if plat == "win32":
        appdata = env.get("APPDATA")
        if appdata:
            return AppPaths(Path(appdata) / APP_ID, portable=False)
        return AppPaths(Path.home() / "AppData" / "Roaming" / APP_ID, portable=False)

    # Development on other platforms only.
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return AppPaths(base / APP_ID, portable=False)


def resources_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources"
