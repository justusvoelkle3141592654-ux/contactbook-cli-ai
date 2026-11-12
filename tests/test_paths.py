from pathlib import Path

from desktop_organizer.core.paths import DATA_DIR_ENV, resolve_paths


def test_windows_uses_appdata() -> None:
    paths = resolve_paths({"APPDATA": r"C:\Users\a\AppData\Roaming"}, None, "win32")
    assert paths.data_dir == Path(r"C:\Users\a\AppData\Roaming") / "DesktopOrganizer"
    assert not paths.portable


def test_portable_when_data_folder_next_to_exe(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    paths = resolve_paths({"APPDATA": "x"}, tmp_path, "win32")
    assert paths.portable
    assert paths.data_dir == tmp_path / "data"


def test_not_portable_without_data_folder(tmp_path: Path) -> None:
    paths = resolve_paths({"APPDATA": str(tmp_path / "roaming")}, tmp_path, "win32")
    assert not paths.portable


def test_environment_override_wins(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    paths = resolve_paths({DATA_DIR_ENV: str(tmp_path / "custom")}, tmp_path, "win32")
    assert paths.data_dir == tmp_path / "custom"


def test_ensure_creates_folders(tmp_path: Path) -> None:
    paths = resolve_paths({DATA_DIR_ENV: str(tmp_path / "d")}, None, "win32")
    paths.ensure()
    assert paths.log_dir.is_dir()
    assert paths.settings_file.parent == paths.data_dir
