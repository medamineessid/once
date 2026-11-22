from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from uuid import uuid4


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write one text file without truncating the previous file on failure.

    The payload goes to a unique sibling temporary file, which replaces the
    destination only after the whole write succeeded. An interrupted write
    leaves the previous file exactly as it was.
    """
    destination = Path(path)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding=encoding)
        temporary.replace(destination)
    except OSError:
        with suppress(OSError):
            temporary.unlink()
        raise


class RealFs:
    """Simple read-only filesystem facade used by scanner and validators."""

    @staticmethod
    def exists(path: str | os.PathLike[str]) -> bool:
        return Path(path).exists()

    @staticmethod
    def is_file(path: str | os.PathLike[str]) -> bool:
        return Path(path).is_file()

    @staticmethod
    def is_dir(path: str | os.PathLike[str]) -> bool:
        return Path(path).is_dir()

    @staticmethod
    def is_symlink(path: str | os.PathLike[str]) -> bool:
        return Path(path).is_symlink()

    @staticmethod
    def stat(path: str | os.PathLike[str], *, follow_symlinks: bool = True) -> os.stat_result:
        return Path(path).stat() if follow_symlinks else Path(path).stat(follow_symlinks=False)

    @staticmethod
    def access(path: str | os.PathLike[str], mode: int) -> bool:
        return os.access(path, mode)

    @staticmethod
    def same_volume(path_a: str | os.PathLike[str], path_b: str | os.PathLike[str]) -> bool:
        a = Path(path_a)
        b = Path(path_b)

        def nearest_existing(path: Path) -> Path:
            current = path
            while not current.exists():
                if current.parent == current:
                    return current
                current = current.parent
            return current

        first = nearest_existing(a)
        second = nearest_existing(b)
        return first.stat().st_dev == second.stat().st_dev
