# Purpose: build a new working page in the v1 contract shape.
import uuid
from typing import Any

from hylogger_bridge.clock import now


def new_page(number: int, parent_id: str | None = None) -> dict[str, Any]:
    timestamp = now()
    return {
        "id": str(uuid.uuid4()),
        "number": number,
        "parent_id": parent_id,
        "template": "investigation" if number == 1 else "candidate_evidence",
        "template_version": 1,
        "title": "An unfamiliar drill hole" if number == 1 else "Follow-up investigation",
        "question": "Show spectral-change intervals that overlap assay records.",
        "status": "draft",
        "revision": 0,
        "summary": "A synthetic case for exploring the live investigation book.",
        "progress": "Ready to start the synthetic example",
        "evidence": [],
        "outcome": None,
        "errors": [],
        "decision": None,
        "action": None,
        "assessment": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "scientific_review": "unreviewed",
        "demo_running": False,
    }
