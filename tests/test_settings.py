import json
from pathlib import Path

import pytest

from desktop_organizer.core.settings import DEFAULTS, SCHEMA_VERSION, Settings


def test_defaults_when_missing(tmp_path: Path) -> None:
    s = Settings(tmp_path / "settings.json")
    s.load()
    assert s.get("language") == "system"
    assert s.get("theme") == "system"


def test_round_trip_and_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    s.set("theme", "dark")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["theme"] == "dark"
    again = Settings(path)
    again.load()
    assert again.get("theme") == "dark"


def test_invalid_values_rejected(tmp_path: Path) -> None:
    s = Settings(tmp_path / "settings.json")
    s.load()
    with pytest.raises(ValueError):
        s.set("theme", "purple")
    with pytest.raises(KeyError):
        s.set("unknown", 1)


def test_invalid_values_in_file_fall_back(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 1, "theme": "purple", "language": "de"}))
    s = Settings(path)
    s.load()
    assert s.get("theme") == DEFAULTS["theme"]
    assert s.get("language") == "de"


def test_corrupt_file_is_kept_and_defaults_used(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    s = Settings(path)
    s.load()
    assert s.get("theme") == "system"
    assert not path.exists()
    assert len(list(tmp_path.glob("settings.json.broken-*"))) == 1


def test_newer_schema_is_not_overwritten_silently(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": SCHEMA_VERSION + 1}))
    s = Settings(path)
    s.load()
    assert len(list(tmp_path.glob("settings.json.broken-*"))) == 1


def test_listeners_and_no_save_after_disable(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    seen: list[tuple[str, object]] = []
    s.subscribe(lambda k, v: seen.append((k, v)))
    s.set("language", "en")
    s.set("language", "en")  # unchanged: no second notification
    assert seen == [("language", "en")]
    path.unlink()
    s.disable_saving()
    s.set("language", "de")
    assert not path.exists()
