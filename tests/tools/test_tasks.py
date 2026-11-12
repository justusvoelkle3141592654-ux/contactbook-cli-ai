import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from desktop_organizer.core.storage import Database
from desktop_organizer.tools.tasks.logic import (
    MIGRATIONS,
    counts,
    create,
    delete_done,
    end_of_day,
    lists,
    query,
    set_done,
    update,
)

NOW = datetime(2026, 11, 12, 14, 0).timestamp()


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = Database(tmp_path / "t.db")
    db.migrate(MIGRATIONS)
    return db.connection


def test_filters(conn: sqlite3.Connection) -> None:
    overdue = create(conn, "alt", NOW - 3600, list_name="Arbeit")
    today = create(conn, "heute", NOW + 3600)
    upcoming = create(conn, "morgen", NOW + 86400 * 2, priority=2)
    undated = create(conn, "irgendwann", list_name="Arbeit")
    done = create(conn, "fertig")
    set_done(conn, done, True, NOW)
    ids = lambda name: [t.id for t in query(conn, name, now=NOW)]  # noqa: E731
    assert ids("overdue") == [overdue]
    assert ids("today") == [overdue, today]
    assert ids("upcoming") == [upcoming]
    assert ids("open") == [overdue, today, upcoming, undated]
    assert ids("done") == [done]
    assert counts(conn, NOW) == {"open": 4, "today": 2, "overdue": 1, "upcoming": 1, "done": 1}
    assert lists(conn) == [("Arbeit", 2)]
    assert [t.id for t in query(conn, "open", "Arbeit", now=NOW)] == [overdue, undated]
    assert [t.id for t in query(conn, "open", now=NOW, text="morg")] == [upcoming]


def test_update_and_delete_done(conn: sqlite3.Connection) -> None:
    task = create(conn, "a")
    update(conn, task, "b", None, 0, "L", "n")
    assert query(conn, "open")[0].title == "b"
    set_done(conn, task, True)
    assert delete_done(conn) == 1


def test_end_of_day() -> None:
    assert datetime.fromtimestamp(end_of_day(NOW)) == datetime(2026, 11, 13)
