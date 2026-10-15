# Purpose: case registry and expert operations for authoritative multi-case routing.
import fcntl
import json
import sqlite3
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.provider import Provider
from hylogger_bridge.book import BookStore
from hylogger_bridge.cases.dispatch import (
    CommandRunner,
    WatcherRegistry,
    bind_session,
    check_and_dispatch,
    load_dispatches,
    load_session_binding,
    unbind_session,
)
from hylogger_bridge.cases.identity import case_slug as case_slug
from hylogger_bridge.cases.identity import interval, resolve_package
from hylogger_bridge.cases.identity import is_valid_case_id as is_valid_case_id
from hylogger_bridge.cases.runtime import (
    continue_case,
    create_initial_page,
)
from hylogger_bridge.cases.runtime import (
    start_case as runtime_start_case,
)
from hylogger_bridge.cases.servers import get_or_start_server
from hylogger_bridge.science.package import name_of
from hylogger_bridge.store import scenes

ServerLauncher = Callable[[Path, str, Path], str]


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
        cmd_runner: CommandRunner = subprocess.run,
        watcher_interval: float = 1.0,
    ) -> None:
        self.cases_dir = cases_dir.resolve()
        self.data_root = data_root.resolve()
        self.provider = provider
        self.science = science
        self.default_db = default_db.resolve() if default_db else None
        self.server_launcher = server_launcher
        self.cmd_runner = cmd_runner
        self.watcher_interval = watcher_interval
        self._stores: dict[str, BookStore] = {}
        self._watchers = WatcherRegistry()
        self._lock = threading.Lock()
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def _start_watcher_if_bound(self, case_id: str) -> None:
        binding = load_session_binding(self.cases_dir, case_id)
        if binding and binding.get("active"):
            self._watchers.start_watcher(
                self.cases_dir,
                case_id,
                lambda: self.get_store(case_id),
                interval=self.watcher_interval,
                cmd_runner=self.cmd_runner,
            )

    def bind_case(self, case_id: str, session_id: str) -> dict[str, Any]:
        store = self.get_store(case_id)
        record = bind_session(self.cases_dir, case_id, session_id)
        self._start_watcher_if_bound(case_id)
        check_and_dispatch(
            self.cases_dir,
            case_id,
            store,
            cmd_runner=self.cmd_runner,
        )
        return record

    def unbind_case(self, case_id: str) -> dict[str, Any]:
        _ = self.get_store(case_id)
        self._watchers.stop_watcher(case_id)
        return unbind_session(self.cases_dir, case_id)

    def close(self) -> None:
        self._watchers.stop_all()

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

    def resolve_workspace(self, workspace: str | Path | None = None) -> Path:
        if workspace is not None:
            cleaned = str(workspace).strip()
            if not cleaned:
                raise ValueError("workspace cannot be empty")
            p = Path(cleaned).resolve()
            if not p.is_dir():
                raise ValueError(
                    f"Authorised workspace does not exist or is not a directory: {workspace}"
                )
            return p
        return self.data_root

    def start_case(
        self,
        package_id: str,
        target: tuple[float, float] | list[float],
        reference: tuple[float, float] | list[float],
        session_id: str | None = None,
        workspace: str | Path | None = None,
    ) -> dict[str, Any]:
        data_root = self.resolve_workspace(workspace)
        t, r = interval(target), interval(reference)
        if workspace is not None and data_root != self.data_root:
            case_id = case_slug(package_id, t, r, workspace=data_root)
        else:
            case_id = case_slug(package_id, t, r)
            # Old public case IDs remain usable; only reuse when stored scientific criteria match.
            legacy = f"{package_id.strip().lower()}-{t[0]:g}_{t[1]:g}-vs-{r[0]:g}_{r[1]:g}"
            if is_valid_case_id(legacy) and (self.cases_dir / f"{legacy}.sqlite3").exists():
                old = self.get_store(legacy)
                if self._matches(old, package_id, t, r, workspace=data_root):
                    case_id = legacy
        book_path = self.cases_dir / f"{case_id}.sqlite3"
        with self._lock, (self.cases_dir / f"{case_id}.init.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if session_id:
                bind_session(self.cases_dir, case_id, session_id)
                self._start_watcher_if_bound(case_id)
            if book_path.exists():
                store = self._stores.get(case_id)
                if store is None:
                    store = BookStore(book_path, provider=self.provider, science=self.science)
                    self._stores[case_id] = store
                snapshot = store.snapshot()
                page1 = snapshot["pages"][0]
                if not self._matches(store, package_id, t, r, workspace=data_root):
                    with sqlite3.connect(store.path) as conn:
                        attached = scenes.get(conn, page1["id"])
                    if attached is not None:
                        raise ValueError("stored case scene does not match the requested criteria")
                    expected = create_initial_page(package_id, t, r)["page"]["question"]
                    if page1["question"] != expected:
                        raise ValueError("stored case does not match the requested criteria")
                if page1["status"] == "draft":
                    pkg_folder = resolve_package(data_root, package_id)
                    runtime_start_case(store, pkg_folder, package_id, t, r)
                    page1 = store.snapshot()["pages"][0]
                return self._started(case_id, page1, True, workspace=data_root)

            pkg_folder = resolve_package(data_root, package_id)
            initial_page = create_initial_page(package_id, t, r)
            store = BookStore(
                book_path, provider=self.provider, science=self.science, start=initial_page
            )
            self._stores[case_id] = store

            runtime_start_case(store, pkg_folder, package_id, t, r)
            return self._started(case_id, store.snapshot()["pages"][0], False, workspace=data_root)

    @staticmethod
    def _matches(
        store: BookStore,
        package_id: str,
        target: Any,
        reference: Any,
        workspace: Path | None = None,
    ) -> bool:
        page = store.snapshot()["pages"][0]
        with sqlite3.connect(store.path) as conn:
            scene = scenes.get(conn, page["id"])
        if scene is None:
            return False
        matched = (
            scene["package_id"] == package_id.strip()
            and tuple(scene["target"]) == tuple(target)
            and tuple(scene["reference"]) == tuple(reference)
        )
        if not matched:
            return False
        if workspace is not None:
            folder = Path(scene.get("folder", "")).resolve()
            if not folder.is_relative_to(workspace.resolve()):
                return False
        return True

    def _started(
        self,
        case_id: str,
        page: dict[str, Any],
        reused: bool,
        workspace: Path | None = None,
    ) -> dict[str, Any]:
        advice = page.get("assessment") or {}
        binding = load_session_binding(self.cases_dir, case_id)
        res = {
            "case_id": case_id,
            "reused": reused,
            "page": page["id"],
            "status": page["status"],
            "advice_origin": advice.get("origin"),
            "model_version": advice.get("model_version"),
            "assessment": page.get("assessment"),
            "readable_evidence": page.get("evidence", []),
        }
        if binding:
            res["session_binding"] = binding
        if workspace:
            res["workspace"] = str(workspace)
        return res

    def read_case(self, case_id: str) -> dict[str, Any]:
        store = self.get_store(case_id)
        store.expire_deliveries()
        self._start_watcher_if_bound(case_id)
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
                    "revision": p["revision"],
                    "question": p["question"],
                    "summary": p["summary"],
                    "title": p.get("title"),
                    "status": p["status"],
                    "outcome": p.get("outcome"),
                    "readable_evidence": [dict(e) for e in p.get("evidence", [])],
                    "decision": decision,
                    "assessment": p.get("assessment"),
                    "action": p.get("action"),
                }
            )

        binding = load_session_binding(self.cases_dir, case_id)
        dispatches = load_dispatches(self.cases_dir, case_id)
        return {
            "case_id": case_id,
            "pages": pages_summary,
            "human_decision_pending": human_decision_pending,
            "session_binding": binding,
            "dispatches": list(dispatches.values()),
        }

    def continue_case_tool(
        self,
        case_id: str,
        target: tuple[float, float] | list[float] | None = None,
        reference: tuple[float, float] | list[float] | None = None,
        session_id: str | None = None,
        workspace: str | Path | None = None,
    ) -> dict[str, Any]:
        if session_id:
            self.bind_case(case_id, session_id)
        store = self.get_store(case_id)
        data_root = self.resolve_workspace(workspace)
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

        with sqlite3.connect(store.path) as conn:
            stored = conn.execute("SELECT scene FROM scenes").fetchall()
        for (encoded,) in stored:
            scene = json.loads(encoded)
            expected = resolve_package(data_root, scene["package_id"])
            if Path(scene["folder"]).resolve() != expected:
                raise ValueError("case scene is outside the currently authorised package folder")
        done = continue_case(store, target=target, reference=reference, on_no_pending="raise_error")
        snapshot = store.snapshot()
        successor = next(p for p in snapshot["pages"] if p["id"] == done["page"])
        readable = [dict(e) for e in successor.get("evidence", [])]
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

    def find_packages_tool(
        self, hole: str | None = None, workspace: str | Path | None = None
    ) -> dict[str, Any]:
        root = self.resolve_workspace(workspace)
        packages: list[dict[str, str]] = []
        if not root.is_dir():
            return {"packages": []}

        discovered_dirs: set[Path] = set()
        for tsg_file in sorted(root.glob("**/*_tsg.tsg")):
            if not tsg_file.resolve().is_relative_to(root):
                continue
            pkg_dir = tsg_file.parent.resolve()
            if not pkg_dir.is_relative_to(root):
                continue
            actual_pkg = (
                pkg_dir.parent.resolve()
                if pkg_dir.name == "pkg" and pkg_dir.parent.resolve().is_relative_to(root)
                else pkg_dir
            )
            if actual_pkg in discovered_dirs:
                continue

            rel = actual_pkg.relative_to(root)
            package_id = rel.as_posix()
            try:
                resolve_package(root, package_id)
            except ValueError:
                continue
            discovered_dirs.add(actual_pkg)

            hole_id = name_of(actual_pkg.name)

            if hole:
                h_clean = hole.strip().lower()
                if h_clean != hole_id.lower() and h_clean not in hole_id.lower():
                    continue
            packages.append({"hole_id": hole_id, "package_id": package_id})

        return {"packages": packages}

    def list_cases_tool(self, workspace: str | Path | None = None) -> dict[str, Any]:
        cases = []
        target_ws = self.resolve_workspace(workspace) if workspace else None
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
                        case_folder = None
                        s_row = conn.execute("SELECT scene FROM scenes LIMIT 1").fetchone()
                        if s_row:
                            scene = json.loads(s_row[0])
                            package_id = scene.get("package_id", "")
                            hole_id = (
                                name_of(package_id) if package_id else scene.get("hole_id", "")
                            )
                            target = scene.get("target")
                            reference = scene.get("reference")
                            case_folder = scene.get("folder")

                        if target_ws and case_folder:
                            if not Path(case_folder).resolve().is_relative_to(target_ws):
                                continue

                        case_info: dict[str, Any] = {
                            "case_id": case_id,
                            "hole": hole_id,
                            "target": target,
                            "reference": reference,
                            "last_page_status": last_status,
                            "pages_count": len(pages),
                        }
                        if case_folder:
                            case_info["folder"] = case_folder
                        cases.append(case_info)
                except Exception:
                    continue
        return {"cases": cases}
