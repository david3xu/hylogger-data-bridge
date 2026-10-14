# Purpose: describe the worker tools MCP clients may call; each maps to one shared operation.
from typing import Any

TEXT: dict[str, Any] = {"type": "string"}
REVISION: dict[str, Any] = {"type": "integer", "minimum": 0}
ATTEMPT: dict[str, Any] = {
    "type": "integer",
    "minimum": 1,
    "maximum": 10,
    "description": "Copy the attempt from your own Handoff. Never guess or reuse another's.",
}
SECONDS: dict[str, Any] = {"type": "number", "minimum": 1, "maximum": 3600}
CLAIM: dict[str, Any] = {
    "type": ["object", "null"],
    "description": "{continuation_id, attempt} from your Handoff, or null on a page with none.",
}


def _tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    return {"name": name, "description": description, "inputSchema": schema}


TOOLS: list[dict[str, Any]] = [
    _tool("read_book", "Read the authoritative book snapshot.", {}, []),
    _tool(
        "claim_delivery",
        "Claim the oldest pending delivery. Returns a Handoff holding the exact committed "
        "human choice and note, or null. Acknowledge it before writing anything.",
        {"worker": TEXT, "seconds": SECONDS},
        ["worker"],
    ),
    _tool(
        "acknowledge_delivery",
        "Say this worker accepted its attempt. Repeating it renews the lease.",
        {"continuation_id": TEXT, "attempt": ATTEMPT, "seconds": SECONDS},
        ["continuation_id", "attempt"],
    ),
    _tool(
        "fail_delivery",
        "Give an attempt back with an Error (contract v1); it is retried while attempts remain.",
        {"continuation_id": TEXT, "attempt": ATTEMPT, "error": {"type": "object"}},
        ["continuation_id", "attempt", "error"],
    ),
    _tool(
        "submit_evidence",
        "Add one Evidence item to the working page. State partial or failed results honestly.",
        {
            "page_id": TEXT,
            "expected_revision": REVISION,
            "evidence": {"type": "object"},
            "claim": CLAIM,
        },
        ["page_id", "expected_revision", "evidence", "claim"],
    ),
    {
        "name": "submit_result",
        "description": "Finish the working page with a Completion (schemas/v1.json): complete, "
        "partial or failed. Retrying the same request_id is safe.",
        "inputSchema": {"type": "object"},
    },
    _tool(
        "request_assessment",
        "Ask the local provider for advice. Advice never authorises an action.",
        {
            "page_id": TEXT,
            "expected_revision": REVISION,
            "candidates": {"type": "array"},
            "instruction": TEXT,
        },
        ["page_id", "expected_revision"],
    ),
    _tool(
        "read_attempts",
        "Read every delivery attempt and its own acknowledgement.",
        {"continuation_id": TEXT},
        ["continuation_id"],
    ),
]
