from pathlib import Path

from desktop_organizer.tools.file_size.logic import analyze, find_node


def test_sizes_roll_up(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "x.bin").write_bytes(b"1" * 100)
    (tmp_path / "a" / "b" / "y.bin").write_bytes(b"1" * 300)
    (tmp_path / "z.txt").write_bytes(b"1" * 50)
    (tmp_path / ".hidden").write_bytes(b"1" * 1000)
    result = analyze(tmp_path, include_hidden=False, top_files=2)
    assert result.root.size == 450
    assert result.root.files == 3
    a = find_node(result.root, tmp_path / "a")
    assert a is not None and a.size == 400 and a.own_files_size == 100
    assert [Path(p).name for _s, p, _m in result.largest] == ["y.bin", "x.bin"]
    assert result.types[".bin"] == (2, 400)
    assert analyze(tmp_path, include_hidden=True).root.size == 1450


def test_find_node_returns_none_outside(tmp_path: Path) -> None:
    result = analyze(tmp_path)
    assert find_node(result.root, tmp_path.parent) is None
