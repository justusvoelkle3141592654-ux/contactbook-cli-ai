"""Find duplicate files. Pure logic, no UI.

Stages: collect files by size, then compare a partial hash (first and last block),
then (for "content") a full BLAKE2 hash. Hard links to the same file and the same
path reached through overlapping folders are counted once.
"""

from __future__ import annotations

import csv
import hashlib
import os
import stat
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from desktop_organizer.core import safety
from desktop_organizer.core.jobs import Job

BLOCK = 64 * 1024
CHUNK = 1024 * 1024
METHODS = ("content", "fast", "name_size")
RULES = ("newest", "oldest", "shortest_path", "longest_path", "first_folder")


@dataclass(frozen=True)
class Options:
    method: str = "content"
    min_size: int = 1  # bytes
    max_size: int = 0  # bytes, 0 = no limit
    include_extensions: frozenset[str] = frozenset()  # lower-case, without dot
    exclude_extensions: frozenset[str] = frozenset()
    exclude_folders: frozenset[str] = frozenset({".git", "node_modules", "$recycle.bin"})
    skip_hidden: bool = True


@dataclass(frozen=True)
class FileEntry:
    path: Path
    size: int
    modified: float
    root_index: int  # which chosen folder it was found under


@dataclass
class Group:
    size: int
    files: list[FileEntry]

    @property
    def wasted(self) -> int:
        return self.size * (len(self.files) - 1)


@dataclass
class ScanResult:
    groups: list[Group] = field(default_factory=list)
    scanned_files: int = 0
    skipped: int = 0  # unreadable or protected

    @property
    def wasted(self) -> int:
        return sum(g.wasted for g in self.groups)


def parse_extensions(text: str) -> frozenset[str]:
    parts = (p.strip().lower().lstrip("*").lstrip(".") for p in text.replace(";", ",").split(","))
    return frozenset(p for p in parts if p)


def _hidden(name: str, st: os.stat_result) -> bool:
    attributes = getattr(st, "st_file_attributes", 0)
    return name.startswith(".") or bool(
        attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM)
    )


def walk(
    folders: list[Path], options: Options, job: Job, result: ScanResult
) -> Iterator[FileEntry]:
    seen_paths: set[str] = set()
    seen_inodes: set[tuple[int, int]] = set()
    counter = 0
    for root_index, root in enumerate(folders):
        stack = [root]
        while stack:
            folder = stack.pop()
            if safety.classify(str(folder)) in (
                safety.PathVerdict.SYSTEM,
                safety.PathVerdict.OTHER_USER,
            ):
                result.skipped += 1
                continue
            try:
                entries = list(os.scandir(folder))
            except OSError:
                result.skipped += 1
                continue
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue  # never follow links (could lead into protected areas)
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    result.skipped += 1
                    continue
                if options.skip_hidden and _hidden(entry.name, st):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in options.exclude_folders:
                        stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                counter += 1
                if counter % 200 == 0:
                    job.progress(counter, 0, entry.path)
                size = st.st_size
                if size < options.min_size or (options.max_size and size > options.max_size):
                    continue
                suffix = Path(entry.name).suffix.lower().lstrip(".")
                if options.include_extensions and suffix not in options.include_extensions:
                    continue
                if suffix in options.exclude_extensions:
                    continue
                key = os.path.normcase(os.path.abspath(entry.path))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                if st.st_ino:
                    inode = (st.st_dev, st.st_ino)
                    if inode in seen_inodes:
                        continue  # hard link to a file we already have
                    seen_inodes.add(inode)
                yield FileEntry(Path(entry.path), size, st.st_mtime, root_index)
    result.scanned_files = counter


def _partial_hash(path: Path, size: int) -> bytes:
    digest = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        digest.update(handle.read(BLOCK))
        if size > 2 * BLOCK:
            handle.seek(-BLOCK, os.SEEK_END)
            digest.update(handle.read(BLOCK))
    return digest.digest()


def _full_hash(path: Path, job: Job) -> bytes:
    digest = hashlib.blake2b(digest_size=32)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            job.check()
            digest.update(chunk)
    return digest.digest()


def _regroup(
    groups: Iterable[list[FileEntry]],
    key_fn: Callable[[FileEntry], object],
    job: Job,
    result: ScanResult,
    label: str,
) -> list[list[FileEntry]]:
    out: list[list[FileEntry]] = []
    groups = list(groups)
    total = sum(len(g) for g in groups)
    done = 0
    for group in groups:
        buckets: dict[object, list[FileEntry]] = defaultdict(list)
        for entry in group:
            done += 1
            job.progress(done, total, f"{label} {entry.path.name}")
            try:
                buckets[key_fn(entry)].append(entry)
            except OSError:
                result.skipped += 1
        out.extend(b for b in buckets.values() if len(b) > 1)
    return out


def scan(
    folders: list[Path],
    options: Options,
    job: Job | None = None,
    labels: dict[str, str] | None = None,
) -> ScanResult:
    job = job or Job()
    labels = labels or {}
    result = ScanResult()
    by_size: dict[int, list[FileEntry]] = defaultdict(list)
    for entry in walk(folders, options, job, result):
        by_size[entry.size].append(entry)
    candidates = [g for g in by_size.values() if len(g) > 1]

    if options.method == "name_size":
        groups = _regroup(
            candidates, lambda e: e.path.name.casefold(), job, result, labels.get("compare", "")
        )
    else:
        groups = _regroup(
            candidates,
            lambda e: _partial_hash(e.path, e.size),
            job,
            result,
            labels.get("partial", ""),
        )
        if options.method == "content":
            groups = _regroup(
                groups, lambda e: _full_hash(e.path, job), job, result, labels.get("full", "")
            )
    result.groups = sorted(
        (Group(g[0].size, sorted(g, key=lambda e: str(e.path).casefold())) for g in groups),
        key=lambda g: (-g.wasted, str(g.files[0].path).casefold()),
    )
    return result


def files_to_remove(group: Group, rule: str) -> list[FileEntry]:
    """All files of the group except the one the rule keeps."""
    if rule == "newest":
        keep = max(group.files, key=lambda e: (e.modified, -len(str(e.path))))
    elif rule == "oldest":
        keep = min(group.files, key=lambda e: (e.modified, len(str(e.path))))
    elif rule == "shortest_path":
        keep = min(group.files, key=lambda e: (len(str(e.path)), str(e.path)))
    elif rule == "longest_path":
        keep = max(group.files, key=lambda e: (len(str(e.path)), str(e.path)))
    elif rule == "first_folder":
        keep = min(group.files, key=lambda e: (e.root_index, len(str(e.path))))
    else:
        raise ValueError(rule)
    return [e for e in group.files if e is not keep]


def groups_fully_selected(groups: list[Group], selected: set[Path]) -> list[Group]:
    """Groups where every copy is selected; removing them would lose the file."""
    return [g for g in groups if all(e.path in selected for e in g.files)]


@dataclass
class ActionResult:
    done: int = 0
    freed: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)


def recycle(entries: list[FileEntry], job: Job | None = None) -> ActionResult:
    from send2trash import send2trash

    job = job or Job()
    result = ActionResult()
    for index, entry in enumerate(entries):
        job.progress(index, len(entries), entry.path.name)
        try:
            send2trash(str(entry.path))
            result.done += 1
            result.freed += entry.size
        except Exception as exc:  # noqa: BLE001 - send2trash raises various types
            result.failed.append((entry.path, str(exc)))
    return result


def move_to(entries: list[FileEntry], destination: Path, job: Job | None = None) -> ActionResult:
    import shutil

    from desktop_organizer.tools.file_cleaner.logic import unique_target

    job = job or Job()
    result = ActionResult()
    destination.mkdir(parents=True, exist_ok=True)
    for index, entry in enumerate(entries):
        job.progress(index, len(entries), entry.path.name)
        try:
            target = unique_target(destination / entry.path.name, set())
            shutil.move(str(entry.path), str(target))
            result.done += 1
            result.freed += entry.size
        except OSError as exc:
            result.failed.append((entry.path, exc.strerror or str(exc)))
    return result


def export_csv(groups: list[Group], target: Path, selected: set[Path]) -> None:
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["group", "path", "size_bytes", "modified", "selected"])
        for number, group in enumerate(groups, start=1):
            for entry in group.files:
                from datetime import datetime

                writer.writerow(
                    [
                        number,
                        str(entry.path),
                        entry.size,
                        datetime.fromtimestamp(entry.modified).isoformat(timespec="seconds"),
                        "yes" if entry.path in selected else "no",
                    ]
                )
