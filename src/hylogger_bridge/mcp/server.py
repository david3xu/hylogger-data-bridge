# Purpose: serve the expert and worker tools over MCP stdio; stdout carries only JSON-RPC messages.
import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from hylogger_bridge.advice.select import Loader, add_option, startup
from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.cases.registry import CaseRegistry, ServerLauncher
from hylogger_bridge.mcp.tools import EXPERT_TOOLS, TOOLS
from hylogger_bridge.work import OPERATIONS

VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
NOTE = (
    "Tools for expert evidence review and worker investigation on live books. "
    "Expert tools prepare, read, continue and open cases. "
    "Worker tools claim deliveries, acknowledge them, and submit evidence. "
    "No tool records a human decision or scientific approval."
)

ExpertOp = Callable[[CaseRegistry, dict[str, Any]], Any]

EXPERT_OPERATIONS: dict[str, ExpertOp] = {
    "start_case": lambda reg, args: reg.start_case(
        args["package_id"],
        args["target"],
        args["reference"],
        session_id=args.get("session_id"),
        workspace=args.get("workspace"),
    ),
    "read_case": lambda reg, args: reg.read_case(args["case_id"]),
    "continue_case": lambda reg, args: reg.continue_case_tool(
        args["case_id"],
        args.get("target"),
        args.get("reference"),
        session_id=args.get("session_id"),
        workspace=args.get("workspace"),
    ),
    "open_book": lambda reg, args: reg.open_book_tool(args["case_id"]),
    "find_packages": lambda reg, args: reg.find_packages_tool(
        args.get("hole"), workspace=args.get("workspace")
    ),
    "list_cases": lambda reg, args: reg.list_cases_tool(workspace=args.get("workspace")),
}

ALL_OPERATIONS = set(OPERATIONS) | set(EXPERT_OPERATIONS)


def _reply(ident: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _fault(ident: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def _content(value: Any, failed: bool) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value)}], "isError": failed}


def call(target: CaseRegistry | BookStore, name: str, arguments: Any) -> dict[str, Any]:
    """Run one tool. A refusal is a tool result carrying the contract's Error, not a crash."""
    try:
        if name in EXPERT_OPERATIONS:
            if isinstance(target, CaseRegistry):
                reg = target
            else:
                reg = CaseRegistry(
                    cases_dir=Path("outputs/cases"),
                    data_root=Path("data/raw/nvcl"),
                    provider=target.provider,
                    science=target.science,
                    default_db=target.path,
                )
            return _content(EXPERT_OPERATIONS[name](reg, arguments), False)
        if name in OPERATIONS:
            if isinstance(target, CaseRegistry):
                args = dict(arguments) if isinstance(arguments, dict) else {}
                case = args.pop("case", None)
                store = target.get_store(case)
            else:
                args = dict(arguments) if isinstance(arguments, dict) else {}
                args.pop("case", None)
                store = target
            return _content(OPERATIONS[name](store, args), False)
        return _content({"error": f"Unknown tool: {name}", "retryable": False}, True)
    except BookConflict as error:
        return _content({"error": str(error), "code": error.code, "retryable": False}, True)
    except ValueError as error:
        body = {"error": str(error) or "Invalid request", "code": "invalid_request"}
        return _content({**body, "retryable": False}, True)


def handle(
    target: CaseRegistry | BookStore,
    message: Any,
    tools_mode: str = "all",
) -> dict[str, Any] | None:
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
        exposed = EXPERT_TOOLS if tools_mode == "expert" else TOOLS
        return _reply(ident, {"tools": exposed})
    if method == "tools/call":
        name = params.get("name")
        allowed = set(EXPERT_OPERATIONS) if tools_mode == "expert" else ALL_OPERATIONS
        if name not in allowed:
            return _fault(ident, -32602, f"Unknown tool: {name}")
        return _reply(ident, call(target, name, params.get("arguments") or {}))
    return _fault(ident, -32601, f"Method not found: {method}")


def serve(
    target: CaseRegistry | BookStore,
    source: TextIO,
    sink: TextIO,
    tools_mode: str = "all",
) -> None:
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
                reply = handle(target, message, tools_mode=tools_mode)
            except Exception as error:  # keep serving; the cause goes to stderr, not stdout
                print(f"internal error: {error!r}", file=sys.stderr)
                ident = message.get("id") if isinstance(message, dict) else None
                reply = _fault(ident, -32603, f"Internal error: {type(error).__name__}")
        if reply is not None:
            sink.write(json.dumps(reply) + "\n")
            sink.flush()


def claim_stdout() -> TextIO:
    """Keep the real stdout for JSON-RPC alone; everything else, native writes included, to stderr.

    Model frameworks print banners from Python and from native code while loading and running.
    Descriptor 1 is pointed at stderr, and the original is kept under a private descriptor.
    """
    saved = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return os.fdopen(saved, "w", encoding="utf-8")


def main(
    argv: list[str] | None = None,
    load: Loader | None = None,
    science: Any = None,
    server_launcher: ServerLauncher | None = None,
) -> None:
    parser = argparse.ArgumentParser(description="HyLogger worker and expert tools over MCP stdio")
    parser.add_argument("--db", type=Path, default=Path("outputs/live-book/demo.sqlite3"))
    parser.add_argument("--cases", type=Path, default=Path("outputs/cases"))
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/nvcl"))
    parser.add_argument(
        "--tools",
        choices=["expert", "all"],
        default="all",
        help="tools exposed over MCP: expert only or all (default: all)",
    )
    add_option(parser)
    args = parser.parse_args(argv)
    sink = claim_stdout()
    provider = startup(args.model, load, python=args.model_python)
    registry = CaseRegistry(
        cases_dir=args.cases,
        data_root=args.data_root,
        provider=provider,
        science=science,
        default_db=args.db,
        server_launcher=server_launcher,
    )
    serve(registry, sys.stdin, sink, tools_mode=args.tools)


if __name__ == "__main__":
    main()
