"""Declarative per-tool settings.

A tool lists its options as ``SettingField`` objects. The same declaration renders the
form in the tool window and on the main settings page, validates stored values and
supplies defaults, so both places always agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from desktop_organizer.core.settings import Settings

Kind = Literal["bool", "int", "choice", "text"]


@dataclass(frozen=True)
class SettingField:
    key: str
    kind: Kind
    default: Any
    choices: tuple[str, ...] = ()
    minimum: int = 0
    maximum: int = 1_000_000

    def label_key(self, tool_id: str) -> str:
        return f"tool.{tool_id}.setting.{self.key}"

    def description_key(self, tool_id: str) -> str:
        return f"tool.{tool_id}.setting.{self.key}.description"

    def choice_key(self, tool_id: str, choice: str) -> str:
        return f"tool.{tool_id}.setting.{self.key}.{choice}"

    def validate(self, value: Any) -> Any:
        """Return ``value`` if it fits this field, otherwise the default."""
        if self.kind == "bool":
            return value if isinstance(value, bool) else self.default
        if self.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                return self.default
            return min(max(value, self.minimum), self.maximum)
        if self.kind == "choice":
            return value if value in self.choices else self.default
        return value if isinstance(value, str) else self.default


def values(settings: Settings, tool_id: str, fields: tuple[SettingField, ...]) -> dict[str, Any]:
    stored = settings.tool_values(tool_id)
    return {f.key: f.validate(stored.get(f.key, f.default)) for f in fields}


def set_value(settings: Settings, tool_id: str, field: SettingField, value: Any) -> None:
    validated = field.validate(value)
    if validated != value:
        raise ValueError(f"Invalid value for {tool_id}.{field.key}: {value!r}")
    settings.set_tool_value(tool_id, field.key, value)
