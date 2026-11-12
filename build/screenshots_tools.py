"""Render screenshots of tool windows with sample data (offscreen).

QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 python build/screenshots_tools.py [tool_id ...]
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "docs" / "images"


def sample_folder() -> Path:
    base = Path(tempfile.mkdtemp()) / "Downloads"
    base.mkdir()
    old = time.time() - 86400 * 3
    data = os.urandom(200_000)
    files = {
        "Rechnung_2026-10.pdf": b"%PDF" + data[:5000],
        "IMG_4021.jpg": data,
        "IMG_4021 (1).jpg": data,
        "Präsentation Q3.pptx": data[:90000],
        "setup-tool-2.4.1.exe": data[:150000],
        "Urlaub Kroatien.mp4": data * 3,
        "daten-export.csv": b"a;b\n1;2\n",
        "Projektplan.xlsx": data[:41000],
        "archiv_alt.zip": data[:120000],
        "Sprachmemo 12.m4a": data[:60000],
        "notizen.txt": b"Notizen",
    }
    for name, content in files.items():
        path = base / name
        path.write_bytes(content)
        os.utime(path, (old, old))
    (base / "Fotos").mkdir()
    (base / "Fotos" / "IMG_4021.jpg").write_bytes(data)
    (base / "Fotos" / "Urlaub.mp4").write_bytes(data * 3)
    return base


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.theming import ThemeManager
    from desktop_organizer.core.i18n import Translator, install
    from desktop_organizer.core.paths import AppPaths, resources_dir
    from desktop_organizer.core.settings import Settings
    from desktop_organizer.core.storage import Database
    from desktop_organizer.tools.registry import all_migrations, all_tools, i18n_files

    wanted = set(sys.argv[1:])
    mode = os.environ.get("THEME", "light")
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
    theme = ThemeManager(app, mode)
    context = AppContext(paths, settings, translator, db, theme, "", tools)
    folder = sample_folder()
    settings.set_tool_value("file_cleaner", "last_folder", str(folder))
    settings.set_tool_value("duplicate_finder", "folders", [str(folder)])
    settings.set_tool_value("duplicate_finder", "min_size_kb", 1)
    settings.set_tool_value("file_size", "last_folder", str(folder))
    settings.set_tool_value("text_replacer", "last_folder", str(folder))
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in tools:
        if wanted and spec.id not in wanted:
            continue
        assert spec.factory is not None
        window = spec.factory(context)
        window.resize(1180, 760)
        window.show()
        prepare = getattr(window, "screenshot_prepare", None)
        if callable(prepare):
            prepare()
        deadline = time.time() + 5
        while time.time() < deadline:
            app.processEvents()
            if not window.busy:
                time.sleep(0.05)
                app.processEvents()
                if not window.busy:
                    break
            time.sleep(0.02)
        app.processEvents()
        target = OUT / f"tool-{spec.id}-{mode}.png"
        window.grab().save(str(target))
        print("Wrote", target.name)
        window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
