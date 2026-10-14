# Purpose: check that advice is consistent with the exact request it answers.
from typing import Any

from hylogger_bridge.contracts.check import ContractError, validate
from hylogger_bridge.contracts.digest import digest


def check_advice(request: dict[str, Any], advice: dict[str, Any]) -> None:
    """Reject advice that cites what the request never offered; it never authorises an action."""
    validate("AssessmentRequest", request)
    validate("Assessment", advice)
    offered = [item["id"] for item in request["candidates"]]
    shown = {item["evidence_id"] for item in request["evidence"]}
    picks = [item["candidate_id"] for item in advice["suggestions"]]
    ranks = [item["rank"] for item in advice["suggestions"]]
    cited = {ref for item in advice["suggestions"] for ref in item["evidence_ids"]}
    rules = [
        (len(set(offered)) == len(offered), "request repeats a candidate"),
        (advice["page_id"] == request["page_id"], "advice belongs to another page"),
        (advice["state_revision"] == request["state_revision"], "advice answers another revision"),
        (advice["request_hash"] == digest(request), "advice answers another request"),
        (set(picks) <= set(offered), "advice names a candidate the request lacks"),
        (len(set(picks)) == len(picks), "advice repeats a candidate"),
        (len(set(ranks)) == len(ranks), "advice repeats a rank"),
        (cited <= shown, "advice cites evidence the request lacks"),
    ]
    for holds, message in rules:
        if not holds:
            raise ContractError(message)
