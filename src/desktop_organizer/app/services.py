"""Background services of the main process: notification area icon, reminders,
clipboard recording, global shortcuts and autostart.

They live in the main window's process because they must keep working while tool
windows are closed. Each one is off by default and switched in the settings.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from desktop_organizer.app.context import AppContext
from desktop_organizer.app.hotkeys import HotkeyManager
from desktop_organizer.core import autostart, tool_settings
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.paths import resources_dir

if TYPE_CHECKING:
    from desktop_organizer.app.overview import OverviewWindow

log = logging.getLogger(__name__)

REMINDER_INTERVAL_MS = 15_000
MISSED_GRACE_S = 120


def foreground_app() -> str:
    """Executable name of the window in front (Windows only), used for exclusions."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        import psutil

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return str(psutil.Process(pid.value).name())
    except Exception:  # noqa: BLE001 - best effort; an unknown app is simply recorded
        return ""


class BackgroundServices(QObject):
    def __init__(self, context: AppContext, window: OverviewWindow) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self.tray: QSystemTrayIcon | None = None
        self.hotkeys = HotkeyManager()
        self.hotkey_errors: dict[str, str] = {}
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self.check_reminders)
        self._pending_open: str | None = None
        self._told_background = False
        context.settings.subscribe(self._settings_changed)
        context.translator.subscribe(self._retranslate)

    # -- lifecycle ----------------------------------------------------------------------------

    def start(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self._clipboard_changed)
        self._reminder_timer.start(REMINDER_INTERVAL_MS)
        self._update_tray()
        self.apply_hotkeys()
        self.sync_autostart()
        QTimer.singleShot(3000, self.report_missed)
        QTimer.singleShot(5000, self.check_reminders)

    def stop(self) -> None:
        self.hotkeys.unregister_all()
        if self.tray is not None:
            self.tray.hide()

    def _settings_changed(self, key: str, _value: object) -> None:
        if key in ("run_in_background", "clipboard_monitoring"):
            self._update_tray()
        elif key.startswith("hotkey"):
            self.apply_hotkeys()
        elif key == "autostart":
            self.sync_autostart()

    # -- notification area ----------------------------------------------------------------

    def tray_wanted(self) -> bool:
        from desktop_organizer.tools.reminders.logic import next_upcoming

        settings = self.context.settings
        return bool(
            settings.get("run_in_background")
            or settings.get("clipboard_monitoring")
            or next_upcoming(self.context.database.connection) is not None
        )

    def _update_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(QIcon(str(resources_dir() / "app.ico")), self)
            self.tray.activated.connect(self._tray_activated)
            self.tray.messageClicked.connect(self._message_clicked)
            self._retranslate()
        self.tray.setVisible(self.tray_wanted())

    def _retranslate(self) -> None:
        if self.tray is None:
            return
        menu = QMenu()
        entries = [
            (tr("tray.open"), self.window.bring_to_front),
            (tr("tray.quick_note"), lambda: self.window.launch("notes", ["--message", "new"])),
            (tr("tool.tasks.title"), lambda: self.window.launch("tasks")),
            (tr("tool.clipboard_history.title"), lambda: self.window.launch("clipboard_history")),
            (tr("tool.password_generator.title"), lambda: self.window.launch("password_generator")),
        ]
        for text, slot in entries:
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.addSeparator()
        monitoring = QAction(tr("tray.clipboard"), menu)
        monitoring.setCheckable(True)
        monitoring.setChecked(bool(self.context.settings.get("clipboard_monitoring")))
        monitoring.toggled.connect(
            lambda on: self.context.settings.set("clipboard_monitoring", bool(on))
        )
        menu.addAction(monitoring)
        menu.addSeparator()
        quit_action = QAction(tr("tray.quit"), menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        self._menu = menu  # keep a reference; Qt does not own it
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(tr("app.name"))

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.window.bring_to_front()

    def _message_clicked(self) -> None:
        if self._pending_open:
            self.window.launch(self._pending_open)
            self._pending_open = None

    def notify(self, title: str, message: str, open_tool: str | None = None) -> None:
        self._update_tray()
        if self.tray is None or not self.tray.isVisible():
            log.info("Notification not shown (no notification area): %s", title)
            return
        self._pending_open = open_tool
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 10_000)

    def window_closed_to_background(self) -> None:
        if not self._told_background:
            self._told_background = True
            self.notify(tr("app.name"), tr("tray.still_running"))

    # -- reminders ----------------------------------------------------------------------------

    def check_reminders(self) -> None:
        from desktop_organizer.tools.reminders.logic import due_now, mark_fired

        conn = self.context.database.connection
        now = time.time()
        try:
            due = due_now(conn, now)
        except Exception:  # noqa: BLE001 - e.g. database closed after "Delete all data"
            return
        for reminder in due:
            if now - reminder.due <= MISSED_GRACE_S or reminder.recurrence != "once":
                self.notify(
                    reminder.title, reminder.message or tr("reminder.default_text"), "reminders"
                )
            mark_fired(conn, reminder, now)
        self._update_tray()

    def report_missed(self) -> None:
        from desktop_organizer.tools.reminders import SETTINGS as REMINDER_SETTINGS
        from desktop_organizer.tools.reminders.logic import due_now, mark_fired

        if not tool_settings.values(self.context.settings, "reminders", REMINDER_SETTINGS)[
            "show_missed"
        ]:
            return
        conn = self.context.database.connection
        now = time.time()
        missed = [r for r in due_now(conn, now) if now - r.due > MISSED_GRACE_S]
        if missed:
            names = ", ".join(r.title for r in missed[:3])
            self.notify(tr("reminder.missed", count=len(missed)), names, "reminders")
            for reminder in missed:
                mark_fired(conn, reminder, now)

    # -- clipboard ----------------------------------------------------------------------------

    def _clipboard_changed(self) -> None:
        if not self.context.settings.get("clipboard_monitoring"):
            return
        from desktop_organizer.tools.clipboard_history import SETTINGS as CLIP_SETTINGS
        from desktop_organizer.tools.clipboard_history.logic import (
            HISTORY_FLAG,
            add,
            is_excluded_app,
            is_sensitive,
        )

        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        if mime is None or not mime.hasText():
            return
        options = tool_settings.values(self.context.settings, "clipboard_history", CLIP_SETTINGS)
        formats = list(mime.formats())
        flag_format = next((f for f in formats if HISTORY_FLAG in f), None)
        flag = bytes(mime.data(flag_format).data()) if flag_format else None
        if options["ignore_sensitive"] and is_sensitive(formats, flag):
            return
        app = foreground_app()
        if is_excluded_app(app, options["excluded_apps"]):
            return
        text = mime.text()
        if len(text.encode("utf-8")) > options["max_length_kb"] * 1024:
            return
        try:
            add(self.context.database.connection, text, options["max_entries"], app)
        except Exception:
            log.exception("Could not store clipboard entry")

    # -- global shortcuts and autostart --------------------------------------------------------

    def apply_hotkeys(self) -> None:
        self.hotkeys.unregister_all()
        self.hotkey_errors = {}
        settings = self.context.settings
        if not settings.get("hotkeys_enabled"):
            return
        bindings = {
            "hotkey_quick_note": lambda: self.window.launch("notes", ["--message", "new"]),
            "hotkey_clipboard": lambda: self.window.launch("clipboard_history"),
            "hotkey_password": lambda: self.window.launch("password_generator"),
        }
        for key, callback in bindings.items():
            error = self.hotkeys.register(str(settings.get(key)), callback)
            if error:
                self.hotkey_errors[key] = error

    def sync_autostart(self) -> None:
        wanted = bool(self.context.settings.get("autostart"))
        if not autostart.supported():
            return
        try:
            if autostart.is_enabled() != wanted:
                autostart.set_enabled(wanted)
            elif wanted:
                autostart.set_enabled(True)  # refresh the path after an update or move
        except OSError:
            log.exception("Could not change autostart")
