import sqlite3
from pathlib import Path

import pytest

from desktop_organizer.core.storage import Database
from desktop_organizer.tools.notes.logic import (
    MIGRATIONS,
    all_tags,
    create,
    delete,
    fts_query,
    get,
    parse_tags,
    search,
    set_pinned,
    to_markdown,
    update,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = Database(tmp_path / "t.db")
    db.migrate(MIGRATIONS)
    return db.connection


def test_create_search_update_delete(conn: sqlite3.Connection) -> None:
    a = create(conn, "Einkauf", "Milch und Brötchen", ["privat"])
    b = create(conn, "Projekt", "Angebot schreiben", ["Arbeit", "projekt"])
    assert [n.id for n in search(conn, "brötch")] == [a]
    assert [n.id for n in search(conn, "angebot schr")] == [b]
    assert search(conn, "nichtvorhanden") == []
    assert [n.id for n in search(conn, tag="arbeit")] == [b]
    update(conn, a, "Einkauf", "Kaffee", ["privat"])
    assert search(conn, "milch") == []
    assert [n.id for n in search(conn, "kaffee")] == [a]
    delete(conn, a)
    assert get(conn, a) is None and search(conn, "kaffee") == []


def test_pinned_first_and_tags(conn: sqlite3.Connection) -> None:
    first = create(conn, "A", "")
    second = create(conn, "B", "", ["x", "Y"])
    set_pinned(conn, first, True)
    assert [n.id for n in search(conn)] == [first, second]
    assert all_tags(conn) == ["x", "Y"]


def test_query_is_safe_for_special_characters(conn: sqlite3.Connection) -> None:
    create(conn, "C++ und \"Zitate\"", "a AND b OR (c)")
    assert fts_query('"AND" OR (') == '"AND"* "OR"*'
    assert len(search(conn, 'and (c) "zitate')) == 1


def test_helpers() -> None:
    assert parse_tags("#a, b;b , ,c") == ["a", "b", "c"]
    note = type("N", (), {"display_title": "T", "body": "Text", "tags": ["x"]})()
    assert to_markdown(note).startswith("# T\n\nText")  # type: ignore[arg-type]
