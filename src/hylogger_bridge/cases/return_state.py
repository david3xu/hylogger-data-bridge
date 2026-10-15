# Purpose: report observed chat-return state separately from immutable book evidence.
from typing import Any

from hylogger_bridge.book import BookStore
from hylogger_bridge.cases.dispatch import load_dispatches, load_session_binding


def return_state(store: BookStore) -> dict[str, Any]:
    folder, case = store.path.parent, store.path.stem
    binding = load_session_binding(folder, case)
    active = bool(binding)
    snapshot = store.snapshot()
    continuations = snapshot.get("continuations", [])
    phase = "connected" if active else "manual"
    attempts = 0
    if continuations:
        current = continuations[-1]
        if current["state"] == "completed":
            phase = "completed"
        elif current["state"] == "running":
            phase = "working"
        elif current["state"] == "failed":
            phase = "failed"
        elif active:
            phase = "pending"
            try:
                records = load_dispatches(folder, case)
                receipts = [
                    v
                    for v in records.values()
                    if v.get("continuation_id") == current["id"]
                    and v.get("generation") == (binding or {}).get("generation")
                ]
                if receipts:
                    latest = receipts[-1]
                    attempts = latest.get("attempts", 0)
                    phase = {
                        "dispatched": "queued",
                        "in_flight": "uncertain",
                        "failed": "failed",
                    }.get(latest.get("status"), "pending")
            except ValueError:
                phase = "failed"
    return {"active": active, "phase": phase, "attempts": attempts, "host": "Codex"}
