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
    yield AppContext(paths, settings, translator, db, theme, str(paths.log_dir / "x.log"))  # type: ignore[arg-type]
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
    assert window.stack.currentWidget() is window.empty
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


def test_settings_dialog_changes_theme_and_language(context: object) -> None:
    from desktop_organizer.app.settings_dialog import SettingsDialog

    dialog = SettingsDialog(context)  # type: ignore[arg-type]
    dialog.theme.setCurrentIndex(dialog.theme.findData("dark"))
    assert context.settings.get("theme") == "dark"  # type: ignore[attr-defined]
    assert context.theme.tokens.window == "#1C1C1C"  # type: ignore[attr-defined]
    dialog.language.setCurrentIndex(dialog.language.findData("de"))
    assert context.translator.language == "de"  # type: ignore[attr-defined]
    assert dialog.close_button.text() == "Schließen"
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    dialog.accept()


def test_every_icon_renders(context: object) -> None:
    for spec in all_tools():
        icon = context.theme.icon(spec.icon)  # type: ignore[attr-defined]
        assert not icon.pixmap(20, 20).isNull()
