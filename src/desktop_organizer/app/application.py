"""Start-up for the main window (``DesktopOrganizer.exe``) and for single tools
(``DesktopOrganizer.exe --tool <id>``), which run as separate processes."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import traceback

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from desktop_organizer import APP_ID, APP_NAME, __version__
from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.settings_sync import SettingsSync
from desktop_organizer.app.single_instance import SingleInstance
from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.core import errors, logging_setup
from desktop_organizer.core.i18n import Translator, install, resolve_language, tr
from desktop_organizer.core.paths import executable_dir, resolve_paths, resources_dir
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database
from desktop_organizer.tools.registry import all_migrations, all_tools, i18n_files

log = logging.getLogger(__name__)

SMOKE_TEST_DELAY_MS = 1500


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_ID, add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--tool", default=None)
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--message", default="activate")
    args, _unknown = parser.parse_known_args(argv[1:])
    return args


def _report_error(context: AppContext) -> errors.Reporter:
    def report(exc: BaseException) -> None:
        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(tr("error.title"))
        box.setText(tr("error.title"))
        box.setInformativeText(tr("error.body", error=str(exc) or type(exc).__name__))
        logs = QPushButton(tr("error.open_logs"))
        box.addButton(logs, QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr("error.close"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is logs:
            dialogs.open_folder(None, context.paths.log_dir)

    return report


def bootstrap(argv: list[str]) -> tuple[QApplication, AppContext] | int:
    """Shared start-up: paths, logging, Qt, settings, language, theme, database."""
    paths = resolve_paths(exe_dir=executable_dir())
    paths.ensure()
    log_file = logging_setup.configure(paths.log_dir)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setWindowIcon(QIcon(str(resources_dir() / "app.ico")))
    app.setProperty("systemLocale", QLocale.system().name())

    tools = all_tools()
    settings = Settings(paths.settings_file)
    settings.load()
    translator = Translator(
        resources_dir() / "i18n",
        resolve_language(settings.get("language"), QLocale.system().name()),
        i18n_files(tools),
    )
    install(translator)
    theme = ThemeManager(app, settings.get("theme"))

    try:
        database = Database(paths.database_file)
        database.migrate(all_migrations(tools))
    except Exception as exc:  # noqa: BLE001 - shown, then exit
        log.exception("Opening the database failed")
        dialogs.critical(
            None,
            tr("error.database_title"),
            tr("error.database", error=str(exc), path=str(paths.database_file)),
        )
        return 1

    context = AppContext(paths, settings, translator, database, theme, str(log_file), tools)
    errors.install_hooks(_report_error(context))

    sync = SettingsSync(settings)
    app.setProperty("settingsSync", id(sync))
    app._settings_sync = sync  # type: ignore[attr-defined]  # keep alive with the app

    def follow(key: str, value: object) -> None:
        if key == "language" and isinstance(value, str):
            translator.set_language(resolve_language(value, QLocale.system().name()))
        elif key == "theme" and isinstance(value, str) and value != theme.mode:
            theme.set_mode(value)

    settings.subscribe(follow)
    return app, context


def run_tool(app: QApplication, context: AppContext, tool_id: str, smoke: bool, message: str) -> int:
    spec = next((t for t in context.tools if t.id == tool_id), None)
    if spec is None or spec.factory is None:
        log.error("Unknown tool %r", tool_id)
        return 2
    instance = SingleInstance(f"{APP_ID}-{context.paths.data_dir}-tool-{tool_id}")
    if not smoke and not instance.acquire(message):
        return 0
    window = spec.factory(context)
    handler = getattr(window, "handle_message", None)

    def on_message(text: str) -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()
        if callable(handler):
            handler(text)

    instance.message_received.connect(on_message)
    window.show()
    if callable(handler) and message != "activate":
        handler(message)
    if smoke:
        QTimer.singleShot(SMOKE_TEST_DELAY_MS, lambda: (window.close(), app.exit(0)))
    code = app.exec()
    log.info("Tool %s exited with code %s", tool_id, code)
    return code


def run_main(app: QApplication, context: AppContext, args: argparse.Namespace) -> int:
    from desktop_organizer.app.overview import OverviewWindow
    from desktop_organizer.app.services import BackgroundServices

    instance = SingleInstance(f"{APP_ID}-{context.paths.data_dir}")
    if not args.smoke_test and not instance.acquire(args.message):
        log.info("Another instance is running; forwarded %r", args.message)
        return 0

    window = OverviewWindow(context, context.tools)
    services = BackgroundServices(context, window)
    window.services = services

    def on_message(text: str) -> None:
        if text.startswith("tool:"):
            window.launch(text.removeprefix("tool:"))
            return
        window.bring_to_front()

    instance.message_received.connect(on_message)
    if args.minimized and context.settings.get("run_in_background"):
        log.info("Started minimized to the notification area")
    else:
        window.show()
    services.start()

    if args.smoke_test:
        QTimer.singleShot(SMOKE_TEST_DELAY_MS, lambda: _run_smoke_test(window, context))

    code = app.exec()
    services.stop()
    return code


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    booted = bootstrap(argv)
    if isinstance(booted, int):
        return booted
    app, context = booted
    log.info(
        "Starting %s %s (portable=%s, tool=%s)",
        APP_NAME,
        __version__,
        context.paths.portable,
        args.tool,
    )
    try:
        if args.tool:
            code = run_tool(app, context, args.tool, args.smoke_test, args.message)
        else:
            code = run_main(app, context, args)
    finally:
        # The database may already be closed after "Delete all data".
        with contextlib.suppress(Exception):
            context.database.close()
    log.info("Exited with code %s", code)
    return code


def _run_smoke_test(window: object, context: AppContext) -> None:
    """Open the main pages and every tool window once (in-process), then exit."""
    from desktop_organizer.app.overview import OverviewWindow

    assert isinstance(window, OverviewWindow)
    try:
        window.search.setText("x")
        window.search.clear()
        window.show_category("files")
        assert window.visible_tool_ids(), "no tools listed"
        window.show_settings()
        assert window.pages.currentWidget() is window.settings_page
        window.show_category("all")
        for spec in context.tools:
            assert spec.factory is not None, f"{spec.id} has no window"
            tool_window = spec.factory(context)
            tool_window.show()
            QApplication.processEvents()
            tool_window.close()
            log.info("Smoke test: %s window OK", spec.id)
        log.info("SMOKE TEST OK")
        QApplication.exit(0)
    except Exception:  # noqa: BLE001
        log.error("SMOKE TEST FAILED\n%s", traceback.format_exc())
        QApplication.exit(1)


def run() -> int:
    """Entry point for the installed ``desktop-organizer`` command."""
    return main(sys.argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
