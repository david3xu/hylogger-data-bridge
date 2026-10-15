# Purpose: prove book-server identity, safe startup failures and concurrent discovery.
import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from hylogger_bridge.book import BookStore
from hylogger_bridge.book_server import BookServer
from hylogger_bridge.cases import servers
from hylogger_bridge.pages.live import start


def book(path: Path, name: str) -> BookStore:
    return BookStore(path, start=start(name, name, "Q", "S", "P"))


def test_wrong_book_is_not_a_healthy_endpoint(tmp_path: Path) -> None:
    expected, other = (
        book(tmp_path / "expected.sqlite3", "expected"),
        book(tmp_path / "other.sqlite3", "other"),
    )
    (tmp_path / "index.html").write_text("<html>test UI</html>")
    server = BookServer(0, other, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert servers.check_book_server_alive(os.getpid(), server.server_port, other.path)
        assert not servers.check_book_server_alive(os.getpid(), server.server_port, expected.path)
    finally:
        server.shutdown()
        server.server_close()


def test_failed_launch_never_publishes_discovery(tmp_path: Path, monkeypatch: Any) -> None:
    ui = tmp_path / "app/dist"
    ui.mkdir(parents=True)
    (ui / "index.html").write_text("<html>test</html>")
    monkeypatch.setenv("HYLOGGER_HOME", str(tmp_path))
    store = book(tmp_path / "book.sqlite3", "test")

    class Exited:
        pid = 123456789

        def poll(self) -> int:
            return 1

    monkeypatch.setattr("hylogger_bridge.cases.servers.subprocess.Popen", lambda *a, **kw: Exited())
    with pytest.raises(ValueError, match="exited"):
        servers.get_or_start_server(tmp_path, "test", store.path)
    assert not (tmp_path / "test.server.json").exists()


def test_concurrent_opens_share_one_verified_process(tmp_path: Path, monkeypatch: Any) -> None:
    ui = tmp_path / "app/dist"
    ui.mkdir(parents=True)
    (ui / "index.html").write_text("<html>test</html>")
    monkeypatch.setenv("HYLOGGER_HOME", str(tmp_path))
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.setenv("PYTHONPATH", str(source))
    store = book(tmp_path / "book.sqlite3", "test")
    launched: list[subprocess.Popen[Any]] = []
    popen = subprocess.Popen

    def launch(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        proc = popen(*args, **kwargs)
        launched.append(proc)
        return proc

    monkeypatch.setattr("hylogger_bridge.cases.servers.subprocess.Popen", launch)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            urls = list(
                pool.map(
                    lambda _: servers.get_or_start_server(tmp_path, "test", store.path), range(2)
                )
            )
        assert len(launched) == 1 and urls[0] == urls[1]
        info = json.loads((tmp_path / "test.server.json").read_text())
        assert servers.check_book_server_alive(info["pid"], info["port"], store.path)
    finally:
        for proc in launched:
            proc.terminate()
            proc.wait(timeout=3)


def test_smoke_failure_does_not_touch_an_existing_registry(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from scripts import smoke_test

    old = tmp_path / "outputs/cases/swmb007s_chips-5_10-vs-0_5.sqlite3"
    old.parent.mkdir(parents=True)
    old.write_text("pre-existing expert book")
    monkeypatch.setattr(smoke_test, "__file__", str(tmp_path / "scripts/smoke_test.py"))

    def unavailable(repo: Path, cases: Path) -> dict[str, Any]:
        assert not cases.is_relative_to(tmp_path / "outputs")
        raise RuntimeError("missing prerequisites")

    monkeypatch.setattr(smoke_test, "run", unavailable)
    with pytest.raises(RuntimeError, match="missing"):
        smoke_test.main()
    assert old.read_text() == "pre-existing expert book"
