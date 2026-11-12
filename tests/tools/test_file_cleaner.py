import os
import time
from pathlib import Path

from desktop_organizer.tools.file_cleaner.logic import (
    Options,
    category_of,
    execute,
    journal_info,
    make_plan,
    undo,
)

OLD = time.time() - 3600


def make(folder: Path, name: str, content: str = "x", mtime: float = OLD) -> Path:
    path = folder / name
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_categories() -> None:
    assert category_of("Foto.JPG") == "images"
    assert category_of("bericht.pdf") == "documents"
    assert category_of("archiv.tar.gz") == "archives"
    assert category_of("noext") == "other"


def test_plan_moves_top_level_files_only(tmp_path: Path) -> None:
    make(tmp_path, "a.jpg")
    make(tmp_path, "b.pdf")
    (tmp_path / "sub").mkdir()
    make(tmp_path / "sub", "c.jpg")
    plan = make_plan(tmp_path, Options(folder_language="de"))
    targets = {m.source.name: m.target.relative_to(tmp_path) for m in plan.moves}
    assert targets == {"a.jpg": Path("Bilder/a.jpg"), "b.pdf": Path("Dokumente/b.pdf")}


def test_skips_recent_partial_hidden_and_other(tmp_path: Path) -> None:
    make(tmp_path, "new.jpg", mtime=time.time())
    make(tmp_path, "file.crdownload")
    make(tmp_path, ".hidden.jpg")
    make(tmp_path, "unknown.xyz")
    plan = make_plan(tmp_path, Options(move_other=False))
    reasons = {p.name: r for p, r in plan.skipped}
    assert reasons == {
        "new.jpg": "recent",
        "file.crdownload": "partial",
        ".hidden.jpg": "hidden",
        "unknown.xyz": "other",
    }
    assert plan.moves == []


def test_conflicts_are_renamed_or_skipped(tmp_path: Path) -> None:
    (tmp_path / "Images").mkdir()
    make(tmp_path / "Images", "a.jpg", "existing")
    make(tmp_path, "a.jpg", "new")
    renamed = make_plan(tmp_path, Options(folder_language="en"))
    assert renamed.moves[0].target.name == "a (2).jpg"
    skipped = make_plan(tmp_path, Options(folder_language="en", on_conflict="skip"))
    assert skipped.moves == [] and skipped.skipped[0][1] == "exists"


def test_date_subfolders(tmp_path: Path) -> None:
    make(tmp_path, "a.jpg", mtime=time.mktime((2024, 3, 5, 12, 0, 0, 0, 0, -1)))
    plan = make_plan(tmp_path, Options(folder_language="en", date_subfolders="year_month"))
    assert plan.moves[0].target.relative_to(tmp_path) == Path("Images/2024/03/a.jpg")


def test_execute_and_undo_restore_everything(tmp_path: Path) -> None:
    folder = tmp_path / "Downloads ü"
    folder.mkdir()
    for name in ("a.jpg", "b.pdf", "c.mp3"):
        make(folder, name, name)
    journal = tmp_path / "journal.json"
    plan = make_plan(folder, Options(folder_language="de"))
    result = execute(plan.moves, journal)
    assert result.moved == 3 and not result.failed
    assert (folder / "Bilder" / "a.jpg").read_text(encoding="utf-8") == "a.jpg"
    assert journal_info(journal)[0] == 3  # type: ignore[index]
    restored = undo(journal)
    assert restored.restored == 3
    assert sorted(p.name for p in folder.iterdir()) == ["a.jpg", "b.pdf", "c.mp3"]
    assert not journal.exists()


def test_execute_never_overwrites(tmp_path: Path) -> None:
    make(tmp_path, "a.jpg", "original")
    plan = make_plan(tmp_path, Options(folder_language="en"))
    (tmp_path / "Images").mkdir()
    make(tmp_path / "Images", "a.jpg", "appeared meanwhile")
    execute(plan.moves, tmp_path / "j.json")
    assert (tmp_path / "Images" / "a.jpg").read_text(encoding="utf-8") == "appeared meanwhile"
    assert (tmp_path / "Images" / "a (2).jpg").read_text(encoding="utf-8") == "original"
