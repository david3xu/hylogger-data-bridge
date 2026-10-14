# Purpose: check the book rules that JSON Schema cannot express.
from typing import Any

from hylogger_bridge.contracts.check import ContractError, validate

Pages = dict[str, dict[str, Any]]


def _parent(page: dict[str, Any], pages: Pages) -> None:
    held = [item["id"] for item in page["evidence"]]
    if len(set(held)) != len(held):
        raise ContractError(f"page {page['id']} repeats an evidence id")
    if page["parent_id"] is None:
        return
    parent = pages.get(page["parent_id"])
    if parent is None or parent["decision"] is None:
        raise ContractError(f"page {page['id']} has no locked parent")
    if parent["decision"]["successor_id"] != page["id"]:
        raise ContractError(f"page {page['id']} is not its parent's successor")


def _decided(page: dict[str, Any], pages: Pages) -> None:
    decision, step = page["decision"], page["continuation"]
    if decision is None:
        return
    locked = decision["locked_revision"] == page["revision"]
    cited = set(decision["evidence_ids"]) <= {item["id"] for item in page["evidence"]}
    child = pages.get(decision["successor_id"], {}).get("parent_id") == page["id"]
    link = (step["page_id"], step["decision_id"], step["successor_id"], step["locked_revision"])
    want = (page["id"], decision["id"], decision["successor_id"], decision["locked_revision"])
    rules = [
        (decision["page_id"] == page["id"], "decision belongs to another page"),
        (locked, "decision was not locked at the page revision"),
        (cited, "decision cites evidence the page lacks"),
        (child, "decision successor is missing or not a child"),
        (link == want, "continuation does not match its decision"),
    ]
    for holds, message in rules:
        if not holds:
            raise ContractError(f"page {page['id']}: {message}")


def check_book(book: dict[str, Any]) -> None:
    validate("Book", book)
    pages: Pages = {page["id"]: page for page in book["pages"]}
    if len(pages) != len(book["pages"]):
        raise ContractError("page ids repeat")
    if book["current_page_id"] not in pages:
        raise ContractError("current page is not in the book")
    for page in pages.values():
        _parent(page, pages)
        _decided(page, pages)
    sequences = [event["sequence"] for event in book["events"]]
    if sequences != sorted(set(sequences)) or (sequences and sequences[-1] > book["sequence"]):
        raise ContractError("event sequences must increase and not pass the book sequence")
