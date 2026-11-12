"""Smoke tests of the shell windows, run offscreen."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from desktop_organizer.core.i18n import Translator
from desktop_organizer.core.paths import AppPaths
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database
from desktop_organizer.tools.registry import all_tools


@pytest.fixture(scope="session")
def theme(qapp: object) -> object:
    from desktop_organizer.app.theming import ThemeManager

    return ThemeManager(qapp, "light")  # type: ignore[arg-type]


@pytest.fixture
def context(theme: object, tmp_path: Path, translator: Translator) -> Iterator[object]:
    from desktop_organizer.app.context import AppContext

    paths = AppPaths(tmp_path / "data", portable=False)
    paths.ensure()
    settings = Settings(paths.settings_file)
    settings.load()
    db = Database(paths.database_file)
    theme.set_mode("light")  # type: ignore[attr-defined]
    from desktop_organizer.tools.registry import all_migrations

    tools = all_tools()
    db.migrate(all_migrations(tools))
    yield AppContext(paths, settings, translator, db, theme, str(paths.log_dir / "x.log"), tools)  # type: ignore[arg-type]
    db.close()


def test_overview_lists_all_tools_and_filters(context: object) -> None:
    from desktop_organizer.app.overview import OverviewWindow

    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    window.show()
    assert len(window.visible_tool_ids()) == 12
    window.search.setText("password")
    assert window.visible_tool_ids() == ["password_generator"]
    window.search.setText("zzzz")
    assert window.visible_tool_ids() == []
    assert window.tools_page.empty.isVisibleTo(window)
    assert window.tools_page.title.text() == "Results for “zzzz”"
    window.search.clear()
    assert len(window.visible_tool_ids()) == 12
    window.close()


def test_overview_retranslates_live(context: object) -> None:
    from desktop_organizer.app.overview import OverviewWindow

    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    context.translator.set_language("de")  # type: ignore[attr-defined]
    assert window.search.placeholderText() == "Werkzeuge suchen"
    window.search.setText("Passwort")
    assert window.visible_tool_ids() == ["password_generator"]
    context.translator.set_language("en")  # type: ignore[attr-defined]
    window.close()


def test_settings_page_changes_theme_and_language(context: object) -> None:
    from desktop_organizer.app.overview import OverviewWindow

    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    window.show_settings()
    page = window.settings_page
    assert window.pages.currentWidget() is page
    assert window.nav_settings.isChecked()
    page.theme.setCurrentIndex(page.theme.findData("dark"))
    assert context.settings.get("theme") == "dark"  # type: ignore[attr-defined]
    assert context.theme.tokens.window == "#1F1F1F"  # type: ignore[attr-defined]
    page.language.setCurrentIndex(page.language.findData("de"))
    assert context.translator.language == "de"  # type: ignore[attr-defined]
    assert page.title.text() == "Einstellungen"
    assert window.nav_all.text() == "Alle Werkzeuge"
    page.language.setCurrentIndex(page.language.findData("en"))
    page.theme.setCurrentIndex(page.theme.findData("light"))
    window.close()


def test_category_navigation_filters_tools(context: object) -> None:
    from desktop_organizer.app.overview import OverviewWindow

    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    window.show_category("files")
    assert window.visible_tool_ids() == [
        "file_cleaner",
        "duplicate_finder",
        "file_size",
        "text_replacer",
    ]
    assert window.tools_page.title.text() == "Files"
    window.show_category("system")
    assert window.visible_tool_ids() == ["system_monitor", "clipboard_history"]
    window.show_category("all")
    assert len(window.visible_tool_ids()) == 12
    window.close()


def test_cards_launch_tools_as_separate_processes(context: object, monkeypatch: object) -> None:
    from desktop_organizer.app import launcher
    from desktop_organizer.app.overview import OverviewWindow

    started: list[tuple[str, object]] = []
    monkeypatch.setattr(
        launcher, "launch_tool", lambda tool, extra=None: started.append((tool, extra)) or True
    )  # type: ignore[attr-defined]
    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    cards = window.tools_page.cards()
    assert cards and all(card.available for card in cards)
    cards[0].click()
    assert started == [("file_cleaner", None)]
    assert context.settings.get("recent_tools")[0] == "file_cleaner"  # type: ignore[attr-defined]
    window.close()


def test_launch_command_uses_tool_argument() -> None:
    from desktop_organizer.app.launcher import command

    program, args = command("notes", ["--message", "new"])
    assert args[-4:] == ["--tool", "notes", "--message", "new"]


def test_settings_page_lists_every_tool(context: object) -> None:
    from desktop_organizer.app.settings_page import SettingsPage

    page = SettingsPage(context)  # type: ignore[arg-type]
    assert len(page.tool_cards) == len(all_tools())
    page.background_switch.click()
    assert context.settings.get("run_in_background") is True  # type: ignore[attr-defined]
    page.background_switch.click()


@pytest.mark.parametrize("tool_id", [s.id for s in all_tools()])
def test_every_tool_window_opens(context: object, tool_id: str) -> None:
    spec = next(s for s in all_tools() if s.id == tool_id)
    assert spec.factory is not None
    window = spec.factory(context)  # type: ignore[arg-type]
    window.show()
    assert callable(window.open_settings)
    window.close()


def test_every_icon_renders(context: object) -> None:
    for spec in all_tools():
        icon = context.theme.icon(spec.icon)  # type: ignore[attr-defined]
        assert not icon.pixmap(20, 20).isNull()


def test_every_icon_name_in_the_shell_exists() -> None:
    import re

    from desktop_organizer.core.paths import resources_dir

    package = resources_dir().parent
    pattern = re.compile(
        r'(?:NavButton|SettingsCard|IconTile)\([^,()]+,\s*"([a-z0-9-]+)"'
        r'|Category\.\w+: "([a-z0-9-]+)"'
        r'|\.(?:icon|accent_icon)\("([a-z0-9-]+)"'
        r'|IconTile\(context\.theme, "([a-z0-9-]+)"'
        r'|EmptyState\(context\.theme, "([a-z0-9-]+)"'
    )
    names = set()
    icon_dict = re.compile(r"ICONS\s*=\s*\{([^}]*)\}", re.S)
    for file in package.rglob("*.py"):
        text = file.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            names.add(next(g for g in match.groups() if g))
        for block in icon_dict.findall(text):
            names.update(re.findall(r':\s*"([a-z0-9-]+)"', block))
    assert len(names) >= 10
    missing = sorted(n for n in names if not (resources_dir() / "icons" / f"{n}.svg").exists())
    assert missing == []


def test_arrow_keys_move_between_cards(context: object) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from desktop_organizer.app.overview import OverviewWindow

    window = OverviewWindow(context, all_tools())  # type: ignore[arg-type]
    window.resize(1080, 720)
    window.show()
    window.tools_page.focus_first_card()
    cards = window.tools_page.cards()
    assert cards[0].hasFocus() or not window.isActiveWindow()
    QTest.keyClick(cards[0], Qt.Key.Key_Right)
    if window.isActiveWindow():
        assert cards[1].hasFocus()
    window.close()
