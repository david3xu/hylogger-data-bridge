# Purpose: the start of a dedicated real-data book; the default synthetic book is untouched.
from typing import Any

from hylogger_bridge.pages.make import new_page


def start(run_id: str, title: str, question: str, summary: str, progress: str) -> dict[str, Any]:
    """A first page with truthful text, for a book whose source is `live`."""
    for label, value in (
        ("run_id", run_id),
        ("title", title),
        ("question", question),
        ("summary", summary),
        ("progress", progress),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be non-empty text")
    page = new_page(1)
    page.update(title=title, question=question, summary=summary, progress=progress)
    return {"run_id": run_id, "source": "live", "page": page}
