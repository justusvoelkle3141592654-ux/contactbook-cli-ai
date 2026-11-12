"""Reminder storage and recurrence. Pure logic, no UI.

The main Desktop Organizer process checks for due reminders and shows them as Windows
notifications; this module only stores them and computes the next occurrence.
"""

from __future__ import annotations

import calendar
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from desktop_organizer.core.storage import Migration

RECURRENCES = ("once", "minutes", "daily", "weekdays", "weekly", "monthly")

MIGRATIONS = (
    Migration(
        "reminders",
        1,
        (
            "CREATE TABLE reminders ("
            " id INTEGER PRIMARY KEY,"
            " title TEXT NOT NULL,"
            " message TEXT NOT NULL DEFAULT '',"
            " due REAL NOT NULL,"
            " recurrence TEXT NOT NULL DEFAULT 'once',"
            " interval INTEGER NOT NULL DEFAULT 1,"
            " enabled INTEGER NOT NULL DEFAULT 1,"
            " last_fired REAL,"
            " created REAL NOT NULL,"
            " task_id INTEGER)",
            "CREATE INDEX reminders_due ON reminders(enabled, due)",
        ),
    ),
)


@dataclass
class Reminder:
    id: int
    title: str
    message: str
    due: float
    recurrence: str
    interval: int
    enabled: bool
    last_fired: float | None
    task_id: int | None


def _row(row: sqlite3.Row) -> Reminder:
    return Reminder(
        row["id"],
        row["title"],
        row["message"],
        row["due"],
        row["recurrence"],
        row["interval"],
        bool(row["enabled"]),
        row["last_fired"],
        row["task_id"],
    )


def _add_month(moment: datetime) -> datetime:
    year, month = (moment.year + 1, 1) if moment.month == 12 else (moment.year, moment.month + 1)
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def step(moment: datetime, recurrence: str, interval: int) -> datetime:
    if recurrence == "minutes":
        return moment + timedelta(minutes=max(1, interval))
    if recurrence == "daily":
        return moment + timedelta(days=1)
    if recurrence == "weekdays":
        moment += timedelta(days=1)
        while moment.weekday() >= 5:
            moment += timedelta(days=1)
        return moment
    if recurrence == "weekly":
        return moment + timedelta(days=7)
    if recurrence == "monthly":
        return _add_month(moment)
    raise ValueError(recurrence)


def next_after(due: float, recurrence: str, interval: int, now: float) -> float | None:
    """The first occurrence strictly after ``now``; None for one-off reminders."""
    if recurrence == "once":
        return None
    if recurrence == "minutes":
        period = max(1, interval) * 60
        steps = max(1, math.floor((now - due) / period) + 1)
        return due + steps * period
    moment = datetime.fromtimestamp(due)
    limit = datetime.fromtimestamp(now)
    moment = step(moment, recurrence, interval)
    while moment <= limit:
        moment = step(moment, recurrence, interval)
    return moment.timestamp()


def create(
    conn: sqlite3.Connection,
    title: str,
    due: float,
    recurrence: str = "once",
    interval: int = 1,
    message: str = "",
    task_id: int | None = None,
) -> int:
    if recurrence not in RECURRENCES:
        raise ValueError(recurrence)
    cursor = conn.execute(
        "INSERT INTO reminders (title, message, due, recurrence, interval, created, task_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, message, due, recurrence, interval, time.time(), task_id),
    )
    return int(cursor.lastrowid or 0)


def update(
    conn: sqlite3.Connection,
    reminder_id: int,
    title: str,
    due: float,
    recurrence: str,
    interval: int,
    message: str,
) -> None:
    conn.execute(
        "UPDATE reminders SET title = ?, due = ?, recurrence = ?, interval = ?, message = ?,"
        " enabled = 1 WHERE id = ?",
        (title, due, recurrence, interval, message, reminder_id),
    )


def set_enabled(conn: sqlite3.Connection, reminder_id: int, enabled: bool) -> None:
    conn.execute("UPDATE reminders SET enabled = ? WHERE id = ?", (int(enabled), reminder_id))


def delete(conn: sqlite3.Connection, reminder_id: int) -> None:
    conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


def get(conn: sqlite3.Connection, reminder_id: int) -> Reminder | None:
    row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row(row) if row else None


def all_reminders(conn: sqlite3.Connection) -> list[Reminder]:
    rows = conn.execute("SELECT * FROM reminders ORDER BY enabled DESC, due ASC").fetchall()
    return [_row(r) for r in rows]


def for_task(conn: sqlite3.Connection, task_id: int) -> Reminder | None:
    row = conn.execute("SELECT * FROM reminders WHERE task_id = ? LIMIT 1", (task_id,)).fetchone()
    return _row(row) if row else None


def due_now(conn: sqlite3.Connection, now: float) -> list[Reminder]:
    rows = conn.execute(
        "SELECT * FROM reminders WHERE enabled = 1 AND due <= ? ORDER BY due", (now,)
    ).fetchall()
    return [_row(r) for r in rows]


def mark_fired(conn: sqlite3.Connection, reminder: Reminder, now: float) -> None:
    following = next_after(reminder.due, reminder.recurrence, reminder.interval, now)
    if following is None:
        conn.execute(
            "UPDATE reminders SET enabled = 0, last_fired = ? WHERE id = ?", (now, reminder.id)
        )
    else:
        conn.execute(
            "UPDATE reminders SET due = ?, last_fired = ? WHERE id = ?",
            (following, now, reminder.id),
        )


def snooze(conn: sqlite3.Connection, reminder_id: int, minutes: int, now: float) -> None:
    conn.execute(
        "UPDATE reminders SET due = ?, enabled = 1 WHERE id = ?", (now + minutes * 60, reminder_id)
    )


def next_upcoming(conn: sqlite3.Connection) -> Reminder | None:
    row = conn.execute("SELECT * FROM reminders WHERE enabled = 1 ORDER BY due LIMIT 1").fetchone()
    return _row(row) if row else None
