"""Export and deletion of all user data (settings dialog)."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from desktop_organizer.core.paths import AppPaths
from desktop_organizer.core.storage import Database


def export_data(paths: AppPaths, database: Database, target: Path) -> list[str]:
    """Write settings and a consistent database copy into a ZIP file.

    Logs are not included; they contain no user content and are not needed to restore.
    Returns the names of the archived entries.
    """
    names: list[str] = []
    tmp_zip = target.with_name(target.name + ".tmp")
    with tempfile.TemporaryDirectory() as tmp:
        db_copy = Path(tmp) / paths.database_file.name
        database.backup_to(db_copy)
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if paths.settings_file.exists():
                archive.write(paths.settings_file, paths.settings_file.name)
                names.append(paths.settings_file.name)
            archive.write(db_copy, db_copy.name)
            names.append(db_copy.name)
    tmp_zip.replace(target)
    return names


def delete_all_data(paths: AppPaths) -> None:
    """Remove the whole data folder. Database and log handlers must be closed first."""
    if paths.data_dir.exists():
        shutil.rmtree(paths.data_dir)
    if paths.portable:
        # The empty folder is what marks the build as portable; keep it.
        paths.data_dir.mkdir()
