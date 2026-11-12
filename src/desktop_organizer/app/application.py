"""Start-up sequence."""

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
from desktop_organizer.app.overview import OverviewWindow
from desktop_organizer.app.single_instance import SingleInstance
from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.core import errors, logging_setup
from desktop_organizer.core.i18n import Translator, install, resolve_language, tr
from desktop_organizer.core.paths import executable_dir, resolve_paths, resources_dir
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database
from desktop_organizer.tools.registry import all_tools

log = logging.getLogger(__name__)

SMOKE_TEST_DELAY_MS = 1500


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_ID, add_help=False)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Start, open every shell window once, exit with code 0 on success.",
    )
    args, _unknown = parser.parse_known_args(argv[1:])
    return args


def _report_error(context: AppContext | None) -> errors.Reporter:
    def report(exc: BaseException) -> None:
        app = QApplication.instance()
        if app is None or context is None:
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


def main(argv: list[str]) -> int:
    args = _parse(argv)
    paths = resolve_paths(exe_dir=executable_dir())
    paths.ensure()
    log_file = logging_setup.configure(paths.log_dir)
    log.info("Starting %s %s (portable=%s)", APP_NAME, __version__, paths.portable)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setWindowIcon(QIcon(str(resources_dir() / "app.ico")))
    app.setProperty("systemLocale", QLocale.system().name())

    instance = SingleInstance(f"{APP_ID}-{paths.data_dir}")
    if not args.smoke_test and not instance.acquire():
        log.info("Another instance is running; asked it to come to the front")
        return 0

    settings = Settings(paths.settings_file)
    settings.load()
    translator = Translator(
        resources_dir() / "i18n",
        resolve_language(settings.get("language"), QLocale.system().name()),
    )
    install(translator)
    theme = ThemeManager(app, settings.get("theme"))

    try:
        database = Database(paths.database_file)
        database.migrate([])  # Tool migrations are registered as tools are added.
    except Exception as exc:
        log.exception("Opening the database failed")
        dialogs.critical(
            None,
            tr("error.database_title"),
            tr("error.database", error=str(exc), path=str(paths.database_file)),
        )
        return 1

    context = AppContext(paths, settings, translator, database, theme, str(log_file))
    errors.install_hooks(_report_error(context))

    window = OverviewWindow(context, all_tools())

    def bring_to_front() -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()

    instance.activated.connect(bring_to_front)
    window.show()

    if args.smoke_test:
        QTimer.singleShot(SMOKE_TEST_DELAY_MS, lambda: _run_smoke_test(window))

    code = app.exec()
    # The database may already be closed after "Delete all data".
    with contextlib.suppress(Exception):
        database.close()
    log.info("Exited with code %s", code)
    return code


def _run_smoke_test(window: OverviewWindow) -> None:
    try:
        window.search.setText("x")
        window.search.clear()
        window.show_category("files")
        assert window.visible_tool_ids(), "no tools listed"
        window.show_settings()
        assert window.pages.currentWidget() is window.settings_page
        window.show_category("all")
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
