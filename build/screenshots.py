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


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.overview import OverviewWindow
    from desktop_organizer.app.theming import ThemeManager
    from desktop_organizer.core.i18n import Translator, install
    from desktop_organizer.core.paths import AppPaths, resources_dir
    from desktop_organizer.core.settings import Settings
    from desktop_organizer.core.storage import Database
    from desktop_organizer.tools.registry import all_tools

    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    tmp = Path(tempfile.mkdtemp())
    paths = AppPaths(tmp / "data", portable=False)
    paths.ensure()
    settings = Settings(paths.settings_file)
    settings.load()
    translator = Translator(resources_dir() / "i18n", "de")
    install(translator)
    db = Database(paths.database_file)
    theme = ThemeManager(app, "light")
    context = AppContext(paths, settings, translator, db, theme, "")

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
