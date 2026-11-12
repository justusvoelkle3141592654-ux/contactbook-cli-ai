"""Measure how much space folders, files and file types use. Pure logic, no UI."""

from __future__ import annotations

import heapq
import os
import shutil
import stat
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from desktop_organizer.core import safety
from desktop_organizer.core.jobs import Job


@dataclass
class Node:
    name: str
    path: Path
    size: int = 0
    files: int = 0
    modified: float = 0.0
    children: list[Node] = field(default_factory=list)
    own_files_size: int = 0  # files directly in this folder

    def sorted_children(self) -> list[Node]:
        return sorted(self.children, key=lambda n: -n.size)


@dataclass
class Analysis:
    root: Node
    largest: list[tuple[int, str, float]]  # (size, path, modified)
    types: dict[str, tuple[int, int]]  # extension -> (count, size)
    errors: int = 0
    disk_total: int = 0
    disk_free: int = 0


def _hidden(name: str, st: os.stat_result) -> bool:
    attributes = getattr(st, "st_file_attributes", 0)
    return name.startswith(".") or bool(attributes & stat.FILE_ATTRIBUTE_HIDDEN)


def analyze(
    folder: Path,
    include_hidden: bool = False,
    top_files: int = 100,
    job: Job | None = None,
) -> Analysis:
    job = job or Job()
    largest: list[tuple[int, str, float]] = []
    types: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    errors = 0
    counter = 0

    root = Node(folder.name or str(folder), folder)
    # Iterative post-order walk: avoids recursion limits on deep trees.
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, done = stack.pop()
        if done:
            node.size = node.own_files_size + sum(c.size for c in node.children)
            node.files += sum(c.files for c in node.children)
            node.modified = max([node.modified, *(c.modified for c in node.children)])
            continue
        stack.append((node, True))
        if safety.classify(str(node.path)) in (
            safety.PathVerdict.SYSTEM,
            safety.PathVerdict.OTHER_USER,
        ):
            errors += 1
            continue
        try:
            entries = list(os.scandir(node.path))
        except OSError:
            errors += 1
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                errors += 1
                continue
            if not include_hidden and _hidden(entry.name, st):
                continue
            if entry.is_dir(follow_symlinks=False):
                child = Node(entry.name, Path(entry.path))
                node.children.append(child)
                stack.append((child, False))
            elif entry.is_file(follow_symlinks=False):
                counter += 1
                if counter % 500 == 0:
                    job.progress(counter, 0, entry.path)
                size = st.st_size
                node.own_files_size += size
                node.files += 1
                node.modified = max(node.modified, st.st_mtime)
                suffix = Path(entry.name).suffix.lower() or "-"
                types[suffix][0] += 1
                types[suffix][1] += size
                item = (size, entry.path, st.st_mtime)
                if len(largest) < top_files:
                    heapq.heappush(largest, item)
                elif size > largest[0][0]:
                    heapq.heapreplace(largest, item)
    job.progress(counter, counter, "")
    try:
        usage = shutil.disk_usage(folder)
        disk_total, disk_free = usage.total, usage.free
    except OSError:
        disk_total = disk_free = 0
    return Analysis(
        root=root,
        largest=sorted(largest, reverse=True),
        types={k: (v[0], v[1]) for k, v in types.items()},
        errors=errors,
        disk_total=disk_total,
        disk_free=disk_free,
    )


def find_node(root: Node, path: Path) -> Node | None:
    if root.path == path:
        return root
    for child in root.children:
        if path == child.path or child.path in path.parents:
            return find_node(child, path)
    return None
