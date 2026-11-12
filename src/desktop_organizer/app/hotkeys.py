"""System-wide keyboard shortcuts on Windows (RegisterHotKey).

Only the main process registers shortcuts. Supported keys: letters, digits and F1 to
F12 combined with Ctrl, Alt, Shift and Win. Other platforms report "unsupported".
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312


def parse(text: str) -> tuple[int, int] | None:
    """'Ctrl+Alt+N' -> (modifiers, virtual key) or None if not supported."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        return None
    modifiers = 0
    for part in parts[:-1]:
        flag = {
            "ctrl": MOD_CONTROL,
            "strg": MOD_CONTROL,
            "alt": MOD_ALT,
            "shift": MOD_SHIFT,
            "umschalt": MOD_SHIFT,
            "win": MOD_WIN,
            "meta": MOD_WIN,
        }.get(part)
        if flag is None:
            return None
        modifiers |= flag
    key = parts[-1]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        vk = 0x70 + int(key[1:]) - 1
    else:
        return None
    if modifiers & ~MOD_SHIFT == 0:
        return None  # require Ctrl, Alt or Win so typing is never captured
    return modifiers, vk


def normalize(sequence: QKeySequence) -> str:
    return sequence.toString(QKeySequence.SequenceFormat.PortableText)


class HotkeyManager(QAbstractNativeEventFilter):
    def __init__(self) -> None:
        super().__init__()
        self._callbacks: dict[int, Callable[[], object]] = {}
        self._next_id = 0xB000
        self._installed = False

    @staticmethod
    def supported() -> bool:
        return sys.platform == "win32"

    def register(self, text: str, callback: Callable[[], object]) -> str | None:
        """Register; returns None on success or an error code."""
        if not self.supported():
            return "unsupported"
        parsed = parse(text)
        if parsed is None:
            return "invalid"
        import ctypes

        modifiers, vk = parsed
        hotkey_id = self._next_id
        self._next_id += 1
        if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk):
            log.warning("Hotkey %s is already used by another program", text)
            return "taken"
        self._callbacks[hotkey_id] = callback
        if not self._installed:
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)
                self._installed = True
        return None

    def unregister_all(self) -> None:
        if not self.supported():
            return
        import ctypes

        for hotkey_id in list(self._callbacks):
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self._callbacks.clear()

    def nativeEventFilter(self, event_type: QByteArray | bytes, message: int) -> object:  # noqa: N802
        kind = event_type.data() if isinstance(event_type, QByteArray) else event_type
        if bytes(kind) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        from ctypes import wintypes

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam in self._callbacks:
            self._callbacks[msg.wParam]()
            return True, 0
        return False, 0
