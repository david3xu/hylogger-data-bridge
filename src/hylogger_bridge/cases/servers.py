# Purpose: start and discover only verified book servers, serialized per investigation.
import fcntl
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def identity(book_path: Path) -> tuple[str, str]:
    with sqlite3.connect(book_path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
    if row is None:
        raise ValueError("book has no investigation")
    book = json.loads(row[0])
    return book["run_id"], book["pages"][0]["id"]


def check_book_server_alive(pid: int, port: int, book_path: Path) -> bool:
    try:
        os.kill(pid, 0)
        expected = identity(book_path)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/book", timeout=0.5) as reply:
            book = json.load(reply)
        if (book["run_id"], book["pages"][0]["id"]) != expected:
            return False
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5) as reply:
            return reply.status == 200 and "<html" in reply.read(32768).decode().lower()
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


def _reuse(record: Path, book_path: Path) -> str | None:
    try:
        value = json.loads(record.read_text())
        if check_book_server_alive(int(value["pid"]), int(value["port"]), book_path):
            return f"http://127.0.0.1:{int(value['port'])}"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def get_or_start_server(cases_dir: Path, case_id: str, book_path: Path) -> str:
    # A file lock also covers separate MCP processes using this registry.
    with (cases_dir / f"{case_id}.server.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = cases_dir / f"{case_id}.server.json"
        reused = _reuse(record, book_path)
        if reused is not None:
            return reused
        record.unlink(missing_ok=True)
        root = Path(os.environ.get("HYLOGGER_HOME", Path(__file__).resolve().parents[3]))
        static = (root / "app/dist").resolve()
        if not (static / "index.html").is_file():
            raise ValueError("built book UI missing; run npm --prefix app run build")
        identity(book_path)
        log_path = cases_dir / f"{case_id}.server.log"
        cmd = [
            sys.executable,
            "-m",
            "hylogger_bridge.book_server",
            "--db",
            str(book_path.resolve()),
            "--port",
            "0",
            "--static-root",
            str(static),
        ]
        with log_path.open("w") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise ValueError(f"book server exited; see {log_path}")
                match = re.search(r"Live book: http://127\.0\.0\.1:(\d+)", log_path.read_text())
                if match is not None:
                    port = int(match[1])
                    if check_book_server_alive(proc.pid, port, book_path):
                        value: dict[str, Any] = {"pid": proc.pid, "port": port}
                        temporary = record.with_suffix(".tmp")
                        temporary.write_text(json.dumps(value) + "\n")
                        temporary.replace(record)
                        return f"http://127.0.0.1:{port}"
                time.sleep(0.05)
            raise ValueError(f"book server did not become ready; see {log_path}")
        except BaseException:
            # Never signal a PID read from a discovery file: this call owns only proc.
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            raise
