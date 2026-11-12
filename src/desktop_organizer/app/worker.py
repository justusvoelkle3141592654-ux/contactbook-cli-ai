"""Runs tool logic in a background thread so windows never freeze."""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from desktop_organizer.core.jobs import Cancelled, Job

log = logging.getLogger(__name__)

PROGRESS_INTERVAL_S = 0.05


class _Signals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class Worker(QRunnable):
    """Call ``function(job)`` off the UI thread; results arrive as Qt signals."""

    def __init__(self, function: Callable[[Job], Any]) -> None:
        super().__init__()
        self.signals = _Signals()
        self._function = function
        self._last_emit = 0.0
        self.job = Job(self._emit_progress)

    def _emit_progress(self, done: int, total: int, message: str) -> None:
        # Throttle: thousands of files per second would flood the UI thread.
        now = time.monotonic()
        if now - self._last_emit >= PROGRESS_INTERVAL_S or (total and done >= total):
            self._last_emit = now
            self.signals.progress.emit(done, total, message)

    def run(self) -> None:
        try:
            result = self._function(self.job)
        except Cancelled:
            self.signals.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 - reported to the user, logged with traceback
            log.error("Background task failed\n%s", traceback.format_exc())
            self.signals.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.signals.finished.emit(result)


def start(worker: Worker) -> None:
    QThreadPool.globalInstance().start(worker)
