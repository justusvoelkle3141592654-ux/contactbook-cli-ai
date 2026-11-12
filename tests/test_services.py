"""Background services of the main process."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from desktop_organizer.app.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse
from desktop_organizer.core import autostart


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ctrl+Alt+N", (MOD_CONTROL | MOD_ALT, ord("N"))),
        ("Strg+Shift+F5", (MOD_CONTROL | MOD_SHIFT, 0x74)),
        ("Alt+1", (MOD_ALT, ord("1"))),
        ("Shift+A", None),
        ("N", None),
        ("Ctrl+Space", None),
        ("Hyper+N", None),
    ],
)
def test_hotkey_parsing(text: str, expected: tuple[int, int] | None) -> None:
    assert parse(text) == expected


def test_autostart_is_only_offered_for_the_packaged_windows_build() -> None:
    import sys

    assert autostart.supported() == (
        sys.platform == "win32" and bool(getattr(sys, "frozen", False))
    )
    assert "--minimized" in autostart.command()


def test_due_reminders_fire_once(qapp: object, tmp_path: Path, translator: object) -> None:
    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.services import BackgroundServices
    from desktop_organizer.app.theming import ThemeManager
    from desktop_organizer.core.paths import AppPaths
    from desktop_organizer.core.settings import Settings
    from desktop_organizer.core.storage import Database
    from desktop_organizer.tools.registry import all_migrations, all_tools
    from desktop_organizer.tools.reminders.logic import create, get

    paths = AppPaths(tmp_path / "d", portable=False)
    paths.ensure()
    settings = Settings(paths.settings_file)
    settings.load()
    db = Database(paths.database_file)
    tools = all_tools()
    db.migrate(all_migrations(tools))
    context = AppContext(paths, settings, translator, db, ThemeManager(qapp, "light"), "", tools)  # type: ignore[arg-type]

    class Window:
        def __init__(self) -> None:
            self.launched: list[str] = []

        def launch(self, tool: str, extra: object = None) -> bool:
            self.launched.append(tool)
            return True

        def bring_to_front(self) -> None:
            pass

    services = BackgroundServices(context, Window())  # type: ignore[arg-type]
    shown: list[str] = []
    services.notify = lambda title, message, open_tool=None: shown.append(title)  # type: ignore[method-assign]
    once = create(db.connection, "Jetzt", time.time() - 5)
    daily = create(db.connection, "Täglich", time.time() - 5, "daily")
    services.check_reminders()
    services.check_reminders()
    assert shown == ["Jetzt", "Täglich"]
    assert get(db.connection, once).enabled is False  # type: ignore[union-attr]
    assert get(db.connection, daily).due > time.time()  # type: ignore[union-attr]
    db.close()
