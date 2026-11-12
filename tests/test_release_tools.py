import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, ROOT / "build" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_release_notes_extracts_one_section() -> None:
    notes = _load("release_notes")
    text = "# Changelog\n\n## [0.2.0] - x\n\nNew.\n\n## [0.1.0] - y\n\nOld.\n"
    assert notes.section(text, "0.2.0") == "New."  # type: ignore[attr-defined]
    assert notes.section(text, "0.1.0") == "Old."  # type: ignore[attr-defined]
    with pytest.raises(SystemExit):
        notes.section(text, "9.9.9")  # type: ignore[attr-defined]


def test_changelog_has_section_for_current_version() -> None:
    from desktop_organizer import __version__

    notes = _load("release_notes")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert notes.section(changelog, __version__)  # type: ignore[attr-defined]


def test_build_reads_same_version_as_app() -> None:
    from desktop_organizer import __version__

    build = _load("build")
    assert build.read_version() == __version__  # type: ignore[attr-defined]


def test_icon_contains_all_sizes() -> None:
    import struct

    data = (ROOT / "src" / "desktop_organizer" / "resources" / "app.ico").read_bytes()
    _reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert kind == 1
    sizes = {data[6 + 16 * i] or 256 for i in range(count)}
    assert {16, 24, 32, 48, 256} <= sizes
