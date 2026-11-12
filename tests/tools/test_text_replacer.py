import os
from pathlib import Path

import pytest

from desktop_organizer.tools.text_replacer.logic import (
    Options,
    apply,
    compile_pattern,
    latest_journal,
    parse_patterns,
    preview,
    undo,
)


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("Hallo Welt\nwelt am Ende\nWeltall\n", encoding="utf-8")
    (tmp_path / "sub" / "b.txt").write_bytes("Grüße an die Welt\r\n".encode("cp1252"))
    (tmp_path / "bom.txt").write_bytes(b"\xef\xbb\xbfWelt mit BOM")
    (tmp_path / "bin.txt").write_bytes(b"Welt\x00\x01")
    (tmp_path / "skip.md").write_text("Welt", encoding="utf-8")
    return tmp_path


def opts(**kw: object) -> Options:
    base = {"find": "Welt", "replace": "Erde", "patterns": ("*.txt",)}
    base.update(kw)
    return Options(**base)  # type: ignore[arg-type]


def test_preview_counts_and_skips_binary(folder: Path) -> None:
    result = preview(folder, opts())
    counts = {f.path.name: f.count for f in result.files}
    assert counts == {"a.txt": 3, "b.txt": 1, "bom.txt": 1}
    assert result.skipped_binary == 1
    a = next(f for f in result.files if f.path.name == "a.txt")
    assert [c.number for c in a.lines] == [1, 2, 3]
    assert a.lines[0].after == "Hallo Erde"


def test_case_and_whole_word(folder: Path) -> None:
    case = preview(folder, opts(case_sensitive=True))
    assert {f.path.name: f.count for f in case.files}["a.txt"] == 2
    word = preview(folder, opts(whole_word=True))
    assert {f.path.name: f.count for f in word.files}["a.txt"] == 2  # not "Weltall"


def test_regex_with_groups_and_literal_backslashes(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("2026-11-12", encoding="utf-8")
    result = preview(tmp_path, opts(find=r"(\d+)-(\d+)-(\d+)", replace=r"\3.\2.\1", regex=True))
    assert result.files[0].lines[0].after == "12.11.2026"
    literal = preview(tmp_path, opts(find="11", replace=r"\1"))
    assert literal.files[0].lines[0].after == r"2026-\1-12"


def test_apply_keeps_encoding_newlines_and_undo_restores(folder: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    result = preview(folder, opts())
    applied = apply(result.files, opts(), backups)
    assert applied.files == 3 and applied.replacements == 5
    assert (folder / "sub" / "b.txt").read_bytes() == "Grüße an die Erde\r\n".encode("cp1252")
    assert (folder / "bom.txt").read_bytes() == b"\xef\xbb\xbfErde mit BOM"
    journal = latest_journal(backups)
    assert journal is not None
    restored, failed = undo(journal)
    assert restored == 3 and failed == []
    assert (folder / "a.txt").read_text(encoding="utf-8").startswith("Hallo Welt")
    assert latest_journal(backups) is None


def test_files_changed_after_preview_are_skipped(folder: Path, tmp_path: Path) -> None:
    result = preview(folder, opts())
    target = folder / "a.txt"
    target.write_text("Welt geändert, länger als vorher", encoding="utf-8")
    os.utime(target, (1, 1))
    applied = apply(result.files, opts(), tmp_path / "b")
    assert (target, "changed") in applied.failed


def test_invalid_input() -> None:
    with pytest.raises(ValueError):
        compile_pattern(opts(find=""))
    assert parse_patterns(" *.txt ; *.md,") == ("*.txt", "*.md")
