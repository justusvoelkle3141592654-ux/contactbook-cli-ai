"""Sort the files of one folder into subfolders by type. Pure logic, no UI.

Only files directly inside the chosen folder are moved; existing subfolders are left
alone. Nothing is ever overwritten. Every run writes a journal so it can be undone.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from desktop_organizer.core.jobs import Job

# fmt: off
CATEGORIES: dict[str, tuple[str, ...]] = {
    "images": (
        "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp", "heic", "heif", "svg",
        "ico", "raw", "cr2", "cr3", "nef", "arw", "dng", "psd", "avif",
    ),
    "documents": ("pdf", "doc", "docx", "odt", "rtf", "txt", "md", "tex", "pages", "epub", "xps"),
    "spreadsheets": ("xls", "xlsx", "xlsm", "ods", "csv", "tsv", "numbers"),
    "presentations": ("ppt", "pptx", "odp", "key"),
    "audio": ("mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "aiff", "mid"),
    "video": ("mp4", "mkv", "avi", "mov", "wmv", "webm", "m4v", "mpg", "mpeg", "flv", "3gp"),
    "archives": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz", "iso", "cab", "zst"),
    "programs": ("exe", "msi", "msix", "appx", "bat", "cmd", "ps1", "apk", "dmg", "jar"),
    "code": (
        "py", "js", "ts", "html", "htm", "css", "json", "xml", "yml", "yaml", "java", "c",
        "cpp", "h", "cs", "go", "rs", "php", "rb", "sh", "sql", "ipynb", "toml", "ini",
    ),
    "fonts": ("ttf", "otf", "woff", "woff2"),
}
# fmt: on
OTHER = "other"
CATEGORY_ORDER = (*CATEGORIES.keys(), OTHER)

# fmt: off
FOLDER_NAMES = {
    "de": {
        "images": "Bilder", "documents": "Dokumente", "spreadsheets": "Tabellen",
        "presentations": "Präsentationen", "audio": "Audio", "video": "Videos",
        "archives": "Archive", "programs": "Programme", "code": "Code", "fonts": "Schriften",
        "other": "Sonstiges",
    },
    "en": {
        "images": "Images", "documents": "Documents", "spreadsheets": "Spreadsheets",
        "presentations": "Presentations", "audio": "Audio", "video": "Videos",
        "archives": "Archives", "programs": "Programs", "code": "Code", "fonts": "Fonts",
        "other": "Other",
    },
}

# fmt: on

_BY_EXTENSION = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}
PARTIAL_SUFFIXES = (".crdownload", ".part", ".partial", ".tmp", ".download")


def category_of(name: str) -> str:
    suffix = Path(name).suffix.lower().lstrip(".")
    return _BY_EXTENSION.get(suffix, OTHER)


def is_hidden(path: Path, st: os.stat_result) -> bool:
    if path.name.startswith("."):
        return True
    attributes = getattr(st, "st_file_attributes", 0)
    return bool(attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))


@dataclass(frozen=True)
class Options:
    folder_language: str = "de"  # "de" or "en"
    move_other: bool = True
    date_subfolders: str = "none"  # "none", "year", "year_month"
    include_hidden: bool = False
    skip_recent_minutes: int = 10
    on_conflict: str = "rename"  # "rename" or "skip"


@dataclass
class Move:
    source: Path
    target: Path
    category: str
    size: int
    modified: float


@dataclass
class Plan:
    folder: Path
    moves: list[Move] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # reason codes


def unique_target(target: Path, taken: set[Path]) -> Path:
    """``name (2).ext``, ``name (3).ext`` ... until neither on disk nor planned."""
    candidate = target
    counter = 2
    while candidate.exists() or candidate in taken:
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        counter += 1
    return candidate


def make_plan(
    folder: Path, options: Options, job: Job | None = None, now: float | None = None
) -> Plan:
    job = job or Job()
    now = time.time() if now is None else now
    names = FOLDER_NAMES.get(options.folder_language, FOLDER_NAMES["en"])
    plan = Plan(folder)
    taken: set[Path] = set()
    entries = sorted(os.scandir(folder), key=lambda e: e.name.casefold())
    for index, entry in enumerate(entries):
        job.progress(index, len(entries), entry.name)
        path = Path(entry.path)
        try:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                continue
            st = entry.stat(follow_symlinks=False)
        except OSError:
            plan.skipped.append((path, "unreadable"))
            continue
        if not options.include_hidden and is_hidden(path, st):
            plan.skipped.append((path, "hidden"))
            continue
        if path.suffix.lower() in PARTIAL_SUFFIXES:
            plan.skipped.append((path, "partial"))
            continue
        if options.skip_recent_minutes and now - st.st_mtime < options.skip_recent_minutes * 60:
            plan.skipped.append((path, "recent"))
            continue
        category = category_of(path.name)
        if category == OTHER and not options.move_other:
            plan.skipped.append((path, "other"))
            continue
        target_dir = folder / names[category]
        if options.date_subfolders != "none":
            moment = datetime.fromtimestamp(st.st_mtime)
            target_dir = target_dir / f"{moment:%Y}"
            if options.date_subfolders == "year_month":
                target_dir = target_dir / f"{moment:%m}"
        target = target_dir / path.name
        if target.exists() or target in taken:
            if options.on_conflict == "skip":
                plan.skipped.append((path, "exists"))
                continue
            target = unique_target(target, taken)
        taken.add(target)
        plan.moves.append(Move(path, target, category, st.st_size, st.st_mtime))
    return plan


@dataclass
class RunResult:
    moved: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)
    journal: Path | None = None


def execute(moves: list[Move], journal_path: Path, job: Job | None = None) -> RunResult:
    """Move files; never overwrite; record every move in a journal for undo."""
    job = job or Job()
    result = RunResult(journal=journal_path)
    journal: dict[str, object] = {"created_dirs": [], "moves": [], "time": time.time()}
    created: list[str] = journal["created_dirs"]  # type: ignore[assignment]
    done: list[list[str]] = journal["moves"]  # type: ignore[assignment]
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        for index, move in enumerate(moves):
            job.progress(index, len(moves), move.source.name)
            try:
                parent = move.target.parent
                missing = []
                probe = parent
                while not probe.exists():
                    missing.append(probe)
                    probe = probe.parent
                parent.mkdir(parents=True, exist_ok=True)
                created.extend(str(p) for p in reversed(missing))
                target = move.target
                if target.exists():
                    target = unique_target(target, set())
                # os.rename refuses to replace an existing file on Windows; on other
                # systems the exists() check above guards against overwriting.
                os.rename(move.source, target)
                done.append([str(move.source), str(target)])
                result.moved += 1
            except OSError as exc:
                result.failed.append((move.source, exc.strerror or str(exc)))
    finally:
        journal_path.write_text(json.dumps(journal, indent=1), encoding="utf-8")
    return result


@dataclass
class UndoResult:
    restored: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)


def undo(journal_path: Path, job: Job | None = None) -> UndoResult:
    job = job or Job()
    data = json.loads(journal_path.read_text(encoding="utf-8"))
    result = UndoResult()
    moves = list(reversed(data.get("moves", [])))
    for index, (source, target) in enumerate(moves):
        job.progress(index, len(moves), Path(target).name)
        src, dst = Path(source), Path(target)
        if not dst.exists():
            result.failed.append((dst, "missing"))
            continue
        if src.exists():
            result.failed.append((src, "occupied"))
            continue
        try:
            os.rename(dst, src)
            result.restored += 1
        except OSError as exc:
            result.failed.append((dst, exc.strerror or str(exc)))
    for folder in reversed(data.get("created_dirs", [])):
        try:
            Path(folder).rmdir()  # only removes folders that are empty again
        except OSError:
            pass
    journal_path.unlink()
    return result


def journal_info(journal_path: Path) -> tuple[int, float] | None:
    """(number of moves, time) of the last run, or None."""
    try:
        data = json.loads(journal_path.read_text(encoding="utf-8"))
        return len(data.get("moves", [])), float(data.get("time", 0))
    except (OSError, ValueError):
        return None
