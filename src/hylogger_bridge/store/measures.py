# Purpose: bind calculated features to the exact persisted evidence a trusted measurement wrote.
import hashlib
import json
import sqlite3
from typing import Any

FIELDS = ("id", "label", "value", "source", "kind", "origin", "state")


def evidence_hash(item: dict[str, Any]) -> str:
    """What the evidence says, so a same-ID item with other content is not the same evidence."""
    body = {key: item[key] for key in FIELDS}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def put(
    connection: sqlite3.Connection, page_id: str, item: dict[str, Any], features: dict[str, Any]
) -> None:
    """Written in the same transaction as the evidence, never separately."""
    connection.execute(
        "INSERT INTO measurements VALUES (?,?,?,?)",
        (page_id, item["id"], evidence_hash(item), json.dumps(features, sort_keys=True)),
    )


def trusted(connection: sqlite3.Connection, page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Features only for evidence still exactly as a trusted measurement persisted it."""
    rows = connection.execute(
        "SELECT evidence_id, fingerprint, features FROM measurements WHERE page_id=?",
        (page["id"],),
    ).fetchall()
    found: dict[str, dict[str, Any]] = {}
    for evidence_id, fingerprint, features in rows:
        item = next((e for e in page["evidence"] if e["id"] == evidence_id), None)
        if item is not None and evidence_hash(item) == fingerprint:
            found[evidence_id] = json.loads(features)
    return found
