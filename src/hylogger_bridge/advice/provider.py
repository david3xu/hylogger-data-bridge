# Purpose: the assessment provider interface and two clearly labelled stand-ins.
from typing import Any, Protocol

from hylogger_bridge.contracts.digest import digest


class Provider(Protocol):
    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        """Answer one AssessmentRequest with one Assessment for exactly that request."""
        ...


def _advice(request: dict[str, Any], at: str, version: str) -> dict[str, Any]:
    key = digest(request)
    return {
        "contract_version": 1,
        "id": f"assess-{key[:16]}",
        "page_id": request["page_id"],
        "state_revision": request["state_revision"],
        "model_version": version,
        "origin": "fixture",
        "status": "available",
        "request_hash": key,
        "suggestions": [],
        "evidence_gaps": [],
        "uncertainty": None,
        "limitations": [],
        "created_at": at,
    }


class FixtureProvider:
    """Orders candidates as given. No model produced this; it authorises nothing."""

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        advice = _advice(request, at, "fixture-v1")
        advice["suggestions"] = [
            {
                "candidate_id": item["id"],
                "rank": rank,
                "rationale": "Fixture ordering for interface development; no model produced this.",
                "evidence_ids": [],
            }
            for rank, item in enumerate(request["candidates"], start=1)
        ]
        advice["evidence_gaps"] = ["The fixture does not assess evidence gaps."]
        advice["limitations"] = [
            "Labelled fixture: no trained model was consulted.",
            "A ranking never authorises an action.",
        ]
        return advice


class UnavailableProvider:
    """No local model is installed. Manual or deterministic work stays possible."""

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        advice = _advice(request, at, "none-installed")
        advice["status"] = "unavailable"
        advice["limitations"] = ["No local model is installed, so there is no advice."]
        return advice
