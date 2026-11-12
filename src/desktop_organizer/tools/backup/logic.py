"""Incremental folder backup with preview, verification and log. Pure logic, no UI.

Each source folder is copied to ``<destination>/<source folder name>``. Only new and
changed files (size or modification time differ) are copied. In mirror mode, files
that no longer exist in the source are removed from the backup (to the Recycle Bin).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from desktop_organizer.core import safety
from desktop_organizer.core.jobs import Job

MTIME_TOLERANCE = 2.0  # FAT and network drives store times with 2 s precision


@dataclass(frozen=True)
class Options:
    mirror: bool = False
    verify: str = "size"  # "none", "size", "hash"
    exclude: tuple[str, ...] = ()
    skip_hidden: bool = False


@dataclass
class Copy:
    source: Path
    target: Path
    size: int
    reason: str  # "new" or "changed"


@dataclass
class BackupPlan:
    copies: list[Copy] = field(default_factory=list)
    deletions: list[Path] = field(default_factory=list)
    unchanged: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def bytes_to_copy(self) -> int:
        return sum(c.size for c in self.copies)


class BackupError(ValueError):
    """Raised for an impossible source/destination combination."""


def target_folders(sources: list[Path], destination: Path) -> list[Path]:
    """One folder per source below the destination; duplicate names get a suffix."""
    used: set[str] = set()
    result = []
    for source in sources:
        name = source.name or source.drive.rstrip(":\\") or "Backup"
        candidate, counter = name, 2
        while candidate.casefold() in used:
            candidate = f"{name} ({counter})"
            counter += 1
        used.add(candidate.casefold())
        result.append(destination / candidate)
    return result


def validate(sources: list[Path], destination: Path) -> None:
    if not sources:
        raise BackupError("no_sources")
    dest = destination.resolve()
    for source in sources:
        src = source.resolve()
        if src == dest or src in dest.parents:
            raise BackupError("destination_inside_source")
        if dest in src.parents:
            raise BackupError("source_inside_destination")


def _excluded(name: str, options: Options) -> bool:
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pattern.lower()) for pattern in options.exclude)


def _hidden(name: str, st: os.stat_result) -> bool:
    attributes = getattr(st, "st_file_attributes", 0)
    return name.startswith(".") or bool(attributes & stat.FILE_ATTRIBUTE_HIDDEN)


def _walk(
    root: Path, options: Options, errors: list[tuple[Path, str]]
) -> dict[str, os.stat_result]:
    """Relative path -> stat for every file below root."""
    found: dict[str, os.stat_result] = {}
    stack = [root]
    while stack:
        folder = stack.pop()
        if safety.classify(str(folder)) in (
            safety.PathVerdict.SYSTEM,
            safety.PathVerdict.OTHER_USER,
        ):
            continue
        try:
            entries = list(os.scandir(folder))
        except OSError as exc:
            errors.append((folder, exc.strerror or str(exc)))
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append((Path(entry.path), exc.strerror or str(exc)))
                continue
            if _excluded(entry.name, options) or (options.skip_hidden and _hidden(entry.name, st)):
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                found[os.path.relpath(entry.path, root)] = st
    return found


def make_plan(
    sources: list[Path], destination: Path, options: Options, job: Job | None = None
) -> BackupPlan:
    job = job or Job()
    validate(sources, destination)
    plan = BackupPlan()
    for index, (source, target_root) in enumerate(
        zip(sources, target_folders(sources, destination), strict=True)
    ):
        job.progress(index, len(sources), str(source))
        source_files = _walk(source, options, plan.errors)
        target_files = _walk(target_root, options, []) if target_root.exists() else {}
        for count, (relative, st) in enumerate(sorted(source_files.items())):
            if count % 200 == 0:
                job.progress(count, len(source_files), relative)
            existing = target_files.get(relative)
            target = target_root / relative
            if existing is None:
                plan.copies.append(Copy(source / relative, target, st.st_size, "new"))
            elif (
                existing.st_size != st.st_size
                or abs(existing.st_mtime - st.st_mtime) > MTIME_TOLERANCE
            ):
                plan.copies.append(Copy(source / relative, target, st.st_size, "changed"))
            else:
                plan.unchanged += 1
        if options.mirror:
            plan.deletions.extend(
                target_root / relative for relative in sorted(set(target_files) - set(source_files))
            )
    return plan


def file_hash(path: Path, job: Job) -> bytes:
    digest = hashlib.blake2b(digest_size=32)
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            job.check()
            digest.update(chunk)
    return digest.digest()


@dataclass
class RunResult:
    copied: int = 0
    copied_bytes: int = 0
    deleted: int = 0
    verified: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)
    verify_failed: list[Path] = field(default_factory=list)
    started: float = 0.0
    finished: float = 0.0
    log_lines: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed and not self.verify_failed


def run(plan: BackupPlan, options: Options, job: Job | None = None) -> RunResult:
    job = job or Job()
    result = RunResult(started=time.time())
    log = result.log_lines
    total = plan.bytes_to_copy or 1
    done_bytes = 0
    for copy in plan.copies:
        job.progress(done_bytes, total, str(copy.source))
        try:
            copy.target.parent.mkdir(parents=True, exist_ok=True)
            tmp = copy.target.with_name(copy.target.name + ".do-partial")
            shutil.copy2(copy.source, tmp)
            os.replace(tmp, copy.target)
            result.copied += 1
            result.copied_bytes += copy.size
            log.append(f"COPY   {copy.reason:7} {copy.source} -> {copy.target}")
            if options.verify != "none":
                same = copy.target.stat().st_size == copy.source.stat().st_size
                if same and options.verify == "hash":
                    same = file_hash(copy.source, job) == file_hash(copy.target, job)
                if same:
                    result.verified += 1
                else:
                    result.verify_failed.append(copy.target)
                    log.append(f"VERIFY FAILED {copy.target}")
        except OSError as exc:
            reason = exc.strerror or str(exc)
            result.failed.append((copy.source, reason))
            log.append(f"ERROR  {copy.source}: {reason}")
        done_bytes += copy.size
    if plan.deletions:
        from send2trash import send2trash

        for path in plan.deletions:
            job.check()
            try:
                send2trash(str(path))
                result.deleted += 1
                log.append(f"REMOVE {path}")
            except Exception as exc:  # noqa: BLE001 - send2trash raises various types
                result.failed.append((path, str(exc)))
                log.append(f"ERROR  {path}: {exc}")
    result.finished = time.time()
    return result


def save_history(
    history_file: Path, profile: str, destination: Path, result: RunResult, log_dir: Path
) -> Path:
    """Append a summary to the history file and write the full log; returns the log path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(result.started))}.log"
    header = [
        f"Profile: {profile}",
        f"Destination: {destination}",
        f"Copied: {result.copied} files, {result.copied_bytes} bytes",
        f"Removed: {result.deleted}",
        f"Verified: {result.verified}, verification failed: {len(result.verify_failed)}",
        f"Errors: {len(result.failed)}",
        "",
    ]
    log_path.write_text("\n".join(header + result.log_lines) + "\n", encoding="utf-8")
    history = load_history(history_file)
    history.insert(
        0,
        {
            "profile": profile,
            "destination": str(destination),
            "started": result.started,
            "finished": result.finished,
            "copied": result.copied,
            "bytes": result.copied_bytes,
            "deleted": result.deleted,
            "errors": len(result.failed) + len(result.verify_failed),
            "log": str(log_path),
        },
    )
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history[:200], indent=1), encoding="utf-8")
    return log_path


def load_history(history_file: Path) -> list[dict[str, object]]:
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        return [entry for entry in data if isinstance(entry, dict)]
    except (OSError, ValueError):
        return []
