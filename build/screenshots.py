"""Render screenshots of the shell windows for docs and design review.

Run offscreen: QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 python build/screenshots.py
Writes PNG files to docs/images/. Fonts depend on the machine: on Windows the app uses
Segoe UI Variable; elsewhere the fallback in the style sheet is used.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "docs" / "images"


def seed(conn: object) -> None:
    """Sample data so the overview's today strip shows realistic values."""
    import time

    from desktop_organizer.tools.notes.logic import create as note
    from desktop_organizer.tools.reminders.logic import create as reminder
    from desktop_organizer.tools.tasks.logic import create as task
    from desktop_organizer.tools.time_tracker.logic import ensure_project, start

    now = time.time()
    task(conn, "Angebot senden", now + 3600)  # type: ignore[arg-type]
    task(conn, "Steuerunterlagen sortieren", now + 7200)  # type: ignore[arg-type]
    task(conn, "Team-Meeting vorbereiten", now + 86400 * 2)  # type: ignore[arg-type]
    reminder(conn, "Pause", now + 35 * 60, "minutes", 50)  # type: ignore[arg-type]
    for title in ("Einkauf", "Projekt Q4", "Ideen", "Urlaub"):
        note(conn, title, "")  # type: ignore[arg-type]
    start(conn, ensure_project(conn, "Website-Relaunch"), "", now - 47 * 60)  # type: ignore[arg-type]


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.overview import OverviewWindow
    from desktop_organizer.app.theming import ThemeManager
    from desktop_organizer.core.i18n import Translator, install
    from desktop_organizer.core.paths import AppPaths, resources_dir
    from desktop_organizer.core.settings import Settings
    from desktop_organizer.core.storage import Database
    from desktop_organizer.tools.registry import all_migrations, all_tools, i18n_files

    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    tmp = Path(tempfile.mkdtemp())
    paths = AppPaths(tmp / "data", portable=False)
    paths.ensure()
    settings = Settings(paths.settings_file)
    settings.load()
    tools = all_tools()
    translator = Translator(resources_dir() / "i18n", "de", i18n_files(tools))
    install(translator)
    db = Database(paths.database_file)
    db.migrate(all_migrations(tools))
    seed(db.connection)
    theme = ThemeManager(app, "light")
    context = AppContext(paths, settings, translator, db, theme, "", tools)

    shots: list[str] = []
    window = OverviewWindow(context, all_tools())
    window.resize(1080, 720)
    window.show()
    for mode in ("light", "dark"):
        theme.set_mode(mode)
        window.show_category("all")
        window.meter_cpu.set_reading("CPU", "12\u00a0%", 0.12)
        window.meter_memory.set_reading("Arbeitsspeicher", "8,1 GB von 16,0 GB", 0.51)
        window.meter_battery.set_reading("Akku", "84\u00a0%", 0.84)
        window.meter_battery.show()
        app.processEvents()
        name = OUT / f"overview-{mode}.png"
        window.grab().save(str(name))
        shots.append(name.name)

        window.show_settings()
        window.settings_page.location_card.description.setText(
            "C:\\Users\\anna\\AppData\\Roaming\\DesktopOrganizer"
        )
        app.processEvents()
        name = OUT / f"settings-{mode}.png"
        window.grab().save(str(name))
        shots.append(name.name)

    db.close()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    print("Wrote", ", ".join(shots))
    return 0


if __name__ == "__main__":
    sys.exit(main())
