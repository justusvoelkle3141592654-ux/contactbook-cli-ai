"""Catalogue of tools shown in the overview.

Every tool lives in its own package below ``desktop_organizer.tools`` and exposes a
module-level ``SPEC`` (a ``ToolSpec`` with a window factory). Tools that are planned but
not built yet appear in ``PLANNED`` and are shown as "not available yet". Adding a tool
means adding its package; no other tool changes.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

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

WindowFactory = Callable[["AppContext"], "ToolWindow"]


@dataclass(frozen=True)
class ToolSpec:
    id: str
    category: Category
    icon: str
    factory: WindowFactory | None = None

    @property
    def available(self) -> bool:
        return self.factory is not None

    @property
    def title_key(self) -> str:
        return f"tool.{self.id}.title"

    @property
    def description_key(self) -> str:
        return f"tool.{self.id}.description"


PLANNED: tuple[ToolSpec, ...] = (
    ToolSpec("file_cleaner", Category.FILES, "folder-tree"),
    ToolSpec("duplicate_finder", Category.FILES, "copy"),
    ToolSpec("file_size", Category.FILES, "chart-pie"),
    ToolSpec("text_replacer", Category.FILES, "replace"),
    ToolSpec("backup", Category.SAFETY, "hard-drive-download"),
    ToolSpec("password_generator", Category.SAFETY, "key-round"),
    ToolSpec("notes", Category.EVERYDAY, "notebook-pen"),
    ToolSpec("tasks", Category.EVERYDAY, "list-checks"),
    ToolSpec("reminders", Category.EVERYDAY, "bell"),
    ToolSpec("time_tracker", Category.EVERYDAY, "timer"),
    ToolSpec("system_monitor", Category.SYSTEM, "activity"),
    ToolSpec("clipboard_history", Category.SYSTEM, "clipboard-list"),
)


def discover() -> dict[str, ToolSpec]:
    """Return implemented tools found as packages below ``desktop_organizer.tools``."""
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
    """Planned tools in their fixed order, replaced by the implementation where one exists."""
    impl = discover() if implemented is None else implemented
    tools = [impl.get(spec.id, spec) for spec in PLANNED]
    planned_ids = {spec.id for spec in PLANNED}
    tools.extend(spec for tool_id, spec in impl.items() if tool_id not in planned_ids)
    order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    return sorted(tools, key=lambda s: order[s.category])  # stable: keeps planned order
