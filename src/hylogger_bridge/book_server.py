# Purpose: serve the local book API, committed SSE notifications and the built frontend.
import argparse
import json
import mimetypes
import re
import sqlite3
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from hylogger_bridge.advice.select import Loader, add_option, startup
from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.install.paths import asset
from hylogger_bridge.work import OPERATIONS


def _start(job: Callable[[], None]) -> None:
    threading.Thread(target=job, daemon=True).start()


class BookServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, store: BookStore, static_root: Path) -> None:
        self.store = store
        self.static_root = static_root.resolve()
        # How background jobs start; a test may hold a job to prove it is fenced by its own run.
        self.launch: Callable[[Callable[[], None]], None] = _start
        self.demo_delay = 0.7
        super().__init__(("127.0.0.1", port), BookHandler)


class BookHandler(BaseHTTPRequestHandler):
    server: BookServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Do not log evidence, user notes or arbitrary request payloads.
        return

    def _json(self, status: int, value: object) -> None:
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _local_request(self, mutation: bool = False) -> bool:
        host = self.headers.get("Host", "")
        if host not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
            "127.0.0.1:5173",
            "localhost:5173",
        }:
            return False
        origin = self.headers.get("Origin")
        allowed_origins = {f"http://{host}", "http://127.0.0.1:5173", "http://localhost:5173"}
        if origin is not None and origin not in allowed_origins:
            return False
        return not mutation or self.headers.get("Sec-Fetch-Site") != "cross-site"

    def do_GET(self) -> None:
        if not self._local_request():
            self._json(403, {"error": "Local requests only"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/book":
            self._json(200, self.server.store.snapshot())
        elif parsed.path == "/api/events":
            raw_cursor = (
                self.headers.get("Last-Event-ID") or parse_qs(parsed.query).get("after", ["0"])[0]
            )
            try:
                cursor = int(raw_cursor)
                if cursor < 0:
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "Invalid event cursor"})
                return
            self._stream(cursor)
        elif parsed.path.startswith("/api/"):
            self._json(404, {"error": "Unknown endpoint"})
        else:
            relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            path = (self.server.static_root / relative).resolve()
            if not path.is_relative_to(self.server.static_root) or not path.is_file():
                self._json(404, {"error": "Frontend not built or file not found"})
                return
            raw = path.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream"
            )
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

    def _stream(self, cursor: int) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 1000\n: connected\n\n")
            self.wfile.flush()
            while True:
                store = self.server.store
                events = store.events_after(cursor)
                # In-process commits wake this at once; commits by another process (a worker
                # tool) are found by re-reading the log each second.
                for _ in range(15):
                    if events:
                        break
                    with store.changed:
                        store.changed.wait(timeout=1)
                    events = store.events_after(cursor)
                if not events:
                    # A keepalive maintains the connection; it never changes application state.
                    self.wfile.write(b": keepalive\n\n")
                for event in events:
                    cursor = event["sequence"]
                    payload = {key: event[key] for key in ("sequence", "type", "page_id")}
                    frame = f"id: {cursor}\nevent: book_updated\ndata: {json.dumps(payload)}\n\n"
                    self.wfile.write(frame.encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, sqlite3.OperationalError):
            # A vanished client or database ends this stream; the client reconnects and refetches.
            return
        finally:
            self.close_connection = True

    def do_POST(self) -> None:
        self.close_connection = True
        if not self._local_request(mutation=True):
            self._json(403, {"error": "Local same-origin mutations only"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._json(415, {"error": "Use application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                raise ValueError("Request body must be between 1 and 32768 bytes")
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Request body must be an object")
            path = urlparse(self.path).path
            store = self.server.store
            if path == "/api/demo/start":
                self._fields(body, {"page_id", "expected_revision"})
                if not isinstance(body["page_id"], str):
                    raise ValueError("page_id must be text")
                # The exact run is captured now; a late callback must never look one up by page.
                run = store.begin_demo(body["page_id"], body["expected_revision"])
                delay = self.server.demo_delay
                self.server.launch(lambda: store.run_demo(run.page_id, delay, run))
                self._json(202, {"started": True})
                return
            work_route = re.fullmatch(r"/api/work/([a-z_]+)", path)
            if work_route is not None:
                operation = OPERATIONS.get(work_route.group(1))
                if operation is None:
                    self._json(404, {"error": "Unknown operation", "code": "not_found"})
                    return
                self._json(200, operation(store, body))
                return
            matched = re.fullmatch(r"/api/pages/([a-zA-Z0-9-]+)/(decision|evidence)", path)
            if matched is None:
                self._json(404, {"error": "Unknown endpoint"})
                return
            page_id, operation_name = matched.groups()
            if operation_name == "decision":
                self._fields(body, {"choice", "note", "expected_revision", "request_id"})
                result = store.decide(
                    page_id,
                    body["expected_revision"],
                    body["choice"],
                    body["note"],
                    body["request_id"],
                )
            else:
                self._fields(body, {"expected_revision", "evidence"}, {"claim"})
                if not isinstance(body["evidence"], dict):
                    raise ValueError("evidence must be an object")
                result = store.add_evidence(
                    page_id, body["expected_revision"], body["evidence"], body.get("claim")
                )
            self._json(200, result)
        except BookConflict as error:
            status = 404 if error.code == "not_found" else 409
            self._json(status, {"error": str(error), "code": error.code, "retryable": False})
        except (ValueError, UnicodeError, TimeoutError) as error:
            message = "Invalid JSON" if isinstance(error, json.JSONDecodeError) else str(error)
            body = {"error": message or "Invalid request", "code": "invalid_request"}
            self._json(400, {**body, "retryable": False})

    @staticmethod
    def _fields(
        body: dict[str, Any], required: set[str], optional: frozenset[str] | set[str] = frozenset()
    ) -> None:
        if not required <= set(body) <= required | optional:
            raise ValueError("Request fields do not match the endpoint contract")


def main(argv: list[str] | None = None, load: Loader | None = None) -> None:
    parser = argparse.ArgumentParser(description="Local synthetic live-book demo")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--db", type=Path, default=Path("outputs/live-book/demo.sqlite3"))
    parser.add_argument("--static-root", type=Path, default=asset("book"))
    add_option(parser)
    args = parser.parse_args(argv)
    # Choose the provider first: a requested model that cannot start must not touch the book.
    provider = startup(args.model, load, python=args.model_python)
    store = BookStore(args.db, provider=provider)
    server = BookServer(args.port, store, args.static_root)
    store.recover_interrupted()
    source = store.snapshot()["source"]
    print(f"Live book: http://127.0.0.1:{server.server_port} ({source})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
