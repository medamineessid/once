from __future__ import annotations

import ctypes
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from engine.errors import PlanError
from engine.models import FileEntry


@dataclass(frozen=True)
class SkippedItem:
    path: str
    reason: str


@dataclass(frozen=True)
class ScanResult:
    entries: tuple[FileEntry, ...]
    skipped: tuple[SkippedItem, ...]


def _is_hidden_windows(path: Path) -> bool:
    attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if attributes == 0xFFFFFFFF:
        return False
    return bool(attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))


def _is_hidden_other(name: str) -> bool:
    return name.startswith(".")


def _birthtime_ns(path: Path, fallback: os.stat_result) -> int | None:
    candidate = getattr(fallback, "st_birthtime", None)
    if isinstance(candidate, (int, float)) and candidate > 0:
        return int(candidate * 1_000_000_000)
    direct = path.stat(follow_symlinks=False)
    candidate = getattr(direct, "st_birthtime", None)
    if isinstance(candidate, (int, float)) and candidate > 0:
        return int(candidate * 1_000_000_000)
    return fallback.st_mtime_ns


def _hidden_for(path: Path, stat_result: os.stat_result) -> bool:
    if os.name == "nt":
        return _is_hidden_other(path.name) or _is_hidden_windows(path)
    return _is_hidden_other(path.name)


def scan_folder(
    folder: str | os.PathLike[str],
    *,
    recursive: bool = False,
    include_hidden: bool = False,
) -> ScanResult:
    """Scan a folder and return immutable file entries plus skipped items."""
    root = Path(folder)
    if not root.exists():
        raise PlanError(f"Folder is missing: {root}")
    if not root.is_dir():
        raise PlanError(f"Path is not a directory: {root}")

    entries: list[FileEntry] = []
    skipped: list[SkippedItem] = []

    def walk(current: Path) -> None:
        try:
            with os.scandir(current) as iterator:
                children = sorted(iterator, key=lambda item: item.name.casefold())
        except OSError:
            raise PlanError(f"Folder is unreadable: {current}") from None

        for entry in children:
            path = Path(entry.path)
            try:
                stat_result = entry.stat(follow_symlinks=False)
            except OSError:
                skipped.append(SkippedItem(str(path), "Could not read: permission denied"))
                continue

            if entry.is_dir(follow_symlinks=False):
                if not recursive:
                    skipped.append(SkippedItem(str(path), "Folder"))
                    continue
                if not include_hidden and _hidden_for(path, stat_result):
                    skipped.append(SkippedItem(str(path), "Hidden file"))
                    continue
                walk(path)
                continue

            if entry.is_symlink() or bool(stat_result.st_mode & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                skipped.append(SkippedItem(str(path), "Shortcut or link"))
                continue

            if not include_hidden and _hidden_for(path, stat_result):
                skipped.append(SkippedItem(str(path), "Hidden file"))
                continue

            if not entry.is_file(follow_symlinks=False):
                skipped.append(SkippedItem(str(path), "Folder"))
                continue

            entries.append(
                FileEntry(
                    path=path,
                    name=path.name,
                    stem=path.stem,
                    suffix=path.suffix,
                    size=stat_result.st_size,
                    mtime_ns=stat_result.st_mtime_ns,
                    birthtime_ns=_birthtime_ns(path, stat_result),
                    is_hidden=_hidden_for(path, stat_result),
                )
            )

    walk(root)
    entries.sort(key=lambda item: (item.name.casefold(), item.name, str(item.path)))
    skipped.sort(key=lambda item: (item.path.casefold(), item.path))
    return ScanResult(entries=tuple(entries), skipped=tuple(skipped))
