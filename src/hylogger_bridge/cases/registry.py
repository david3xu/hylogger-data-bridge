# Purpose: case registry and expert operations for authoritative multi-case routing.
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.provider import Provider
from hylogger_bridge.book import BookStore
from hylogger_bridge.cases.runtime import (
    continue_case,
    create_initial_page,
)
from hylogger_bridge.cases.runtime import (
    start_case as runtime_start_case,
)
from hylogger_bridge.science.package import name_of

ServerLauncher = Callable[[Path, str, Path], str]


def is_valid_case_id(case_id: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", case_id)) and not case_id.startswith("-")


def case_slug(
    package_id: str,
    target: tuple[float, float] | list[float],
    reference: tuple[float, float] | list[float],
) -> str:
    pkg = re.sub(r"[^a-zA-Z0-9_-]", "_", package_id.strip()).lower()
    t0, t1 = float(target[0]), float(target[1])
    r0, r1 = float(reference[0]), float(reference[1])
    return f"{pkg}-{t0:g}_{t1:g}-vs-{r0:g}_{r1:g}"


def resolve_package(data_root: Path, package_id: str) -> Path:
    if not package_id or not isinstance(package_id, str):
        raise ValueError("package_id must be a non-empty string")
    clean_id = package_id.strip()
    if ".." in clean_id or "/" in clean_id or "\\" in clean_id:
        raise ValueError(f"Invalid package_id: {package_id!r}")
    candidate = (data_root / clean_id).resolve()
    data_root_resolved = data_root.resolve()
    if not candidate.is_relative_to(data_root_resolved):
        raise ValueError(f"Package path {candidate} escapes data root {data_root}")
    if not candidate.is_dir():
        raise ValueError(f"Package {package_id} not found in {data_root}")
    pkg_sub = candidate / "pkg"
    if pkg_sub.is_dir():
        return pkg_sub
    return candidate


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_book_server_alive(pid: int, port: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/book", method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


def get_or_start_server(cases_dir: Path, case_id: str, book_path: Path) -> str:
    server_file = cases_dir / f"{case_id}.server.json"
    if server_file.is_file():
        try:
            info = json.loads(server_file.read_text())
            pid = int(info["pid"])
            port = int(info["port"])
            if check_book_server_alive(pid, port):
                return f"http://127.0.0.1:{port}"
        except Exception:
            pass
        try:
            server_file.unlink(missing_ok=True)
        except OSError:
            pass

    target_port = 8766
    if is_port_in_use(target_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            target_port = s.getsockname()[1]

    cmd = [
        sys.executable,
        "-m",
        "hylogger_bridge.book_server",
        "--db",
        str(book_path),
        "--port",
        str(target_port),
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if check_book_server_alive(proc.pid, target_port):
            break
        time.sleep(0.05)

    server_file.write_text(json.dumps({"pid": proc.pid, "port": target_port}) + "\n")
    return f"http://127.0.0.1:{target_port}"


class CaseRegistry:
    """Authoritative registry for case books and server instances."""

    def __init__(
        self,
        cases_dir: Path,
        data_root: Path,
        provider: Provider,
        science: Any = None,
        default_db: Path | None = None,
        server_launcher: ServerLauncher | None = None,
    ) -> None:
        self.cases_dir = cases_dir.resolve()
        self.data_root = data_root.resolve()
        self.provider = provider
        self.science = science
        self.default_db = default_db.resolve() if default_db else None
        self.server_launcher = server_launcher
        self._stores: dict[str, BookStore] = {}
        self._lock = threading.Lock()
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def get_store(self, case_id: str | None = None) -> BookStore:
        if case_id is None:
            if self.default_db is None:
                raise ValueError("No default database configured and no case specified")
            with self._lock:
                if "__default__" not in self._stores:
                    self._stores["__default__"] = BookStore(
                        self.default_db, provider=self.provider, science=self.science
                    )
                return self._stores["__default__"]

        if not is_valid_case_id(case_id):
            raise ValueError(f"Invalid case_id: {case_id!r}")

        book_path = self.cases_dir / f"{case_id}.sqlite3"
        with self._lock:
            if case_id in self._stores:
                return self._stores[case_id]
            if not book_path.exists():
                raise ValueError(f"Case {case_id} not found in {self.cases_dir}")
            store = BookStore(book_path, provider=self.provider, science=self.science)
            self._stores[case_id] = store
            return store

    def start_case(
        self,
        package_id: str,
        target: tuple[float, float] | list[float],
        reference: tuple[float, float] | list[float],
    ) -> dict[str, Any]:
        if len(target) != 2 or len(reference) != 2:
            raise ValueError("target and reference must each have 2 elements [top, bottom]")
        t = (float(target[0]), float(target[1]))
        r = (float(reference[0]), float(reference[1]))
        if t[0] >= t[1] or r[0] >= r[1]:
            raise ValueError("Interval bounds must be finite and increasing")

        case_id = case_slug(package_id, t, r)
        book_path = self.cases_dir / f"{case_id}.sqlite3"

        with self._lock:
            if book_path.exists():
                # Reusing existing case without restart or overwrite
                if case_id not in self._stores:
                    self._stores[case_id] = BookStore(
                        book_path, provider=self.provider, science=self.science
                    )
                store = self._stores[case_id]
                snapshot = store.snapshot()
                page1 = snapshot["pages"][0]
                advice = page1.get("assessment") or {}
                readable = [
                    {"id": e["id"], "label": e.get("label", e["id"]), "value": e["value"]}
                    for e in page1.get("evidence", [])
                ]
                return {
                    "case_id": case_id,
                    "reused": True,
                    "page": page1["id"],
                    "status": page1["status"],
                    "advice_origin": advice.get("origin"),
                    "model_version": advice.get("model_version"),
                    "readable_evidence": readable,
                }

            pkg_folder = resolve_package(self.data_root, package_id)
            initial_page = create_initial_page(package_id, t, r)
            store = BookStore(
                book_path, provider=self.provider, science=self.science, start=initial_page
            )
            self._stores[case_id] = store

            runtime_start_case(store, pkg_folder, package_id, t, r)
            snapshot = store.snapshot()
            page1 = snapshot["pages"][0]
            advice = page1.get("assessment") or {}
            readable = [
                {"id": e["id"], "label": e.get("label", e["id"]), "value": e["value"]}
                for e in page1.get("evidence", [])
            ]
            return {
                "case_id": case_id,
                "reused": False,
                "page": page1["id"],
                "status": page1["status"],
                "advice_origin": advice.get("origin"),
                "model_version": advice.get("model_version"),
                "readable_evidence": readable,
            }

    def read_case(self, case_id: str) -> dict[str, Any]:
        store = self.get_store(case_id)
        store.expire_deliveries()
        snapshot = store.snapshot()
        pending_conts = [
            c for c in snapshot.get("continuations", []) if c.get("state") == "pending"
        ]
        human_decision_pending = len(pending_conts) > 0

        pages_summary = []
        for p in snapshot.get("pages", []):
            decision = None
            if p.get("decision"):
                decision = {
                    "choice": p["decision"]["choice"],
                    "note": p["decision"]["note"],
                    "actor": p["decision"].get("actor"),
                }
            pages_summary.append(
                {
                    "id": p["id"],
                    "number": p["number"],
                    "title": p.get("title"),
                    "status": p["status"],
                    "outcome": p.get("outcome"),
                    "readable_evidence": [
                        {"id": e["id"], "label": e.get("label", e["id"]), "value": e["value"]}
                        for e in p.get("evidence", [])
                    ],
                    "decision": decision,
                }
            )

        return {
            "case_id": case_id,
            "pages": pages_summary,
            "human_decision_pending": human_decision_pending,
        }

    def continue_case_tool(
        self,
        case_id: str,
        target: tuple[float, float] | list[float] | None = None,
        reference: tuple[float, float] | list[float] | None = None,
    ) -> dict[str, Any]:
        store = self.get_store(case_id)
        store.expire_deliveries()
        snapshot = store.snapshot()
        pending_conts = [
            c for c in snapshot.get("continuations", []) if c.get("state") == "pending"
        ]
        if not pending_conts:
            return {
                "case_id": case_id,
                "status": "waiting_for_decision",
                "message": (
                    "No committed human decision is pending for this case. "
                    "Ask the expert to review the evidence in the book and "
                    "record their choice in the browser first."
                ),
            }

        done = continue_case(store, target=target, reference=reference, on_no_pending="raise_error")
        snapshot = store.snapshot()
        successor = next(p for p in snapshot["pages"] if p["id"] == done["page"])
        readable = [
            {"id": e["id"], "label": e.get("label", e["id"]), "value": e["value"]}
            for e in successor.get("evidence", [])
        ]
        result_dict = {
            "case_id": case_id,
            "status": "continued",
            "page": successor["id"],
            "readable_evidence": readable,
        }
        if "compare" in done:
            result_dict["compare"] = done["compare"]
        if done.get("stopped"):
            result_dict["stopped"] = True
        if done.get("clarification_needed"):
            result_dict["clarification_needed"] = True
        return result_dict

    def open_book_tool(self, case_id: str) -> dict[str, Any]:
        _ = self.get_store(case_id)
        book_path = self.cases_dir / f"{case_id}.sqlite3"
        if self.server_launcher is not None:
            url = self.server_launcher(self.cases_dir, case_id, book_path)
        else:
            url = get_or_start_server(self.cases_dir, case_id, book_path)
        return {"case_id": case_id, "url": url}

    def find_packages_tool(self, hole: str | None = None) -> dict[str, Any]:
        packages = []
        if self.data_root.is_dir():
            for p in sorted(self.data_root.iterdir()):
                if not p.is_dir():
                    continue
                pkg_sub = p / "pkg"
                pkg_dir = pkg_sub if pkg_sub.is_dir() else p
                if any(pkg_dir.glob("*_tsg.tsg")):
                    hole_id = name_of(p.name)
                    if hole:
                        h_clean = hole.strip().lower()
                        if h_clean != hole_id.lower() and h_clean not in hole_id.lower():
                            continue
                    packages.append({"hole_id": hole_id, "package_id": p.name})
        return {"packages": packages}

    def list_cases_tool(self) -> dict[str, Any]:
        cases = []
        if self.cases_dir.is_dir():
            for p in sorted(self.cases_dir.glob("*.sqlite3")):
                case_id = p.stem
                if not is_valid_case_id(case_id):
                    continue
                try:
                    with sqlite3.connect(p) as conn:
                        row = conn.execute("SELECT data FROM book WHERE id=1").fetchone()
                        if not row:
                            continue
                        data = json.loads(row[0])
                        pages = data.get("pages", [])
                        last_page = pages[-1] if pages else None
                        last_status = last_page.get("status") if last_page else "empty"

                        hole_id = ""
                        target = None
                        reference = None
                        s_row = conn.execute("SELECT scene FROM scenes LIMIT 1").fetchone()
                        if s_row:
                            scene = json.loads(s_row[0])
                            package_id = scene.get("package_id", "")
                            hole_id = (
                                name_of(package_id) if package_id else scene.get("hole_id", "")
                            )
                            target = scene.get("target")
                            reference = scene.get("reference")

                        cases.append(
                            {
                                "case_id": case_id,
                                "hole": hole_id,
                                "target": target,
                                "reference": reference,
                                "last_page_status": last_status,
                                "pages_count": len(pages),
                            }
                        )
                except Exception:
                    continue
        return {"cases": cases}
