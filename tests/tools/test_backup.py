import os
from pathlib import Path

import pytest

from desktop_organizer.tools.backup.logic import (
    BackupError,
    Options,
    load_history,
    make_plan,
    run,
    save_history,
    target_folders,
)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "Dokumente"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("a", encoding="utf-8")
    (src / "sub" / "b.txt").write_text("bb", encoding="utf-8")
    (src / "~$lock.docx").write_text("x", encoding="utf-8")
    return src


def test_first_run_copies_everything_then_nothing(source: Path, tmp_path: Path) -> None:
    dest = tmp_path / "USB"
    options = Options(verify="hash", exclude=("~$*",))
    plan = make_plan([source], dest, options)
    assert sorted(c.reason for c in plan.copies) == ["new", "new"]
    result = run(plan, options)
    assert result.ok and result.copied == 2 and result.verified == 2
    assert (dest / "Dokumente" / "sub" / "b.txt").read_text(encoding="utf-8") == "bb"
    again = make_plan([source], dest, options)
    assert again.copies == [] and again.unchanged == 2


def test_changed_files_are_copied(source: Path, tmp_path: Path) -> None:
    dest = tmp_path / "USB"
    run(make_plan([source], dest, Options()), Options())
    (source / "a.txt").write_text("changed", encoding="utf-8")
    plan = make_plan([source], dest, Options())
    assert [(c.source.name, c.reason) for c in plan.copies] == [("a.txt", "changed")]


def test_mirror_lists_deletions_and_update_never_deletes(source: Path, tmp_path: Path) -> None:
    dest = tmp_path / "USB"
    run(make_plan([source], dest, Options()), Options())
    (source / "a.txt").unlink()
    assert make_plan([source], dest, Options()).deletions == []
    mirror = make_plan([source], dest, Options(mirror=True))
    assert [p.name for p in mirror.deletions] == ["a.txt"]


def test_invalid_combinations(source: Path) -> None:
    with pytest.raises(BackupError, match="destination_inside_source"):
        make_plan([source], source / "backup", Options())
    with pytest.raises(BackupError, match="source_inside_destination"):
        make_plan([source], source.parent, Options())
    with pytest.raises(BackupError, match="no_sources"):
        make_plan([], source, Options())


def test_duplicate_source_names_get_separate_folders(tmp_path: Path) -> None:
    folders = target_folders([tmp_path / "x" / "Fotos", tmp_path / "y" / "Fotos"], tmp_path / "d")
    assert [f.name for f in folders] == ["Fotos", "Fotos (2)"]


def test_history_and_log(source: Path, tmp_path: Path) -> None:
    dest = tmp_path / "USB"
    result = run(make_plan([source], dest, Options()), Options())
    log = save_history(tmp_path / "h.json", "Profil", dest, result, tmp_path / "logs")
    assert "Copied: 3 files" in log.read_text(encoding="utf-8")
    history = load_history(tmp_path / "h.json")
    assert history[0]["profile"] == "Profil" and history[0]["errors"] == 0


def test_unreadable_target_does_not_overwrite_partial(source: Path, tmp_path: Path) -> None:
    dest = tmp_path / "USB"
    plan = make_plan([source], dest, Options())
    os.remove(source / "a.txt")  # vanished between preview and run
    result = run(plan, Options())
    assert len(result.failed) == 1 and not (dest / "Dokumente" / "a.txt").exists()
    assert not list(dest.rglob("*.do-partial"))
