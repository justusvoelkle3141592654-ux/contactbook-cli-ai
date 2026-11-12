"""Start with Windows via the per-user Run key (no administrator rights needed)."""

from __future__ import annotations

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DesktopOrganizer"


def supported() -> bool:
    """Only the packaged Windows build can register itself."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def command() -> str:
    return f'"{sys.executable}" --minimized'


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME, cmd: str | None = None) -> None:
    if sys.platform != "win32":
        raise OSError("Autostart is only available on Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, cmd or command())
        else:
            try:
                winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass
