"""Catalogue of tools.

Every tool lives in its own package below ``desktop_organizer.tools`` and exposes a
module-level ``SPEC``. The spec carries everything the shell needs: category, icon,
window factory, settings declaration, database migrations and the location of its
language file. Adding a tool means adding its package; no other tool changes.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from desktop_organizer.core.storage import Migration
from desktop_organizer.core.tool_settings import SettingField

if TYPE_CHECKING:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.tool_window import ToolWindow

log = logging.getLogger(__name__)


class Category(Enum):
    FILES = "files"
    SAFETY = "safety"
    EVERYDAY = "everyday"
    SYSTEM = "system"


CATEGORY_ORDER = (Category.FILES, Category.SAFETY, Category.EVERYDAY, Category.SYSTEM)

TOOL_ORDER = (
    "file_cleaner",
    "duplicate_finder",
    "file_size",
    "text_replacer",
    "backup",
    "password_generator",
    "notes",
    "tasks",
    "reminders",
    "time_tracker",
    "system_monitor",
    "clipboard_history",
)

WindowFactory = Callable[["AppContext"], "ToolWindow"]


@dataclass(frozen=True)
class ToolSpec:
    id: str
    category: Category
    icon: str
    factory: WindowFactory | None = None
    settings: tuple[SettingField, ...] = ()
    migrations: tuple[Migration, ...] = ()
    package_dir: Path | None = field(default=None, compare=False)

    @property
    def available(self) -> bool:
        return self.factory is not None

    @property
    def title_key(self) -> str:
        return f"tool.{self.id}.title"

    @property
    def description_key(self) -> str:
        return f"tool.{self.id}.description"

    @property
    def i18n_file(self) -> Path | None:
        if self.package_dir is None:
            return None
        path = self.package_dir / "i18n.json"
        return path if path.exists() else None


def discover() -> dict[str, ToolSpec]:
    """Return the tools found as packages below ``desktop_organizer.tools``."""
    import desktop_organizer.tools as package

    found: dict[str, ToolSpec] = {}
    for info in pkgutil.iter_modules(package.__path__):
        if not info.ispkg:
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        spec = getattr(module, "SPEC", None)
        if isinstance(spec, ToolSpec):
            found[spec.id] = spec
        else:
            log.warning("Tool package %s has no SPEC", info.name)
    return found


def all_tools(implemented: dict[str, ToolSpec] | None = None) -> list[ToolSpec]:
    """Tools in their fixed order, grouped by category."""
    impl = discover() if implemented is None else implemented
    order = {tool_id: index for index, tool_id in enumerate(TOOL_ORDER)}
    categories = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    return sorted(
        impl.values(), key=lambda s: (categories[s.category], order.get(s.id, len(order)), s.id)
    )


def find(tool_id: str) -> ToolSpec | None:
    return discover().get(tool_id)


def all_migrations(tools: list[ToolSpec]) -> list[Migration]:
    return [migration for spec in tools for migration in spec.migrations]


def i18n_files(tools: list[ToolSpec]) -> list[Path]:
    return [path for spec in tools if (path := spec.i18n_file) is not None]
