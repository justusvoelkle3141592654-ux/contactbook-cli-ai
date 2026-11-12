import os
from pathlib import Path

import pytest

from desktop_organizer.core.jobs import Cancelled, Job
from desktop_organizer.tools.duplicate_finder.logic import (
    Group,
    Options,
    export_csv,
    files_to_remove,
    groups_fully_selected,
    move_to,
    parse_extensions,
    scan,
)


def write(path: Path, data: bytes, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    big = os.urandom(300_000)
    write(tmp_path / "a" / "photo.jpg", big, 1000)
    write(tmp_path / "b" / "photo copy.jpg", big, 2000)
    write(tmp_path / "b" / "deep" / "photo.jpg", big, 3000)
    write(tmp_path / "a" / "other.jpg", big[:-1] + b"X")  # same size, different end
    write(tmp_path / "a" / "note.txt", b"hello")
    write(tmp_path / "b" / "note.txt", b"hello")
    write(tmp_path / "b" / "empty1.txt", b"")
    write(tmp_path / "b" / "empty2.txt", b"")
    return tmp_path


def test_content_scan_finds_real_duplicates_only(tree: Path) -> None:
    result = scan([tree / "a", tree / "b"], Options(min_size=1))
    sets = sorted(sorted(e.path.name for e in g.files) for g in result.groups)
    assert sets == [["note.txt", "note.txt"], ["photo copy.jpg", "photo.jpg", "photo.jpg"]]
    assert result.groups[0].wasted == 600_000  # sorted by space to gain


def test_min_size_and_extension_filters(tree: Path) -> None:
    only_big = scan([tree], Options(min_size=1000))
    assert len(only_big.groups) == 1
    only_txt = scan([tree], Options(min_size=1, include_extensions=frozenset({"txt"})))
    assert [g.files[0].path.suffix for g in only_txt.groups] == [".txt"]
    no_txt = scan([tree], Options(min_size=1, exclude_extensions=frozenset({"txt"})))
    assert all(g.files[0].path.suffix == ".jpg" for g in no_txt.groups)


def test_overlapping_folders_count_each_file_once(tree: Path) -> None:
    result = scan([tree, tree / "a"], Options(min_size=1000))
    assert len(result.groups[0].files) == 3


def test_name_and_size_method(tree: Path) -> None:
    result = scan([tree], Options(method="name_size", min_size=1000))
    assert sorted(len(g.files) for g in result.groups) == [2]  # photo.jpg twice


def test_excluded_folder_names(tree: Path) -> None:
    result = scan([tree], Options(min_size=1000, exclude_folders=frozenset({"deep"})))
    assert len(result.groups[0].files) == 2


def test_rules_keep_exactly_one(tree: Path) -> None:
    group = scan([tree / "a", tree / "b"], Options(min_size=1000)).groups[0]
    keep_newest = {e.path for e in group.files} - {e.path for e in files_to_remove(group, "newest")}
    assert [p.name for p in keep_newest] == ["photo.jpg"] and "deep" in str(next(iter(keep_newest)))
    keep_oldest = {e.path for e in group.files} - {e.path for e in files_to_remove(group, "oldest")}
    assert next(iter(keep_oldest)).parent.name == "a"
    keep_first = {e.path for e in group.files} - {
        e.path for e in files_to_remove(group, "first_folder")
    }
    assert next(iter(keep_first)).parent.name == "a"
    for rule in ("shortest_path", "longest_path"):
        assert len(files_to_remove(group, rule)) == 2


def test_fully_selected_groups_are_detected(tree: Path) -> None:
    groups = scan([tree], Options(min_size=1000)).groups
    every = {e.path for e in groups[0].files}
    assert groups_fully_selected(groups, every) == groups[:1]
    assert groups_fully_selected(groups, set(list(every)[:1])) == []


def test_move_and_export(tree: Path, tmp_path: Path) -> None:
    groups = scan([tree], Options(min_size=1000)).groups
    remove = files_to_remove(groups[0], "oldest")
    result = move_to(remove, tmp_path / "dupes")
    assert result.done == 2 and len(list((tmp_path / "dupes").iterdir())) == 2
    report = tmp_path / "report.csv"
    export_csv(groups, report, {remove[0].path})
    text = report.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == "group;path;size_bytes;modified;selected"
    assert text.count(";yes") == 1


def test_cancel_stops_scan(tree: Path) -> None:
    job = Job()
    job.cancel()
    with pytest.raises(Cancelled):
        scan([tree], Options(min_size=1), job)


def test_parse_extensions() -> None:
    assert parse_extensions(" .JPG, png;*.pdf ,") == frozenset({"jpg", "png", "pdf"})


def test_group_wasted() -> None:
    assert Group(10, [object(), object(), object()]).wasted == 20  # type: ignore[list-item]
