import sqlite3
from pathlib import Path

import pytest

from desktop_organizer.core import dpapi
from desktop_organizer.core.storage import Database
from desktop_organizer.tools.clipboard_history.logic import (
    MIGRATIONS,
    add,
    clear,
    entries,
    is_excluded_app,
    is_sensitive,
    set_pinned,
    state,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = Database(tmp_path / "c.db")
    db.migrate(MIGRATIONS)
    return db.connection


def test_add_dedupes_latest_and_prunes(conn: sqlite3.Connection) -> None:
    add(conn, "eins", now=1)
    add(conn, "zwei", now=2)
    add(conn, "zwei", now=3)
    assert [e.text for e in entries(conn)] == ["zwei", "eins"]
    first = entries(conn)[1]
    set_pinned(conn, first.id, True)
    for index in range(10):
        add(conn, f"x{index}", max_entries=3, now=10 + index)
    texts = [e.text for e in entries(conn)]
    assert texts[0] == "eins" and len(texts) == 4  # pinned + 3 newest
    assert add(conn, "   ") is None
    assert state(conn)[0] == 4


def test_content_is_not_stored_in_plain_text_on_windows(conn: sqlite3.Connection) -> None:
    add(conn, "geheim-123")
    raw = conn.execute("SELECT content, encrypted FROM clipboard").fetchone()
    if dpapi.AVAILABLE:
        assert raw["encrypted"] == 1 and b"geheim-123" not in raw["content"]
    assert entries(conn)[0].text == "geheim-123"


def test_search_and_clear(conn: sqlite3.Connection) -> None:
    add(conn, "Apfel", now=1)
    add(conn, "Birne", now=2)
    assert [e.text for e in entries(conn, "apf")] == ["Apfel"]
    assert clear(conn) == 2


def test_sensitive_detection() -> None:
    assert is_sensitive(
        ['application/x-qt-windows-mime;value="ExcludeClipboardContentFromMonitorProcessing"'], None
    )
    assert is_sensitive([], b"\x00\x00\x00\x00")
    assert not is_sensitive(["text/plain"], b"\x01\x00\x00\x00")
    assert is_excluded_app("keepass.exe", "KeePass.exe, other.exe")
    assert not is_excluded_app("notepad.exe", "KeePass.exe")


def test_dpapi_round_trip() -> None:
    assert dpapi.unprotect(dpapi.protect(b"data")) == b"data"
