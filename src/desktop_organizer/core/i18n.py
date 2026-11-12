"""German and English UI strings.

Strings live in ``resources/i18n/<code>.json`` as flat ``key: text`` objects. Placeholders
use ``{name}`` syntax and are filled with keyword arguments.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED = ("de", "en")
FALLBACK = "en"


def system_language(locale_name: str) -> str:
    """Interview decision: English when Windows is English, German otherwise."""
    return "en" if locale_name.lower().startswith("en") else "de"


def resolve_language(setting: str, locale_name: str) -> str:
    return system_language(locale_name) if setting == "system" else setting


def load_catalog(directory: Path, code: str) -> dict[str, str]:
    data = json.loads((directory / f"{code}.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ValueError(f"Language file {code}.json must map strings to strings")
    return data


class Translator:
    def __init__(self, directory: Path, language: str) -> None:
        self._catalogs = {code: load_catalog(directory, code) for code in SUPPORTED}
        self._language = language if language in SUPPORTED else FALLBACK
        self._listeners: list[Callable[[], None]] = []
        self._reported: set[str] = set()

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, code: str) -> None:
        if code not in SUPPORTED:
            raise ValueError(code)
        if code == self._language:
            return
        self._language = code
        for listener in list(self._listeners):
            listener()

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def tr(self, key: str, **kwargs: object) -> str:
        text = self._catalogs[self._language].get(key)
        if text is None:
            text = self._catalogs[FALLBACK].get(key)
            if key not in self._reported:
                self._reported.add(key)
                log.warning("Missing translation for %r (%s)", key, self._language)
        if text is None:
            return key
        return text.format(**kwargs) if kwargs else text


_current: Translator | None = None


def install(translator: Translator) -> None:
    global _current
    _current = translator


def current() -> Translator:
    if _current is None:
        raise RuntimeError("No translator installed")
    return _current


def tr(key: str, **kwargs: object) -> str:
    return current().tr(key, **kwargs)
