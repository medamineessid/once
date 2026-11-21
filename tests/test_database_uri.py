"""Tests for storage/database.py's SQLite connection target (Sonar S8706).

A database path is not a connection string. It is turned into a percent-encoded
``file:`` URI so that characters which are URI syntax - a space, ``?``, ``#``,
``%`` - stay part of the file name.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from storage import database


def test_uri_encodes_spaces_and_uri_delimiters() -> None:
    uri = database._sqlite_uri(Path(r"C:\temp\a b?c#d%e.db"))

    assert uri.startswith("file:///")
    assert " " not in uri
    assert "?" not in uri
    assert "#" not in uri
    assert "%20" in uri
    assert "%3F" in uri
    assert "%23" in uri
    assert "%25" in uri


def test_database_path_with_spaces_hash_and_percent_round_trips(tmp_path: Path) -> None:
    # '?' cannot exist in a Windows file name, so the live round trip uses the
    # characters that can: space, '#', '%'. The URI escaping of '?' is pinned
    # by the test above.
    path = tmp_path / "a b#c%d.db"

    connection = database.connect(path)
    connection.execute("CREATE TABLE probe(value TEXT)")
    connection.execute("INSERT INTO probe VALUES ('kept')")
    connection.commit()
    connection.close()

    assert path.is_file()
    reopened = database.connect(path)
    try:
        assert reopened.execute("SELECT value FROM probe").fetchone()[0] == "kept"
    finally:
        reopened.close()


def test_two_databases_in_folders_with_uri_characters_stay_separate(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one %23" / "once.db"
    second = tmp_path / "one #" / "once.db"
    first.parent.mkdir()
    second.parent.mkdir()

    for path, marker in ((first, "first"), (second, "second")):
        connection = database.connect(path)
        connection.execute("CREATE TABLE probe(value TEXT)")
        connection.execute("INSERT INTO probe VALUES (?)", (marker,))
        connection.commit()
        connection.close()

    for path, marker in ((first, "first"), (second, "second")):
        connection = sqlite3.connect(database._sqlite_uri(path), uri=True)
        try:
            assert connection.execute("SELECT value FROM probe").fetchone()[0] == marker
        finally:
            connection.close()
