"""Last-resort error handling: log every unhandled exception and tell the user."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from types import TracebackType

log = logging.getLogger("desktop_organizer.errors")

Reporter = Callable[[BaseException], None]


def install_hooks(report: Reporter) -> None:
    """Route unhandled exceptions from the main thread and worker threads to ``report``.

    ``report`` is expected to show a message; it must not raise. The application keeps
    running after an error in an event handler, which Qt allows.
    """

    def excepthook(
        exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        try:
            report(exc)
        except Exception:
            log.exception("Error reporter failed")

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None:
            return
        log.critical(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_hook
