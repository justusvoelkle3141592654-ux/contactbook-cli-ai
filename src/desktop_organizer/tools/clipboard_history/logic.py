"""Clipboard history storage. Entries are encrypted with DPAPI on Windows.

Recording happens in the main Desktop Organizer process (it must keep running while
the history window is closed); this module stores, lists and removes entries.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from desktop_organizer.core import dpapi
from desktop_organizer.core.storage import Migration

MIGRATIONS = (
    Migration(
        "clipboard_history",
        1,
        (
            "CREATE TABLE clipboard ("
            " id INTEGER PRIMARY KEY,"
            " content BLOB NOT NULL,"
            " encrypted INTEGER NOT NULL,"
            " pinned INTEGER NOT NULL DEFAULT 0,"
            " source TEXT NOT NULL DEFAULT '',"
            " created REAL NOT NULL)",
        ),
    ),
)

SENSITIVE_FORMATS = (
    "ExcludeClipboardContentFromMonitorProcessing",
    "Clipboard Viewer Ignore",
)
HISTORY_FLAG = "CanIncludeInClipboardHistory"
DEFAULT_EXCLUDED = (
    "KeePass.exe, KeePassXC.exe, 1Password.exe, Bitwarden.exe, Dashlane.exe, LastPass.exe"
)


@dataclass
class ClipEntry:
    id: int
    text: str
    pinned: bool
    source: str
    created: float


def _encode(text: str) -> tuple[bytes, int]:
    raw = text.encode("utf-8")
    if dpapi.AVAILABLE:
        return dpapi.protect(raw), 1
    return raw, 0


def _decode(blob: bytes, encrypted: int) -> str:
    raw = dpapi.unprotect(blob) if encrypted else blob
    return raw.decode("utf-8", errors="replace")


def is_sensitive(formats: list[str], history_flag: bytes | None) -> bool:
    """Password managers mark secrets with special clipboard formats."""
    if any(any(marker in f for marker in SENSITIVE_FORMATS) for f in formats):
        return True
    # CanIncludeInClipboardHistory = 0 means "do not keep this".
    return history_flag is not None and history_flag[:4] == b"\x00\x00\x00\x00"


def is_excluded_app(app: str, excluded: str) -> bool:
    names = {n.strip().casefold() for n in excluded.split(",") if n.strip()}
    return bool(app) and app.casefold() in names


def add(
    conn: sqlite3.Connection,
    text: str,
    max_entries: int = 200,
    source: str = "",
    now: float | None = None,
) -> int | None:
    """Store text; a repeat of the newest entry only moves it up. Returns the id."""
    if not text.strip():
        return None
    now = time.time() if now is None else now
    latest = conn.execute(
        "SELECT id, content, encrypted FROM clipboard ORDER BY created DESC LIMIT 1"
    ).fetchone()
    if latest is not None and _decode(latest["content"], latest["encrypted"]) == text:
        conn.execute("UPDATE clipboard SET created = ? WHERE id = ?", (now, latest["id"]))
        return int(latest["id"])
    blob, encrypted = _encode(text)
    cursor = conn.execute(
        "INSERT INTO clipboard (content, encrypted, source, created) VALUES (?, ?, ?, ?)",
        (blob, encrypted, source, now),
    )
    prune(conn, max_entries)
    return int(cursor.lastrowid or 0)


def prune(conn: sqlite3.Connection, max_entries: int) -> None:
    conn.execute(
        "DELETE FROM clipboard WHERE pinned = 0 AND id NOT IN ("
        " SELECT id FROM clipboard WHERE pinned = 0 ORDER BY created DESC LIMIT ?)",
        (max_entries,),
    )


def entries(conn: sqlite3.Connection, search: str = "") -> list[ClipEntry]:
    rows = conn.execute("SELECT * FROM clipboard ORDER BY pinned DESC, created DESC").fetchall()
    result = [
        ClipEntry(
            r["id"],
            _decode(r["content"], r["encrypted"]),
            bool(r["pinned"]),
            r["source"],
            r["created"],
        )
        for r in rows
    ]
    if search:
        needle = search.casefold()
        result = [e for e in result if needle in e.text.casefold()]
    return result


def set_pinned(conn: sqlite3.Connection, entry_id: int, pinned: bool) -> None:
    conn.execute("UPDATE clipboard SET pinned = ? WHERE id = ?", (int(pinned), entry_id))


def delete(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM clipboard WHERE id = ?", (entry_id,))


def clear(conn: sqlite3.Connection, keep_pinned: bool = True) -> int:
    sql = "DELETE FROM clipboard" + (" WHERE pinned = 0" if keep_pinned else "")
    return conn.execute(sql).rowcount


def state(conn: sqlite3.Connection) -> tuple[int, float]:
    """(count, newest time): cheap change detection for the history window."""
    row = conn.execute("SELECT COUNT(*), COALESCE(MAX(created), 0) FROM clipboard").fetchone()
    return int(row[0]), float(row[1])
