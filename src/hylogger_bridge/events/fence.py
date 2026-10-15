# Purpose: let only the holder of a delivery's current, acknowledged claim write to its page.
import sqlite3
from datetime import datetime
from typing import Any

from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events.claim import expire
from hylogger_bridge.events.runner import RUNNER
from hylogger_bridge.store import cont


def check_claim(claim: object) -> None:
    """A claim is exactly a delivery ID and an attempt number from 1 to 10."""
    if claim is None:
        return
    if not isinstance(claim, dict) or set(claim) != {"continuation_id", "attempt"}:
        raise ValueError("claim must hold continuation_id and attempt")
    attempt = claim["attempt"]
    if type(attempt) is not int or not 1 <= attempt <= 10:
        raise ValueError("claim attempt must be an integer from 1 to 10")
    validate("Id", claim["continuation_id"])


def fence(
    connection: sqlite3.Connection,
    page: dict[str, Any],
    claim: dict[str, Any] | None,
    at: datetime,
) -> dict[str, Any] | None:
    """The delivery a write on this page belongs to, or None when the page follows none.

    Every worker write passes here: a result and incremental evidence alike. An old attempt,
    an expired lease, an unacknowledged claim or a claim for another page is refused.
    """
    check_claim(claim)
    expire(connection, at)
    step = None if page["parent_id"] is None else cont.for_page(connection, page["parent_id"])
    if step is None:
        if claim is not None:
            raise BookConflict("This page has no delivery to claim", "unrelated_page")
        return None
    if claim is None or claim["continuation_id"] != step["id"]:
        raise BookConflict("This page follows a delivery; present its claim", "unrelated_page")
    if step["state"] != "running" or step["attempts"] != claim["attempt"]:
        raise BookConflict("This delivery claim is no longer current", "claim_expired")
    if step["claimed_by"] == RUNNER:
        raise BookConflict("The synthetic runner holds this delivery", "claim_expired")
    if step["acknowledged_at"] is None:
        raise BookConflict("Acknowledge the delivery before writing to its page", "not_ready")
    return step
