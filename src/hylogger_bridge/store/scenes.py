# Purpose: keep the scientific scene a page is attached to; once set it never changes.
import hashlib
import json
import sqlite3
from typing import Any

from hylogger_bridge.conflict import BookConflict


def fingerprint(scene: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()


def get(connection: sqlite3.Connection, page_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT scene FROM scenes WHERE page_id=?", (page_id,)).fetchone()
    if row is None:
        return None
    scene: dict[str, Any] = json.loads(row[0])
    return scene


def put(connection: sqlite3.Connection, page_id: str, scene: dict[str, Any]) -> bool:
    """Attach once. An identical repeat changes nothing; any other scene needs a new page.

    Persisted evidence takes its meaning from the scene, so replacing it would silently change
    what existing evidence says. True means a scene was newly attached.
    """
    existing = get(connection, page_id)
    if existing is None:
        connection.execute(
            "INSERT INTO scenes VALUES (?,?)", (page_id, json.dumps(scene, sort_keys=True))
        )
        return True
    if existing != scene:
        raise BookConflict(
            "This page is attached to a different scientific scene; use a new page", "request_reuse"
        )
    return False
