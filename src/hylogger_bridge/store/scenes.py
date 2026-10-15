# Purpose: keep the scientific scene a page was attached to, inside a caller-owned transaction.
import json
import sqlite3
from typing import Any


def put(connection: sqlite3.Connection, page_id: str, scene: dict[str, Any]) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO scenes VALUES (?,?)", (page_id, json.dumps(scene, sort_keys=True))
    )


def get(connection: sqlite3.Connection, page_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT scene FROM scenes WHERE page_id=?", (page_id,)).fetchone()
    if row is None:
        return None
    scene: dict[str, Any] = json.loads(row[0])
    return scene
