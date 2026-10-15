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


EXPERT_TOOLS: list[dict[str, Any]] = [
    _tool(
        "start_case",
        (
            "Start or reuse a case for a real HyLogger package inside the authorised data folder. "
            "Returns case_id and page 1 evidence. REQUIRED for automatic return: pass the current "
            "conversation UUID as session_id, obtained from its shell CODEX_THREAD_ID or "
            "CODEX_SESSION_ID. Missing identity is refused before creating a case. "
            "Use manual_return=true only for explicit manual follow-up."
        ),
        {
            "package_id": TEXT,
            "target": BOUNDS,
            "reference": BOUNDS,
            "session_id": {
                "type": "string",
                "description": (
                    "Current conversation UUID. Required unless manual_return=true. Read it in the "
                    "calling chat shell; never guess or reuse a shared server process ID."
                ),
            },
            "manual_return": {
                "type": "boolean",
                "description": (
                    "Explicit manual follow-up instead of automatic return; omit session_id."
                ),
            },
            "workspace": {
                "type": "string",
                "description": (
                    "Optional path to the authorised workspace root containing HyLogger packages. "
                    "Defaults to the server's configured data root."
                ),
            },
        },
        ["package_id", "target", "reference"],
    ),
    _tool(
        "read_case",
        (
            "Read a case's pages, readable evidence, decision choice and note, and whether a human "
            "decision is pending a worker. Pass unbind=true to unbind session and stop automatic "
            "return."
        ),
        {
            "case_id": TEXT,
            "unbind": {
                "type": "boolean",
                "description": "Optional flag to unbind the session and stop automatic return.",
            },
        },
        ["case_id"],
    ),
    _tool(
        "continue_case",
        (
            "Continue a case after an expert commits a decision in the browser book. "
            "Returns successor evidence, or asks the expert to decide if none is pending. "
            "The existing browser book updates live; do not open another tab after continuation."
        ),
        {
            "case_id": TEXT,
            "continuation_id": TEXT,
            "decision_id": TEXT,
            "target": BOUNDS,
            "reference": BOUNDS,
            "session_id": {
                "type": "string",
                "description": "Optional conversation session UUID to update case binding.",
            },
            "workspace": {
                "type": "string",
                "description": (
                    "Optional path to the authorised workspace root to revalidate package access."
                ),
            },
            "unbind": {
                "type": "boolean",
                "description": "Optional flag to unbind the session and stop automatic return.",
            },
        },
        ["case_id"],
    ),
    _tool(
        "open_book",
        (
            "Get the local HTTP URL to open the evidence book in the browser, reusing an active "
            "server if running. Reuse an existing tab for this URL; open a right-side tab only "
            "on first presentation or an explicit reopen request. This tool does not open a tab."
        ),
        {"case_id": TEXT},
        ["case_id"],
    ),
    _tool(
        "find_packages",
        "Find supported packages inside the authorised data folder.",
        {
            "hole": {"type": "string", "description": "Optional hole identifier to filter by."},
            "workspace": {
                "type": "string",
                "description": (
                    "Optional path to the authorised workspace root to discover packages within. "
                    "Defaults to the server's configured data root."
                ),
            },
        },
        [],
    ),
    _tool(
        "list_cases",
        "List existing case investigations and their status so conversations can reuse them.",
        {
            "workspace": {
                "type": "string",
                "description": (
                    "Optional path to filter listed cases to those within the authorised workspace."
                ),
            },
        },
        [],
    ),
]

WORKER_TOOLS: list[dict[str, Any]] = [
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

TOOLS: list[dict[str, Any]] = EXPERT_TOOLS + WORKER_TOOLS
