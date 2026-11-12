import sys
import threading

from desktop_organizer.core import errors


def test_hook_reports_and_survives_failing_reporter() -> None:
    original, original_thread = sys.excepthook, threading.excepthook
    seen: list[BaseException] = []
    try:
        errors.install_hooks(seen.append)
        exc = RuntimeError("boom")
        sys.excepthook(RuntimeError, exc, None)
        assert seen == [exc]

        def failing(_e: BaseException) -> None:
            raise ValueError("reporter broken")

        errors.install_hooks(failing)
        sys.excepthook(RuntimeError, exc, None)  # must not raise
    finally:
        sys.excepthook, threading.excepthook = original, original_thread
