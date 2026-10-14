# Purpose: check the book rules that JSON Schema cannot express.
from typing import Any

from hylogger_bridge.contracts.check import ContractError, validate

Pages = dict[str, dict[str, Any]]


def _parent(page: dict[str, Any], pages: Pages) -> None:
    held = [item["id"] for item in page["evidence"]]
    if len(set(held)) != len(held):
        raise ContractError(f"page {page['id']} repeats an evidence id")
    if page["parent_id"] is None:
        if page["number"] != 1:
            raise ContractError(f"page {page['id']} starts the book but is not number 1")
        return
    parent = pages.get(page["parent_id"])
    if parent is None or parent["decision"] is None:
        raise ContractError(f"page {page['id']} has no locked parent")
    if parent["decision"]["successor_id"] != page["id"]:
        raise ContractError(f"page {page['id']} is not its parent's successor")
    if page["number"] != parent["number"] + 1:
        raise ContractError(f"page {page['id']} breaks the page numbering")


def _chain(pages: Pages, current: str) -> None:
    if sum(page["parent_id"] is None for page in pages.values()) != 1:
        raise ContractError("the book must have exactly one first page")
    for page in pages.values():
        _parent(page, pages)
    if current not in pages:
        raise ContractError("current page is not in the book")
    if [page["id"] for page in pages.values() if page["status"] != "locked"] != [current]:
        raise ContractError("current page must be the one unlocked page at the end of the chain")


def _decided(page: dict[str, Any], pages: Pages) -> None:
    decision = page["decision"]
    if decision is None:
        return
    locked = decision["locked_revision"] == page["revision"]
    cited = set(decision["evidence_ids"]) <= {item["id"] for item in page["evidence"]}
    child = pages.get(decision["successor_id"], {}).get("parent_id") == page["id"]
    rules = [
        (decision["page_id"] == page["id"], "decision belongs to another page"),
        (locked, "decision was not locked at the page revision"),
        (cited, "decision cites evidence the page lacks"),
        (child, "decision successor is missing or not a child"),
    ]
    for holds, message in rules:
        if not holds:
            raise ContractError(f"page {page['id']}: {message}")


def _delivery(pages: Pages, continuations: list[dict[str, Any]]) -> None:
    steps = {step["page_id"]: step for step in continuations}
    if len(steps) != len(continuations) or len({s["id"] for s in continuations}) != len(steps):
        raise ContractError("continuations repeat a page or an id")
    if not set(steps) <= set(pages):
        raise ContractError("a continuation names an unknown page")
    for page in pages.values():
        decision, step = page["decision"], steps.get(page["id"])
        # A decision of unknown origin is history; it is never delivered to an agent.
        dispatched = decision is not None and decision["actor"]["kind"] == "human"
        if step is None and dispatched:
            raise ContractError(f"page {page['id']} has no continuation")
        if step is not None and not dispatched:
            raise ContractError(f"page {page['id']} must not have a continuation")
        if step is None:
            continue
        link = (step["decision_id"], step["successor_id"], step["locked_revision"])
        if link != (decision["id"], decision["successor_id"], decision["locked_revision"]):
            raise ContractError(f"page {page['id']} continuation does not match its decision")
        if step["attempts"] > step["max_attempts"]:
            raise ContractError(f"page {page['id']} continuation exceeds its attempt bound")


def check_book(book: dict[str, Any]) -> None:
    validate("Book", book)
    pages: Pages = {page["id"]: page for page in book["pages"]}
    if len(pages) != len(book["pages"]):
        raise ContractError("page ids repeat")
    _chain(pages, book["current_page_id"])
    for page in pages.values():
        _decided(page, pages)
    _delivery(pages, book["continuations"])
    sequences = [event["sequence"] for event in book["events"]]
    if sequences != sorted(set(sequences)) or (sequences and sequences[-1] > book["sequence"]):
        raise ContractError("event sequences must increase and not pass the book sequence")
