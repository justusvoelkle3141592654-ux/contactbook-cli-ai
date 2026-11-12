from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_organizer.core.i18n import Translator, install
from desktop_organizer.core.paths import resources_dir


@pytest.fixture
def translator() -> Translator:
    from desktop_organizer.tools.registry import all_tools, i18n_files

    t = Translator(resources_dir() / "i18n", "en", i18n_files(all_tools()))
    install(t)
    return t


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"
