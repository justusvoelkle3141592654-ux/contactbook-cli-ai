from pathlib import Path

import pytest

from desktop_organizer.core.storage import Database, Migration, MigrationError

NOTES_V1 = Migration("notes", 1, ("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)",))
NOTES_V2 = Migration("notes", 2, ("ALTER TABLE notes ADD COLUMN created TEXT",))


def test_applies_in_order_and_only_once(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    assert db.migrate([NOTES_V2, NOTES_V1]) == [NOTES_V1, NOTES_V2]
    assert db.current_version("notes") == 2
    assert db.migrate([NOTES_V1, NOTES_V2]) == []
    db.connection.execute("INSERT INTO notes (body, created) VALUES ('a', 'b')")
    db.close()


def test_modules_are_independent(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    tasks = Migration("tasks", 1, ("CREATE TABLE tasks (id INTEGER PRIMARY KEY)",))
    db.migrate([NOTES_V1, tasks])
    assert db.current_version("notes") == 1
    assert db.current_version("tasks") == 1
    assert db.current_version("other") == 0
    db.close()


def test_gap_in_versions_is_rejected(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    with pytest.raises(MigrationError):
        db.migrate([NOTES_V2])
    db.close()


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    broken = Migration(
        "notes", 1, ("CREATE TABLE notes (id INTEGER PRIMARY KEY)", "THIS IS NOT SQL")
    )
    with pytest.raises(MigrationError):
        db.migrate([broken])
    assert db.current_version("notes") == 0
    tables = {r[0] for r in db.connection.execute("SELECT name FROM sqlite_master")}
    assert "notes" not in tables
    db.close()


def test_backup_produces_readable_copy(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    db.migrate([NOTES_V1])
    db.connection.execute("INSERT INTO notes (body) VALUES ('hello')")
    db.backup_to(tmp_path / "copy.db")
    db.close()
    copy = Database(tmp_path / "copy.db")
    assert copy.connection.execute("SELECT body FROM notes").fetchone()[0] == "hello"
    copy.close()
