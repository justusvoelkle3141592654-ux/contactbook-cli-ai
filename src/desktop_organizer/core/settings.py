"""Persistent user settings stored as versioned JSON.

Global settings live at the top level; each tool keeps its own options below
``tools.<tool_id>`` (see ``core/tool_settings.py``). Several processes (the main
window and every tool window) share the file; ``reload`` picks up changes made by
another process.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

LANGUAGES = ("system", "de", "en")
THEMES = ("system", "light", "dark")

DEFAULTS: dict[str, Any] = {
    "language": "system",
    "theme": "system",
    "window_geometry": {},
    "tools": {},
    "run_in_background": False,
    "autostart": False,
    "hotkeys_enabled": False,
    "hotkey_quick_note": "Ctrl+Alt+N",
    "hotkey_clipboard": "Ctrl+Alt+V",
    "hotkey_password": "Ctrl+Alt+P",
    "clipboard_monitoring": False,
    "recent_tools": [],
}

_CHOICES: dict[str, tuple[str, ...]] = {"language": LANGUAGES, "theme": THEMES}

Listener = Callable[[str, Any], None]


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Bring settings from older schema versions up to ``SCHEMA_VERSION``."""
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise ValueError(f"Unsupported settings schema version: {version!r}")
    if version < 2:
        # Version 2 added per-tool settings and system integration options; the new
        # keys simply take their defaults.
        version = 2
    data["schema_version"] = SCHEMA_VERSION
    return data


def _validated(data: dict[str, Any]) -> dict[str, Any]:
    result = {k: (v.copy() if isinstance(v, dict | list) else v) for k, v in DEFAULTS.items()}
    for key, default in DEFAULTS.items():
        if key not in data:
            continue
        value = data[key]
        if key in _CHOICES and value not in _CHOICES[key]:
            log.warning("Ignoring invalid value for setting %s: %r", key, value)
            continue
        if type(value) is not type(default):
            log.warning("Ignoring setting %s with unexpected type", key)
            continue
        result[key] = value
    return result


class Settings:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._values: dict[str, Any] = _validated({})
        self._listeners: list[Listener] = []
        self._saving_enabled = True

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict[str, Any]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Settings file does not contain an object")
        return _validated(_migrate(raw))

    def load(self) -> None:
        if not self._path.exists():
            self._values = _validated({})
            return
        try:
            self._values = self._read()
        except (OSError, ValueError) as exc:
            # A damaged file must never stop the app from starting. Keep a copy for
            # inspection and continue with defaults.
            backup = self._path.with_name(
                f"{self._path.name}.broken-{datetime.now():%Y%m%d-%H%M%S}"
            )
            log.error("Settings could not be read (%s); saved a copy as %s", exc, backup.name)
            try:
                self._path.replace(backup)
            except OSError:
                log.exception("Could not move the damaged settings file")
            self._values = _validated({})

    def reload(self) -> list[str]:
        """Re-read the file written by another process; notify about changed keys."""
        if not self._path.exists():
            return []
        try:
            fresh = self._read()
        except (OSError, ValueError):
            return []  # partly written or damaged: keep current values, try next time
        changed = [k for k in fresh if fresh[k] != self._values.get(k)]
        self._values = fresh
        for key in changed:
            self._notify(key, fresh[key])
        return changed

    def save(self) -> None:
        if not self._saving_enabled:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": SCHEMA_VERSION, **self._values}
        tmp = self._path.with_name(f"{self._path.name}.{id(self)}.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    def disable_saving(self) -> None:
        """Used after "Delete all data" so nothing is written again on exit."""
        self._saving_enabled = False

    def get(self, key: str) -> Any:
        return self._values[key]

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        if key in _CHOICES and value not in _CHOICES[key]:
            raise ValueError(f"Invalid value for {key}: {value!r}")
        if type(value) is not type(DEFAULTS[key]):
            raise TypeError(f"Invalid type for {key}: {type(value).__name__}")
        if self._values.get(key) == value:
            return
        self._values[key] = value
        self.save()
        self._notify(key, value)

    def tool_values(self, tool_id: str) -> dict[str, Any]:
        stored = self._values["tools"].get(tool_id, {})
        return dict(stored) if isinstance(stored, dict) else {}

    def set_tool_value(self, tool_id: str, key: str, value: Any) -> None:
        tools = {k: dict(v) for k, v in self._values["tools"].items() if isinstance(v, dict)}
        entry = tools.setdefault(tool_id, {})
        if entry.get(key) == value and key in entry:
            return
        entry[key] = value
        self._values["tools"] = tools
        self.save()
        self._notify("tools", tools)

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, key: str, value: Any) -> None:
        for listener in list(self._listeners):
            listener(key, value)
