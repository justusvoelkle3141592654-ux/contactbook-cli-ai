"""Task storage and filters. Pure logic, no UI."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from desktop_organizer.core.storage import Migration

MIGRATIONS = (
    Migration(
        "tasks",
        1,
        (
            "CREATE TABLE tasks ("
            " id INTEGER PRIMARY KEY,"
            " title TEXT NOT NULL,"
            " notes TEXT NOT NULL DEFAULT '',"
            " due REAL,"
            " priority INTEGER NOT NULL DEFAULT 1,"
            " list TEXT NOT NULL DEFAULT '',"
            " done INTEGER NOT NULL DEFAULT 0,"
            " done_at REAL,"
            " created REAL NOT NULL)",
            "CREATE INDEX tasks_done_due ON tasks(done, due)",
        ),
    ),
)

FILTERS = ("open", "today", "overdue", "upcoming", "done")
PRIORITIES = (0, 1, 2)  # low, normal, high


@dataclass
class Task:
    id: int
    title: str
    notes: str
    due: float | None
    priority: int
    list: str
    done: bool
    done_at: float | None
    created: float


def _row(row: sqlite3.Row) -> Task:
    return Task(
        row["id"],
        row["title"],
        row["notes"],
        row["due"],
        row["priority"],
        row["list"],
        bool(row["done"]),
        row["done_at"],
        row["created"],
    )


def end_of_day(now: float) -> float:
    moment = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return (moment + timedelta(days=1)).timestamp()


def create(
    conn: sqlite3.Connection,
    title: str,
    due: float | None = None,
    priority: int = 1,
    list_name: str = "",
    notes: str = "",
) -> int:
    cursor = conn.execute(
        "INSERT INTO tasks (title, notes, due, priority, list, created) VALUES (?, ?, ?, ?, ?, ?)",
        (title.strip(), notes, due, priority, list_name.strip(), time.time()),
    )
    return int(cursor.lastrowid or 0)


def update(
    conn: sqlite3.Connection,
    task_id: int,
    title: str,
    due: float | None,
    priority: int,
    list_name: str,
    notes: str,
) -> None:
    conn.execute(
        "UPDATE tasks SET title = ?, due = ?, priority = ?, list = ?, notes = ? WHERE id = ?",
        (title.strip(), due, priority, list_name.strip(), notes, task_id),
    )


def set_done(conn: sqlite3.Connection, task_id: int, done: bool, now: float | None = None) -> None:
    conn.execute(
        "UPDATE tasks SET done = ?, done_at = ? WHERE id = ?",
        (int(done), (now or time.time()) if done else None, task_id),
    )


def delete(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def delete_done(conn: sqlite3.Connection) -> int:
    return conn.execute("DELETE FROM tasks WHERE done = 1").rowcount


def get(conn: sqlite3.Connection, task_id: int) -> Task | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row(row) if row else None


def _where(name: str, now: float) -> tuple[str, tuple[object, ...]]:
    eod = end_of_day(now)
    return {
        "open": ("done = 0", ()),
        "today": ("done = 0 AND due IS NOT NULL AND due < ?", (eod,)),
        "overdue": ("done = 0 AND due IS NOT NULL AND due < ?", (now,)),
        "upcoming": ("done = 0 AND due IS NOT NULL AND due >= ?", (eod,)),
        "done": ("done = 1", ()),
    }[name]


def query(conn: sqlite3.Connection, filter_name: str, list_name: str = "", now: float | None = None, text: str = "") -> list[Task]:
    now = time.time() if now is None else now
    where, params = _where(filter_name, now)
    sql = f"SELECT * FROM tasks WHERE {where}"
    args: list[object] = list(params)
    if list_name:
        sql += " AND list = ?"
        args.append(list_name)
    if text:
        sql += " AND (title LIKE ? OR notes LIKE ?)"
        args.extend([f"%{text}%", f"%{text}%"])
    if filter_name == "done":
        sql += " ORDER BY done_at DESC"
    else:
        sql += " ORDER BY due IS NULL, due, priority DESC, created"
    return [_row(r) for r in conn.execute(sql, args).fetchall()]


def counts(conn: sqlite3.Connection, now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    result = {}
    for name in FILTERS:
        where, params = _where(name, now)
        result[name] = conn.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
    return result


def lists(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT list, SUM(done = 0) FROM tasks WHERE list != '' GROUP BY list ORDER BY list COLLATE NOCASE"
    ).fetchall()
    return [(r[0], int(r[1] or 0)) for r in rows]
