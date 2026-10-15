# Purpose: describe the expert and worker tools MCP clients may call.
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
CASE: dict[str, Any] = {
    "type": "string",
    "description": "Optional case_id. When omitted, uses the default database.",
}
BOUNDS: dict[str, Any] = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 2,
    "maxItems": 2,
    "description": "Interval bounds [top, bottom] in metres.",
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
    # Expert tools
    _tool(
        "start_case",
        (
            "Start or reuse a case for a real HyLogger package inside the authorised data folder. "
            "Returns case_id and page 1 evidence."
        ),
        {"package_id": TEXT, "target": BOUNDS, "reference": BOUNDS},
        ["package_id", "target", "reference"],
    ),
    _tool(
        "read_case",
        (
            "Read a case's pages, readable evidence, decision choice and note, and whether a human "
            "decision is pending a worker."
        ),
        {"case_id": TEXT},
        ["case_id"],
    ),
    _tool(
        "continue_case",
        (
            "Continue a case after an expert commits a decision in the browser book. "
            "Returns page 2 readable evidence, or asks the expert to decide if none is pending."
        ),
        {"case_id": TEXT, "target": BOUNDS, "reference": BOUNDS},
        ["case_id"],
    ),
    _tool(
        "open_book",
        (
            "Get the local HTTP URL to open the evidence book in the browser, reusing an active "
            "server if running."
        ),
        {"case_id": TEXT},
        ["case_id"],
    ),
    _tool(
        "find_packages",
        "Find supported packages inside the authorised data folder.",
        {"hole": {"type": "string", "description": "Optional hole identifier to filter by."}},
        [],
    ),
    _tool(
        "list_cases",
        "List existing case investigations and their status so conversations can reuse them.",
        {},
        [],
    ),
    # Worker tools (with optional case routing)
    _tool("read_book", "Read the authoritative book snapshot.", {"case": CASE}, []),
    _tool(
        "claim_delivery",
        "Claim the oldest pending delivery. Returns a Handoff holding the exact committed "
        "human choice and note, or null. Acknowledge it before writing anything.",
        {"worker": TEXT, "seconds": SECONDS, "case": CASE},
        ["worker"],
    ),
    _tool(
        "acknowledge_delivery",
        "Say this worker accepted its attempt. Repeating it renews the lease.",
        {"continuation_id": TEXT, "attempt": ATTEMPT, "seconds": SECONDS, "case": CASE},
        ["continuation_id", "attempt"],
    ),
    _tool(
        "fail_delivery",
        "Give an attempt back with an Error (contract v1); it is retried while attempts remain.",
        {
            "continuation_id": TEXT,
            "attempt": ATTEMPT,
            "error": {"type": "object"},
            "case": CASE,
        },
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
            "case": CASE,
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
            "case": CASE,
        },
        ["page_id", "expected_revision"],
    ),
    _tool(
        "read_attempts",
        "Read every delivery attempt and its own acknowledgement.",
        {"continuation_id": TEXT, "case": CASE},
        ["continuation_id"],
    ),
]
