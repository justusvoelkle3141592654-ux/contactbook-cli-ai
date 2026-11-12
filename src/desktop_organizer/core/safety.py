"""Guards against touching protected locations.

Every tool that reads or changes files checks user-chosen paths here first. The check
uses Windows path semantics (case-insensitive, both separators) independent of the
platform the tests run on.
"""

from __future__ import annotations

import ntpath
import os
from collections.abc import Mapping
from enum import Enum


class PathVerdict(Enum):
    ALLOWED = "allowed"
    SYSTEM = "system"  # Windows, Program Files, ProgramData
    OTHER_USER = "other_user"  # another user's profile
    DRIVE_ROOT = "drive_root"  # C:\ itself; allowed only with explicit confirmation


def _norm(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path)).rstrip("\\")


def _is_within(path: str, parent: str) -> bool:
    return path == parent or path.startswith(parent + "\\")


def classify(path: str, environ: Mapping[str, str] | None = None) -> PathVerdict:
    env = os.environ if environ is None else environ
    target = _norm(path)

    drive, rest = ntpath.splitdrive(target)
    if drive and rest in ("", "\\"):
        return PathVerdict.DRIVE_ROOT

    system_roots = [
        env.get("SystemRoot") or env.get("WINDIR") or "C:\\Windows",
        env.get("ProgramFiles") or "C:\\Program Files",
        env.get("ProgramFiles(x86)") or "C:\\Program Files (x86)",
        env.get("ProgramData") or "C:\\ProgramData",
    ]
    for root in system_roots:
        if _is_within(target, _norm(root)):
            return PathVerdict.SYSTEM

    profile = env.get("USERPROFILE")
    if profile:
        users_dir = _norm(ntpath.dirname(_norm(profile)))
        own = _norm(profile)
        if _is_within(target, users_dir) and target != users_dir and not _is_within(target, own):
            return PathVerdict.OTHER_USER
        if target == users_dir:
            return PathVerdict.OTHER_USER

    return PathVerdict.ALLOWED
