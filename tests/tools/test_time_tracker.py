import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from desktop_organizer.core.storage import Database
from desktop_organizer.tools.time_tracker.logic import (
    MIGRATIONS,
    add_entry,
    delete_project,
    ensure_project,
    entries_between,
    export_csv,
    projects,
    round_seconds,
    running,
    split_by_day,
    start,
    stop,
    totals,
    week_days,
)


def ts(*a: int) -> float:
    return datetime(*a).timestamp()  # type: ignore[arg-type]


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = Database(tmp_path / "tt.db")
    db.migrate(MIGRATIONS)
    return db.connection


def test_start_stop_and_single_running(conn: sqlite3.Connection) -> None:
    a = ensure_project(conn, "A")
    b = ensure_project(conn, "B")
    assert ensure_project(conn, "a") == a  # case-insensitive
    start(conn, a, "x", now=ts(2026, 1, 5, 9))
    start(conn, b, "y", now=ts(2026, 1, 5, 10))  # stops A
    current = running(conn)
    assert current is not None and current.project == "B"
    stopped = stop(conn, now=ts(2026, 1, 5, 11, 30))
    assert stopped is not None and stopped.duration() == 5400
    assert running(conn) is None


def test_split_across_midnight(conn: sqlite3.Connection) -> None:
    p = ensure_project(conn, "Nacht")
    add_entry(conn, p, ts(2026, 1, 5, 23), ts(2026, 1, 6, 1, 30))
    entry = entries_between(conn, date(2026, 1, 5), date(2026, 1, 6))[0]
    assert split_by_day(entry, 0) == {date(2026, 1, 5): 3600, date(2026, 1, 6): 5400}


def test_week_totals(conn: sqlite3.Connection) -> None:
    p = ensure_project(conn, "Web")
    add_entry(conn, p, ts(2026, 1, 5, 9), ts(2026, 1, 5, 11))
    add_entry(conn, p, ts(2026, 1, 7, 9), ts(2026, 1, 7, 10))
    days = week_days(date(2026, 1, 7))
    assert days[0] == date(2026, 1, 5) and len(days) == 7
    assert week_days(date(2026, 1, 7), "sunday")[0] == date(2026, 1, 4)
    data = totals(conn, days, now=ts(2026, 1, 8))
    assert data == {"Web": {date(2026, 1, 5): 7200, date(2026, 1, 7): 3600}}


def test_invalid_entry_and_delete_project(conn: sqlite3.Connection) -> None:
    p = ensure_project(conn, "X")
    with pytest.raises(ValueError):
        add_entry(conn, p, 10, 5)
    add_entry(conn, p, 0, 10)
    delete_project(conn, p)
    assert projects(conn) == []


def test_round_and_export(conn: sqlite3.Connection, tmp_path: Path) -> None:
    assert round_seconds(7 * 60 + 40, 15) == 15 * 60
    assert round_seconds(100, 0) == 100
    p = ensure_project(conn, "Export")
    add_entry(conn, p, ts(2026, 1, 5, 9), ts(2026, 1, 5, 10, 30), "Notiz")
    target = tmp_path / "out.csv"
    export_csv(entries_between(conn, date(2026, 1, 5), date(2026, 1, 5)), target)
    lines = target.read_text(encoding="utf-8-sig").splitlines()
    assert lines[1].endswith(";1.50") and "Export;Notiz" in lines[1]
