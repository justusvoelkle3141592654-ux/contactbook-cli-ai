import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from desktop_organizer.core.storage import Database
from desktop_organizer.tools.reminders.logic import (
    MIGRATIONS,
    create,
    due_now,
    get,
    mark_fired,
    next_after,
    next_upcoming,
    snooze,
)


def ts(*args: int) -> float:
    return datetime(*args).timestamp()  # type: ignore[arg-type]


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = Database(tmp_path / "r.db")
    db.migrate(MIGRATIONS)
    return db.connection


def test_once_has_no_next() -> None:
    assert next_after(ts(2026, 1, 1, 9), "once", 1, ts(2026, 1, 1, 10)) is None


def test_minutes_skip_missed_periods() -> None:
    start = ts(2026, 1, 1, 9, 0)
    assert next_after(start, "minutes", 30, ts(2026, 1, 1, 9, 0)) == ts(2026, 1, 1, 9, 30)
    assert next_after(start, "minutes", 30, ts(2026, 1, 1, 11, 10)) == ts(2026, 1, 1, 11, 30)


def test_daily_weekdays_weekly_monthly() -> None:
    friday = ts(2026, 11, 13, 8, 0)
    assert next_after(friday, "daily", 1, friday) == ts(2026, 11, 14, 8, 0)
    assert next_after(friday, "weekdays", 1, friday) == ts(2026, 11, 16, 8, 0)
    assert next_after(friday, "weekly", 1, friday) == ts(2026, 11, 20, 8, 0)
    assert next_after(ts(2026, 1, 31, 8), "monthly", 1, ts(2026, 1, 31, 8)) == ts(2026, 2, 28, 8)
    assert next_after(ts(2026, 12, 15, 8), "monthly", 1, ts(2026, 12, 15, 9)) == ts(2027, 1, 15, 8)


def test_fire_disables_once_and_advances_recurring(conn: sqlite3.Connection) -> None:
    now = ts(2026, 5, 4, 12, 0)
    once = create(conn, "Termin", now - 60)
    daily = create(conn, "Tabletten", now - 60, "daily")
    later = create(conn, "Später", now + 3600)
    assert {r.id for r in due_now(conn, now)} == {once, daily}
    for reminder in due_now(conn, now):
        mark_fired(conn, reminder, now)
    assert get(conn, once).enabled is False  # type: ignore[union-attr]
    assert get(conn, daily).due == now - 60 + 86400  # type: ignore[union-attr]
    assert due_now(conn, now) == []
    assert next_upcoming(conn).id == later  # type: ignore[union-attr]


def test_snooze(conn: sqlite3.Connection) -> None:
    reminder = create(conn, "A", 0)
    snooze(conn, reminder, 10, 1000)
    assert get(conn, reminder).due == 1600  # type: ignore[union-attr]


def test_invalid_recurrence(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        create(conn, "x", 0, "yearly")
