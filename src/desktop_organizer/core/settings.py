"""Persistent user settings stored as versioned JSON."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

LANGUAGES = ("system", "de", "en")
THEMES = ("system", "light", "dark")

DEFAULTS: dict[str, Any] = {
    "language": "system",
    "theme": "system",
    "window_geometry": {},
}

_CHOICES: dict[str, tuple[str, ...]] = {"language": LANGUAGES, "theme": THEMES}

Listener = Callable[[str, Any], None]


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Bring settings from older schema versions up to ``SCHEMA_VERSION``.

    Version 1 is the first schema; later versions add steps here, one per version.
    """
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise ValueError(f"Unsupported settings schema version: {version!r}")
    data["schema_version"] = SCHEMA_VERSION
    return data


def _validated(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in data:
            continue
        value = data[key]
        if key in _CHOICES and value not in _CHOICES[key]:
            log.warning("Ignoring invalid value for setting %s: %r", key, value)
            continue
        if not isinstance(value, type(default)):
            log.warning("Ignoring setting %s with unexpected type", key)
            continue
        result[key] = value
    return result


class Settings:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._values: dict[str, Any] = dict(DEFAULTS)
        self._listeners: list[Listener] = []
        self._saving_enabled = True

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        if not self._path.exists():
            self._values = dict(DEFAULTS)
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Settings file does not contain an object")
            self._values = _validated(_migrate(raw))
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
            self._values = dict(DEFAULTS)

    def save(self) -> None:
        if not self._saving_enabled:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": SCHEMA_VERSION, **self._values}
        tmp = self._path.with_name(self._path.name + ".tmp")
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
        if self._values.get(key) == value:
            return
        self._values[key] = value
        self.save()
        for listener in list(self._listeners):
            listener(key, value)

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)
