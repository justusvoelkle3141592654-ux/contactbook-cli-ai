"""Notes storage with full-text search (SQLite FTS5). Pure logic, no UI."""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from desktop_organizer.core.storage import Migration

MIGRATIONS = (
    Migration(
        "notes",
        1,
        (
            "CREATE TABLE notes ("
            " id INTEGER PRIMARY KEY,"
            " title TEXT NOT NULL DEFAULT '',"
            " body TEXT NOT NULL DEFAULT '',"
            " tags TEXT NOT NULL DEFAULT '',"
            " pinned INTEGER NOT NULL DEFAULT 0,"
            " created REAL NOT NULL,"
            " updated REAL NOT NULL)",
            "CREATE VIRTUAL TABLE notes_fts USING fts5("
            " title, body, tags, content='notes', content_rowid='id', tokenize='unicode61')",
            "CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN"
            " INSERT INTO notes_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);"
            " END",
            "CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN"
            " INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)"
            " VALUES ('delete', old.id, old.title, old.body, old.tags);"
            " END",
            "CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN"
            " INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)"
            " VALUES ('delete', old.id, old.title, old.body, old.tags);"
            " INSERT INTO notes_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);"
            " END",
        ),
    ),
)

SORTS = {
    "updated": "pinned DESC, updated DESC",
    "created": "pinned DESC, created DESC",
    "title": "pinned DESC, title COLLATE NOCASE ASC",
}


@dataclass
class Note:
    id: int
    title: str
    body: str
    tags: list[str]
    pinned: bool
    created: float
    updated: float

    @property
    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        first = next((line.strip() for line in self.body.splitlines() if line.strip()), "")
        return first[:80]


def parse_tags(text: str) -> list[str]:
    tags = (t.strip().lstrip("#") for t in re.split(r"[,;]", text))
    return list(dict.fromkeys(t for t in tags if t))


def _row(row: sqlite3.Row) -> Note:
    return Note(
        row["id"],
        row["title"],
        row["body"],
        parse_tags(row["tags"]),
        bool(row["pinned"]),
        row["created"],
        row["updated"],
    )


def create(conn: sqlite3.Connection, title: str = "", body: str = "", tags: list[str] | None = None) -> int:
    now = time.time()
    cursor = conn.execute(
        "INSERT INTO notes (title, body, tags, created, updated) VALUES (?, ?, ?, ?, ?)",
        (title, body, ", ".join(tags or []), now, now),
    )
    return int(cursor.lastrowid or 0)


def update(conn: sqlite3.Connection, note_id: int, title: str, body: str, tags: list[str]) -> None:
    conn.execute(
        "UPDATE notes SET title = ?, body = ?, tags = ?, updated = ? WHERE id = ?",
        (title, body, ", ".join(tags), time.time(), note_id),
    )


def set_pinned(conn: sqlite3.Connection, note_id: int, pinned: bool) -> None:
    conn.execute("UPDATE notes SET pinned = ? WHERE id = ?", (int(pinned), note_id))


def delete(conn: sqlite3.Connection, note_id: int) -> None:
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def get(conn: sqlite3.Connection, note_id: int) -> Note | None:
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return _row(row) if row else None


def fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 query: every word as a prefix term, all required."""
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words)


def search(
    conn: sqlite3.Connection, text: str = "", tag: str = "", sort: str = "updated", limit: int = 1000
) -> list[Note]:
    order = SORTS.get(sort, SORTS["updated"])
    query = fts_query(text)
    if query:
        rows = conn.execute(
            f"SELECT notes.* FROM notes JOIN notes_fts ON notes_fts.rowid = notes.id"
            f" WHERE notes_fts MATCH ? ORDER BY {order} LIMIT ?",
            (query, limit),
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM notes ORDER BY {order} LIMIT ?", (limit,)).fetchall()
    notes = [_row(r) for r in rows]
    if tag:
        notes = [n for n in notes if tag.casefold() in (t.casefold() for t in n.tags)]
    return notes


def all_tags(conn: sqlite3.Connection) -> list[str]:
    tags: dict[str, str] = {}
    for (text,) in conn.execute("SELECT tags FROM notes"):
        for tag in parse_tags(text):
            tags.setdefault(tag.casefold(), tag)
    return sorted(tags.values(), key=str.casefold)


def to_markdown(note: Note) -> str:
    head = f"# {note.display_title}\n\n" if note.display_title else ""
    tags = f"\n\nTags: {', '.join(note.tags)}\n" if note.tags else "\n"
    return head + note.body.rstrip() + tags
