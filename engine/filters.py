from __future__ import annotations

from datetime import date, datetime

from engine.models import FileEntry


def by_extension(entries: tuple[FileEntry, ...], extensions: set[str]) -> tuple[FileEntry, ...]:
    """Return entries whose suffix is within the provided extension set."""
    normalized = {ext.lower().lstrip(".") for ext in extensions}
    return tuple(entry for entry in entries if entry.suffix.lower().lstrip(".") in normalized)


def by_name(
    entries: tuple[FileEntry, ...],
    *,
    contains: str | None = None,
    starts_with: str | None = None,
    ends_with: str | None = None,
    case_sensitive: bool = False,
) -> tuple[FileEntry, ...]:
    """Filter on literal substrings without using regex."""

    def _normalize(value: str) -> str:
        return value if case_sensitive else value.casefold()

    contains_term = _normalize(contains) if contains is not None else None
    starts_term = _normalize(starts_with) if starts_with is not None else None
    ends_term = _normalize(ends_with) if ends_with is not None else None

    selected: list[FileEntry] = []
    for entry in entries:
        name = entry.name if case_sensitive else entry.name.casefold()
        if contains_term is not None and contains_term not in name:
            continue
        if starts_term is not None and not name.startswith(starts_term):
            continue
        if ends_term is not None and not name.endswith(ends_term):
            continue
        selected.append(entry)
    return tuple(selected)


def by_date(
    entries: tuple[FileEntry, ...],
    *,
    field: str = "modified",
    start: date | None = None,
    end: date | None = None,
) -> tuple[FileEntry, ...]:
    """Return entries whose mtime or birthtime falls inside a date range."""
    if field not in {"modified", "created"}:
        raise ValueError("field must be 'modified' or 'created'")

    def _as_date(value: int | None) -> date | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value / 1_000_000_000, tz=None).date()

    start_day = start
    end_day = end
    results: list[FileEntry] = []
    for entry in entries:
        candidate = entry.mtime_ns if field == "modified" else entry.birthtime_ns or entry.mtime_ns
        day = _as_date(candidate)
        if day is None:
            continue
        if start_day is not None and day < start_day:
            continue
        if end_day is not None and day > end_day:
            continue
        results.append(entry)
    return tuple(results)
