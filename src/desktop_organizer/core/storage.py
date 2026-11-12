"""SQLite storage with per-module schema migrations.

Each tool owns its tables and registers its own migrations under its module name, so
adding a tool never changes another tool's schema.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    module: str
    version: int
    statements: tuple[str, ...]


class MigrationError(RuntimeError):
    pass


def _check_sequence(migrations: Sequence[Migration]) -> None:
    by_module: dict[str, list[int]] = {}
    for migration in migrations:
        by_module.setdefault(migration.module, []).append(migration.version)
    for module, versions in by_module.items():
        if sorted(versions) != list(range(1, len(versions) + 1)):
            raise MigrationError(
                f"Migrations for {module!r} must be numbered 1..n without gaps, got {versions}"
            )


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " module TEXT NOT NULL,"
            " version INTEGER NOT NULL,"
            " applied_at TEXT NOT NULL,"
            " PRIMARY KEY (module, version))"
        )

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def current_version(self, module: str) -> int:
        row = self._conn.execute(
            "SELECT MAX(version) FROM schema_migrations WHERE module = ?", (module,)
        ).fetchone()
        return int(row[0]) if row[0] is not None else 0

    def migrate(self, migrations: Iterable[Migration]) -> list[Migration]:
        """Apply all pending migrations. Each one runs in its own transaction."""
        ordered = sorted(migrations, key=lambda m: (m.module, m.version))
        _check_sequence(ordered)
        applied: list[Migration] = []
        for migration in ordered:
            if migration.version <= self.current_version(migration.module):
                continue
            try:
                self._conn.execute("BEGIN")
                for statement in migration.statements:
                    self._conn.execute(statement)
                self._conn.execute(
                    "INSERT INTO schema_migrations (module, version, applied_at) VALUES (?, ?, ?)",
                    (migration.module, migration.version, datetime.now(UTC).isoformat()),
                )
                self._conn.execute("COMMIT")
            except sqlite3.Error as exc:
                self._conn.execute("ROLLBACK")
                raise MigrationError(
                    f"Migration {migration.module} v{migration.version} failed: {exc}"
                ) from exc
            applied.append(migration)
        return applied

    def backup_to(self, target: Path) -> None:
        """Write a consistent copy of the database, even while it is in use."""
        dest = sqlite3.connect(target)
        try:
            self._conn.backup(dest)
        finally:
            dest.close()

    def close(self) -> None:
        self._conn.close()
