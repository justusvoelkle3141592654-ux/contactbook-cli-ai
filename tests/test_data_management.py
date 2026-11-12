import zipfile
from pathlib import Path

from desktop_organizer.core.data_management import delete_all_data, export_data
from desktop_organizer.core.paths import AppPaths
from desktop_organizer.core.settings import Settings
from desktop_organizer.core.storage import Database, Migration


def _setup(tmp_path: Path, portable: bool = False) -> tuple[AppPaths, Database]:
    paths = AppPaths(tmp_path / "data", portable=portable)
    paths.ensure()
    s = Settings(paths.settings_file)
    s.load()
    s.set("theme", "dark")
    db = Database(paths.database_file)
    db.migrate([Migration("t", 1, ("CREATE TABLE t (v TEXT)",))])
    db.connection.execute("INSERT INTO t VALUES ('x')")
    (paths.log_dir / "desktop-organizer.log").write_text("log", encoding="utf-8")
    return paths, db


def test_export_contains_settings_and_database(tmp_path: Path) -> None:
    paths, db = _setup(tmp_path)
    target = tmp_path / "export with spaces ü.zip"
    names = export_data(paths, db, target)
    db.close()
    assert set(names) == {"settings.json", "organizer.db"}
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {"settings.json", "organizer.db"}
        archive.extract("organizer.db", tmp_path / "out")
    copy = Database(tmp_path / "out" / "organizer.db")
    assert copy.connection.execute("SELECT v FROM t").fetchone()[0] == "x"
    copy.close()
    assert not (tmp_path / "export with spaces ü.zip.tmp").exists()


def test_delete_all_data_removes_folder(tmp_path: Path) -> None:
    paths, db = _setup(tmp_path)
    db.close()
    delete_all_data(paths)
    assert not paths.data_dir.exists()


def test_delete_all_data_keeps_portable_marker(tmp_path: Path) -> None:
    paths, db = _setup(tmp_path, portable=True)
    db.close()
    delete_all_data(paths)
    assert paths.data_dir.is_dir()
    assert list(paths.data_dir.iterdir()) == []
