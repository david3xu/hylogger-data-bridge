# Purpose: serve the worker tools over MCP stdio; stdout carries only JSON-RPC messages.
import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.mcp.tools import TOOLS
from hylogger_bridge.work import OPERATIONS

VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
NOTE = (
    "Tools for a worker on the live investigation book. Claim a delivery, acknowledge it, "
    "write evidence or a result with the attempt from your own Handoff, and report partial or "
    "failed work honestly. No tool records a human decision or scientific approval."
)


def _reply(ident: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _fault(ident: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def _content(value: Any, failed: bool) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value)}], "isError": failed}


def call(store: BookStore, name: str, arguments: Any) -> dict[str, Any]:
    """Run one tool. A refusal is a tool result carrying the contract's Error, not a crash."""
    try:
        return _content(OPERATIONS[name](store, arguments), False)
    except BookConflict as error:
        return _content({"error": str(error), "code": error.code, "retryable": False}, True)
    except ValueError as error:
        body = {"error": str(error) or "Invalid request", "code": "invalid_request"}
        return _content({**body, "retryable": False}, True)


def handle(store: BookStore, message: Any) -> dict[str, Any] | None:
    """Answer one JSON-RPC message; notifications and stray responses get no answer."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _fault(None, -32600, "Not a JSON-RPC 2.0 request")
    method, ident = message.get("method"), message.get("id")
    if not isinstance(method, str) or ident is None:
        return None
    params = message.get("params")
    if not isinstance(params, dict):
        params = {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _reply(
            ident,
            {
                "protocolVersion": asked if asked in VERSIONS else VERSIONS[0],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hylogger-bridge", "version": "0.1.0"},
                "instructions": NOTE,
            },
        )
    if method == "ping":
        return _reply(ident, {})
    if method == "tools/list":
        return _reply(ident, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if name not in OPERATIONS:
            return _fault(ident, -32602, f"Unknown tool: {name}")
        return _reply(ident, call(store, name, params.get("arguments") or {}))
    return _fault(ident, -32601, f"Method not found: {method}")


def serve(store: BookStore, source: TextIO, sink: TextIO) -> None:
    """One JSON message per line in, one per line out; nothing else is ever written to sink."""
    for line in source:
        if not line.strip():
            continue
        reply: dict[str, Any] | None
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply = _fault(None, -32700, "Parse error")
        else:
            try:
                reply = handle(store, message)
            except Exception as error:  # keep serving; the cause goes to stderr, not stdout
                print(f"internal error: {error!r}", file=sys.stderr)
                ident = message.get("id") if isinstance(message, dict) else None
                reply = _fault(ident, -32603, f"Internal error: {type(error).__name__}")
        if reply is not None:
            sink.write(json.dumps(reply) + "\n")
            sink.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="HyLogger worker tools over MCP stdio")
    parser.add_argument("--db", type=Path, default=Path("outputs/live-book/demo.sqlite3"))
    args = parser.parse_args()
    # The HTTP service owns startup recovery; a tool process must never interrupt its jobs.
    serve(BookStore(args.db), sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
