"""Cancellation and progress reporting for long-running work, independent of Qt.

Tool logic accepts a ``Job`` and calls ``job.progress(...)`` and ``job.check()``. The
UI runs the logic in a worker thread and maps progress to a progress bar; tests call
the same functions directly.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

ProgressCallback = Callable[[int, int, str], None]


class Cancelled(Exception):
    """Raised inside a job when the user pressed Cancel."""


class Job:
    def __init__(self, on_progress: ProgressCallback | None = None) -> None:
        self._cancel = threading.Event()
        self._on_progress = on_progress

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        if self._cancel.is_set():
            raise Cancelled

    def progress(self, done: int, total: int = 0, message: str = "") -> None:
        """Report progress; ``total == 0`` means unknown total. Also checks for cancel."""
        self.check()
        if self._on_progress is not None:
            self._on_progress(done, total, message)
