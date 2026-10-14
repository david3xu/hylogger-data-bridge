# Purpose: define the SQLite tables and stamp the schema version.
import sqlite3

VERSION = 1


class UnsupportedVersion(ValueError):
    """The database was written by a schema version this build does not support."""


def version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def require_supported(connection: sqlite3.Connection) -> int:
    """Return 0 (unstamped or legacy) or VERSION; refuse anything else before any write."""
    found = version(connection)
    if found not in (0, VERSION):
        raise UnsupportedVersion(
            f"book database is schema version {found}; this build reads 0 or {VERSION}"
        )
    return found


def create(connection: sqlite3.Connection) -> None:
    require_supported(connection)
    connection.execute("CREATE TABLE IF NOT EXISTS book (id INTEGER PRIMARY KEY, data TEXT)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
        "data TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS jobs (page_id TEXT PRIMARY KEY, status TEXT NOT NULL)"
    )
    # One continuation per decision and per page: duplicates fail in the database itself.
    connection.execute(
        "CREATE TABLE IF NOT EXISTS continuations ("
        "id TEXT PRIMARY KEY, "
        "decision_id TEXT NOT NULL UNIQUE, "
        "page_id TEXT NOT NULL UNIQUE, "
        "successor_id TEXT NOT NULL, "
        "locked_revision INTEGER NOT NULL, "
        "state TEXT NOT NULL CHECK (state IN ('pending','running','completed','failed')), "
        "attempts INTEGER NOT NULL CHECK (attempts >= 0), "
        "max_attempts INTEGER NOT NULL CHECK (max_attempts >= 1), "
        "claimed_by TEXT, lease_expires_at TEXT, acknowledged_at TEXT, last_error TEXT, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    connection.execute(f"PRAGMA user_version = {VERSION}")
