"""Start a tool as its own process (own window and taskbar button)."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QProcess

log = logging.getLogger(__name__)


def command(tool_id: str, extra: list[str] | None = None) -> tuple[str, list[str]]:
    args = ["--tool", tool_id, *(extra or [])]
    if getattr(sys, "frozen", False):
        return sys.executable, args
    return sys.executable, ["-m", "desktop_organizer", *args]


def launch_tool(tool_id: str, extra: list[str] | None = None) -> bool:
    program, args = command(tool_id, extra)
    started, _pid = QProcess.startDetached(program, args)
    if not started:
        log.error("Could not start tool %s (%s %s)", tool_id, program, args)
    return bool(started)
