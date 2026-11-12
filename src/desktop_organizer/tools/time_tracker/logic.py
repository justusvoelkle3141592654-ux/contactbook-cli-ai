"""Time tracking storage and reports. Pure logic, no UI.

A running timer is an entry without end time, so it survives restarts of the app.
"""

from __future__ import annotations

import csv
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from desktop_organizer.core.storage import Migration

MIGRATIONS = (
    Migration(
        "time_tracker",
        1,
        (
            "CREATE TABLE tt_projects ("
            " id INTEGER PRIMARY KEY,"
            " name TEXT NOT NULL UNIQUE COLLATE NOCASE,"
            " archived INTEGER NOT NULL DEFAULT 0,"
            " created REAL NOT NULL)",
            "CREATE TABLE tt_entries ("
            " id INTEGER PRIMARY KEY,"
            " project_id INTEGER NOT NULL REFERENCES tt_projects(id) ON DELETE CASCADE,"
            " note TEXT NOT NULL DEFAULT '',"
            " start REAL NOT NULL,"
            " end REAL)",
            "CREATE INDEX tt_entries_start ON tt_entries(start)",
        ),
    ),
)


@dataclass
class Project:
    id: int
    name: str
    archived: bool


@dataclass
class Entry:
    id: int
    project_id: int
    project: str
    note: str
    start: float
    end: float | None

    def duration(self, now: float | None = None) -> float:
        end = self.end if self.end is not None else (now or time.time())
        return max(0.0, end - self.start)


def ensure_project(conn: sqlite3.Connection, name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("empty project name")
    row = conn.execute("SELECT id FROM tt_projects WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute("UPDATE tt_projects SET archived = 0 WHERE id = ?", (row[0],))
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO tt_projects (name, created) VALUES (?, ?)", (name, time.time())
    )
    return int(cursor.lastrowid or 0)


def projects(conn: sqlite3.Connection, include_archived: bool = False) -> list[Project]:
    sql = "SELECT * FROM tt_projects"
    if not include_archived:
        sql += " WHERE archived = 0"
    sql += " ORDER BY name COLLATE NOCASE"
    return [Project(r["id"], r["name"], bool(r["archived"])) for r in conn.execute(sql)]


def rename_project(conn: sqlite3.Connection, project_id: int, name: str) -> None:
    conn.execute("UPDATE tt_projects SET name = ? WHERE id = ?", (name.strip(), project_id))


def set_archived(conn: sqlite3.Connection, project_id: int, archived: bool) -> None:
    conn.execute("UPDATE tt_projects SET archived = ? WHERE id = ?", (int(archived), project_id))


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM tt_entries WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM tt_projects WHERE id = ?", (project_id,))


def _entries(
    conn: sqlite3.Connection, where: str = "1", params: tuple[object, ...] = ()
) -> list[Entry]:
    rows = conn.execute(
        "SELECT e.*, p.name AS project FROM tt_entries e JOIN tt_projects p ON p.id = e.project_id"
        f" WHERE {where} ORDER BY e.start DESC",
        params,
    ).fetchall()
    return [
        Entry(r["id"], r["project_id"], r["project"], r["note"], r["start"], r["end"]) for r in rows
    ]


def get_entry(conn: sqlite3.Connection, entry_id: int) -> Entry | None:
    found = _entries(conn, "e.id = ?", (entry_id,))
    return found[0] if found else None


def running(conn: sqlite3.Connection) -> Entry | None:
    found = _entries(conn, "e.end IS NULL")
    return found[0] if found else None


def start(
    conn: sqlite3.Connection, project_id: int, note: str = "", now: float | None = None
) -> int:
    now = time.time() if now is None else now
    stop(conn, now)
    cursor = conn.execute(
        "INSERT INTO tt_entries (project_id, note, start) VALUES (?, ?, ?)", (project_id, note, now)
    )
    return int(cursor.lastrowid or 0)


def stop(conn: sqlite3.Connection, now: float | None = None) -> Entry | None:
    now = time.time() if now is None else now
    current = running(conn)
    if current is not None:
        conn.execute(
            "UPDATE tt_entries SET end = ? WHERE id = ?", (max(now, current.start), current.id)
        )
        current.end = max(now, current.start)
    return current


def add_entry(
    conn: sqlite3.Connection, project_id: int, begin: float, end: float, note: str = ""
) -> int:
    if end <= begin:
        raise ValueError("end before start")
    cursor = conn.execute(
        "INSERT INTO tt_entries (project_id, note, start, end) VALUES (?, ?, ?, ?)",
        (project_id, note, begin, end),
    )
    return int(cursor.lastrowid or 0)


def update_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    project_id: int,
    begin: float,
    end: float | None,
    note: str,
) -> None:
    if end is not None and end <= begin:
        raise ValueError("end before start")
    conn.execute(
        "UPDATE tt_entries SET project_id = ?, start = ?, end = ?, note = ? WHERE id = ?",
        (project_id, begin, end, note, entry_id),
    )


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM tt_entries WHERE id = ?", (entry_id,))


def day_start(day: date) -> float:
    return datetime(day.year, day.month, day.day).timestamp()


def entries_between(conn: sqlite3.Connection, first: date, last: date) -> list[Entry]:
    """Entries overlapping the days ``first`` to ``last`` (inclusive)."""
    begin = day_start(first)
    end = day_start(last + timedelta(days=1))
    return _entries(conn, "e.start < ? AND (e.end IS NULL OR e.end > ?)", (end, begin))


def split_by_day(entry: Entry, now: float) -> dict[date, float]:
    """Seconds per calendar day; entries crossing midnight are split."""
    result: dict[date, float] = defaultdict(float)
    cursor = entry.start
    end = entry.end if entry.end is not None else now
    while cursor < end:
        day = datetime.fromtimestamp(cursor).date()
        boundary = min(end, day_start(day + timedelta(days=1)))
        result[day] += boundary - cursor
        cursor = boundary
    return dict(result)


def week_days(any_day: date, week_start: str = "monday") -> list[date]:
    offset = any_day.weekday() if week_start == "monday" else (any_day.weekday() + 1) % 7
    first = any_day - timedelta(days=offset)
    return [first + timedelta(days=i) for i in range(7)]


def totals(
    conn: sqlite3.Connection, days: list[date], now: float | None = None
) -> dict[str, dict[date, float]]:
    """project -> day -> seconds for the given days."""
    now = time.time() if now is None else now
    wanted = set(days)
    result: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for entry in entries_between(conn, min(days), max(days)):
        for day, seconds in split_by_day(entry, now).items():
            if day in wanted:
                result[entry.project][day] += seconds
    return {project: dict(per_day) for project, per_day in result.items()}


def round_seconds(seconds: float, minutes: int) -> float:
    if minutes <= 0:
        return seconds
    step = minutes * 60
    return round(seconds / step) * step


def export_csv(entries: list[Entry], target: Path, now: float | None = None) -> None:
    now = time.time() if now is None else now
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["project", "note", "start", "end", "hours"])
        for entry in sorted(entries, key=lambda e: e.start):
            writer.writerow(
                [
                    entry.project,
                    entry.note,
                    datetime.fromtimestamp(entry.start).isoformat(timespec="minutes"),
                    datetime.fromtimestamp(entry.end).isoformat(timespec="minutes")
                    if entry.end
                    else "",
                    f"{entry.duration(now) / 3600:.2f}",
                ]
            )
