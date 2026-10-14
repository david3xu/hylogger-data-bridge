# Purpose: worker operations shared by the HTTP and MCP adapters; validate, then call the store.
from collections.abc import Callable
from typing import Any

from hylogger_bridge.book import BookStore
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events.fence import check_claim

Operation = Callable[[BookStore, Any], Any]


def _shape(raw: Any, required: set[str], optional: frozenset[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(raw, dict) or not required <= set(raw) <= required | optional:
        raise ValueError(f"arguments must hold {sorted(required)} and may hold {sorted(optional)}")
    return raw


def _seconds(args: dict[str, Any]) -> float:
    value = args.get("seconds", 60)
    if isinstance(value, bool) or not isinstance(value, int | float) or not 1 <= value <= 3600:
        raise ValueError("seconds must be a number from 1 to 3600")
    return float(value)


def _claim(args: dict[str, Any]) -> dict[str, Any]:
    """The attempt always comes from the worker's own Handoff; it is checked, never filled in."""
    claim = {"continuation_id": args["continuation_id"], "attempt": args["attempt"]}
    check_claim(claim)
    return claim


def read_book(store: BookStore, raw: Any) -> dict[str, Any]:
    _shape(raw, set())
    return store.snapshot()


def claim_delivery(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"worker"}, frozenset({"seconds"}))
    validate("Id", args["worker"])
    return {"handoff": store.claim_delivery(args["worker"], _seconds(args))}


def acknowledge_delivery(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"continuation_id", "attempt"}, frozenset({"seconds"}))
    claim = _claim(args)
    return store.acknowledge_delivery(claim["continuation_id"], claim["attempt"], _seconds(args))


def fail_delivery(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"continuation_id", "attempt", "error"})
    claim = _claim(args)
    return store.fail_delivery(claim["continuation_id"], claim["attempt"], args["error"])


def submit_evidence(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"page_id", "expected_revision", "evidence", "claim"})
    if not isinstance(args["evidence"], dict):
        raise ValueError("evidence must be an object")
    validate("Id", args["page_id"])
    return store.add_evidence(
        args["page_id"], args["expected_revision"], args["evidence"], args["claim"]
    )


def submit_result(store: BookStore, raw: Any) -> dict[str, Any]:
    return store.submit_result(raw)


def request_assessment(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"page_id", "expected_revision"}, frozenset({"candidates", "instruction"}))
    validate("Id", args["page_id"])
    instruction = args.get("instruction", "")
    if not isinstance(instruction, str):
        raise ValueError("instruction must be text")
    candidates = args.get("candidates")
    if candidates is not None and not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    return store.request_assessment(
        args["page_id"], args["expected_revision"], candidates, instruction
    )


def read_attempts(store: BookStore, raw: Any) -> dict[str, Any]:
    args = _shape(raw, {"continuation_id"})
    validate("Id", args["continuation_id"])
    return {"attempts": store.attempts(args["continuation_id"])}


# There is deliberately no operation that records a human decision or a scientific approval.
OPERATIONS: dict[str, Operation] = {
    "read_book": read_book,
    "claim_delivery": claim_delivery,
    "acknowledge_delivery": acknowledge_delivery,
    "fail_delivery": fail_delivery,
    "submit_evidence": submit_evidence,
    "submit_result": submit_result,
    "request_assessment": request_assessment,
    "read_attempts": read_attempts,
}
