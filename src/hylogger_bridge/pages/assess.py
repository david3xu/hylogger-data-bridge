# Purpose: prepare, then record, advice on a page; inference itself runs in between, unlocked.
import sqlite3
from typing import Any

from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.assess import check_advice
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.pages.actions import REGISTERED
from hylogger_bridge.store import state


def default_candidates() -> list[dict[str, Any]]:
    return [
        {"id": f"cand-{name}", "action_type": name, "arguments": {}} for name in sorted(REGISTERED)
    ]


def request_for(
    page: dict[str, Any], candidates: list[dict[str, Any]], instruction: str
) -> dict[str, Any]:
    """Observed evidence by reference. No numeric features exist yet, so none are invented."""
    return {
        "contract_version": 1,
        "page_id": page["id"],
        "state_revision": page["revision"],
        "question": page["question"],
        "instruction": instruction,
        "evidence": [
            {"evidence_id": e["id"], "kind": e["kind"], "state": e["state"], "features": {}}
            for e in page["evidence"]
        ],
        "candidates": candidates,
    }


def prepare(
    connection: sqlite3.Connection,
    page_id: str,
    expected_revision: int,
    candidates: list[dict[str, Any]],
    instruction: str,
) -> dict[str, Any]:
    """The validated request for a working page. Read-only: nothing is written."""
    page = state.find(state.read(connection), page_id, expected_revision)
    for item in candidates:
        if item.get("action_type") not in REGISTERED:
            raise ValueError("candidates must be registered action types")
    request = request_for(page, candidates, instruction)
    validate("AssessmentRequest", request)
    return request


def record(
    connection: sqlite3.Connection,
    request: dict[str, Any],
    advice: dict[str, Any],
) -> None:
    """Record advice only if its page is still the one it answered.

    Inference ran outside any transaction, so the page may have moved on or been locked. Advice
    for a changed page is refused rather than stored as if current; locked history is untouched.
    """
    check_advice(request, advice)
    book = state.read(connection)
    page = state.find(book, request["page_id"], request["state_revision"])
    if request_for(page, request["candidates"], request["instruction"]) != request:
        raise BookConflict("The page changed while the advice was computed", "stale_revision")
    # Advice is advisory metadata: it is recorded without counting a page revision, and it
    # goes stale on its own when the evidence moves past state_revision.
    page["assessment"] = advice
    state.put(book, page)
    detail = f"Assessment ({advice['origin']})"
    state.save(connection, book, "assessment_recorded", request["page_id"], detail)
