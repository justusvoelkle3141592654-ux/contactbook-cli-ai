"""Find and replace text across many files, with preview, backup and undo. Pure logic."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from desktop_organizer.core import safety
from desktop_organizer.core.jobs import Job

ENCODINGS = ("utf-8", "cp1252")


@dataclass(frozen=True)
class Options:
    find: str
    replace: str = ""
    case_sensitive: bool = False
    whole_word: bool = False
    regex: bool = False
    patterns: tuple[str, ...] = ("*.txt",)
    recursive: bool = True
    skip_hidden: bool = True
    max_file_size: int = 20 * 1024 * 1024


@dataclass
class LineChange:
    number: int
    before: str
    after: str


@dataclass
class FileMatches:
    path: Path
    encoding: str
    count: int
    lines: list[LineChange]
    size: int
    modified: float


@dataclass
class Preview:
    files: list[FileMatches] = field(default_factory=list)
    skipped_binary: int = 0
    skipped_unreadable: int = 0

    @property
    def total(self) -> int:
        return sum(f.count for f in self.files)


def parse_patterns(text: str) -> tuple[str, ...]:
    parts = (p.strip() for p in text.replace(",", ";").split(";"))
    return tuple(p for p in parts if p) or ("*",)


def compile_pattern(options: Options) -> re.Pattern[str]:
    if not options.find:
        raise ValueError("empty search")
    body = options.find if options.regex else re.escape(options.find)
    if options.whole_word:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    flags = re.MULTILINE if options.case_sensitive else re.MULTILINE | re.IGNORECASE
    return re.compile(body, flags)


def substitute(pattern: re.Pattern[str], options: Options, text: str) -> tuple[str, int]:
    if options.regex:
        return pattern.subn(options.replace, text)
    # Literal replacement: no backslash or group interpretation.
    return pattern.subn(lambda _m: options.replace, text)


def decode(data: bytes) -> tuple[str, str] | None:
    """(text, encoding) or None for binary data."""
    if b"\x00" in data[:8192]:
        return None
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig"
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return None


def encode(text: str, encoding: str) -> bytes:
    if encoding == "utf-8-sig":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    return text.encode(encoding)


def _hidden(name: str, st: os.stat_result) -> bool:
    attributes = getattr(st, "st_file_attributes", 0)
    return name.startswith(".") or bool(attributes & stat.FILE_ATTRIBUTE_HIDDEN)


def candidate_files(folder: Path, options: Options) -> list[Path]:
    result: list[Path] = []
    stack = [folder]
    while stack:
        current = stack.pop()
        if safety.classify(str(current)) in (
            safety.PathVerdict.SYSTEM,
            safety.PathVerdict.OTHER_USER,
        ):
            continue
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name.casefold())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if options.skip_hidden and _hidden(entry.name, st):
                continue
            if entry.is_dir(follow_symlinks=False):
                if options.recursive:
                    stack.append(Path(entry.path))
            elif (
                entry.is_file(follow_symlinks=False)
                and any(fnmatch.fnmatch(entry.name.lower(), p.lower()) for p in options.patterns)
                and st.st_size <= options.max_file_size
            ):
                result.append(Path(entry.path))
    return result


def preview(
    folder: Path, options: Options, job: Job | None = None, max_lines: int = 200
) -> Preview:
    job = job or Job()
    pattern = compile_pattern(options)
    result = Preview()
    files = candidate_files(folder, options)
    for index, path in enumerate(files):
        job.progress(index, len(files), path.name)
        try:
            data = path.read_bytes()
            st = path.stat()
        except OSError:
            result.skipped_unreadable += 1
            continue
        decoded = decode(data)
        if decoded is None:
            result.skipped_binary += 1
            continue
        text, encoding = decoded
        new_text, count = substitute(pattern, options, text)
        if not count:
            continue
        lines: list[LineChange] = []
        old_lines = text.splitlines()
        new_lines = new_text.splitlines()
        if len(old_lines) == len(new_lines):
            for number, (before, after) in enumerate(zip(old_lines, new_lines, strict=True), 1):
                if before != after:
                    lines.append(LineChange(number, before, after))
                    if len(lines) >= max_lines:
                        break
        else:  # a pattern that spans or removes line breaks: show matches only
            for match in pattern.finditer(text):
                number = text.count("\n", 0, match.start()) + 1
                lines.append(
                    LineChange(
                        number, match.group(0), substitute(pattern, options, match.group(0))[0]
                    )
                )
                if len(lines) >= max_lines:
                    break
        result.files.append(FileMatches(path, encoding, count, lines, st.st_size, st.st_mtime))
    return result


@dataclass
class ApplyResult:
    files: int = 0
    replacements: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)
    journal: Path | None = None


def apply(
    files: list[FileMatches],
    options: Options,
    backup_root: Path,
    make_backup: bool = True,
    job: Job | None = None,
) -> ApplyResult:
    """Write the replacements. Files changed since the preview are skipped."""
    job = job or Job()
    pattern = compile_pattern(options)
    run_dir = backup_root / time.strftime("%Y%m%d-%H%M%S")
    entries: list[dict[str, str]] = []
    result = ApplyResult()
    for index, matches in enumerate(files):
        job.progress(index, len(files), matches.path.name)
        path = matches.path
        try:
            st = path.stat()
            if st.st_size != matches.size or abs(st.st_mtime - matches.modified) > 1e-6:
                result.failed.append((path, "changed"))
                continue
            if st.st_mode & stat.S_IWRITE == 0:
                result.failed.append((path, "read-only"))
                continue
            data = path.read_bytes()
            decoded = decode(data)
            if decoded is None:
                result.failed.append((path, "binary"))
                continue
            text, encoding = decoded
            new_text, count = substitute(pattern, options, text)
            backup = ""
            if make_backup:
                run_dir.mkdir(parents=True, exist_ok=True)
                target = run_dir / f"{index:05d}_{path.name}"
                shutil.copy2(path, target)
                backup = str(target)
            tmp = path.with_name(path.name + ".do-tmp")
            tmp.write_bytes(encode(new_text, encoding))
            shutil.copystat(path, tmp)
            os.replace(tmp, path)
            entries.append({"path": str(path), "backup": backup})
            result.files += 1
            result.replacements += count
        except (OSError, UnicodeEncodeError) as exc:
            result.failed.append((path, getattr(exc, "strerror", None) or str(exc)))
    if make_backup and entries:
        journal = run_dir / "journal.json"
        journal.write_text(
            json.dumps({"time": time.time(), "files": entries}, indent=1), encoding="utf-8"
        )
        result.journal = journal
    return result


def latest_journal(backup_root: Path) -> Path | None:
    if not backup_root.is_dir():
        return None
    journals = sorted(backup_root.glob("*/journal.json"))
    return journals[-1] if journals else None


def undo(journal: Path) -> tuple[int, list[tuple[Path, str]]]:
    data = json.loads(journal.read_text(encoding="utf-8"))
    restored = 0
    failed: list[tuple[Path, str]] = []
    for entry in data.get("files", []):
        target, backup = Path(entry["path"]), Path(entry["backup"])
        try:
            shutil.copy2(backup, target)
            restored += 1
        except OSError as exc:
            failed.append((target, exc.strerror or str(exc)))
    if not failed:
        shutil.rmtree(journal.parent, ignore_errors=True)
    return restored, failed
