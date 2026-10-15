# Purpose: prove provider selection, startup failures and clean MCP stdout, without any weights.
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from support import SRC, working

from hylogger_bridge import book_server
from hylogger_bridge.advice import assets
from hylogger_bridge.advice.encode import VERSION
from hylogger_bridge.advice.provider import FixtureProvider, ModelProvider
from hylogger_bridge.advice.select import StartupError, describe, select, startup
from hylogger_bridge.book import BookStore

NOISY = """
import os
import sys

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.mcp import server


class Noisy:
    def assess(self, request, at):
        print("framework banner during inference")
        os.write(1, b"native noise during inference!")
        return FixtureProvider().assess(request, at)


def load(folder):
    print("framework banner during loading")
    os.write(1, b"native noise during loading!")
    return Noisy()


server.main(sys.argv[1:], load=load)
"""


def double(state: str, questions: dict[str, Any]) -> dict[str, Any]:
    # A test double standing in for a checkpoint; it is not a trained model.
    keys = sorted(questions["follow_up"]["criteria"])
    odds = {key: 0.6 if key == keys[-1] else 0.1 for key in keys}
    return {"follow_up": {"answer": keys[-1], "probabilities": odds}}


def stub(folder: Path) -> ModelProvider:
    return ModelProvider(double, "double-v0", "synthetic")


def env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(SRC)}


class Scratch(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.dir = Path(scratch.name)

    def bundle(self) -> Path:
        """A complete-looking checkpoint folder of placeholder files; it holds no weights."""
        folder = self.dir / "model"
        names = [*assets.REQUIRED, "base/model.safetensors"]
        for name in names:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder")
        run = {
            "version": "placeholder-v0",
            "data_origin": "synthetic",
            "input_version": VERSION,
            "action_types": ["qa_check"],
            "config": {"max_seq_length": 8},
        }
        assets.write(folder, run)
        return folder


class SelectionTests(Scratch):
    def test_the_default_is_the_labelled_fixture(self) -> None:
        provider = select(None)
        self.assertIsInstance(provider, FixtureProvider)
        self.assertIn("no model is consulted", describe(provider))
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            startup(None)
        self.assertIn("Advice provider: fixture", errors.getvalue())

    def test_a_missing_folder_is_an_error_not_fixture_advice(self) -> None:
        with self.assertRaises(StartupError) as caught:
            select(self.dir / "nowhere")
        self.assertIn("not found", str(caught.exception))
        with self.assertRaises(SystemExit) as stop:
            startup(self.dir / "nowhere")
        self.assertTrue(str(stop.exception).startswith("error: "))

    def test_an_empty_or_corrupt_folder_is_an_invalid_bundle(self) -> None:
        empty = self.dir / "empty"
        empty.mkdir()
        with self.assertRaises(StartupError) as caught:
            select(empty)
        self.assertIn("cannot be used", str(caught.exception))
        (empty / "manifest.json").write_text("{ not json")
        with self.assertRaises(StartupError):
            select(empty)

    def test_a_tampered_bundle_is_refused(self) -> None:
        folder = self.bundle()
        (folder / "base" / "model.safetensors").write_text("changed after hashing")
        with self.assertRaises(StartupError) as caught:
            select(folder)
        self.assertIn("hashes do not match", str(caught.exception))

    def test_a_missing_runtime_is_reported_not_papered_over(self) -> None:
        folder = self.bundle()
        absent = ModuleNotFoundError("No module named 'unsloth'", name="unsloth")
        with mock.patch.dict(os.environ), mock.patch("importlib.import_module", side_effect=absent):
            with self.assertRaises(StartupError) as caught:
                select(folder)
        self.assertIn("runtime unavailable", str(caught.exception))
        self.assertIn("unsloth", str(caught.exception))

    def test_an_explicit_model_uses_its_loader_and_is_labelled(self) -> None:
        provider = select(self.dir, stub)
        self.assertIsInstance(provider, ModelProvider)
        label = describe(provider)
        for part in ("double-v0", "synthetic", "never an authorisation"):
            self.assertIn(part, label)

    def test_load_failures_are_wrapped_but_bugs_are_not_hidden(self) -> None:
        def failing(error: Exception) -> Any:
            def load(folder: Path) -> Any:
                raise error

            return load

        for error in (RuntimeError("no GPU"), ValueError("bad"), KeyError("x"), OSError("io")):
            with self.subTest(error=repr(error)), self.assertRaises(StartupError):
                select(self.dir, failing(error))
        with self.assertRaises(TypeError):
            select(self.dir, failing(TypeError("a programming error")))

    def test_importing_the_launchers_loads_no_model_code(self) -> None:
        code = (
            "import sys\n"
            "import hylogger_bridge.book_server, hylogger_bridge.mcp.server\n"
            "import hylogger_bridge.advice.select\n"
            "heavy = {'unsloth', 'mlx', 'torch', 'hylogger_bridge.advice.local'}\n"
            "print(sorted(heavy & set(sys.modules)))\n"
        )
        done = subprocess.run(
            [sys.executable, "-c", code], env=env(), timeout=60, capture_output=True, text=True
        )
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "[]"), done.stderr)


class LauncherTests(Scratch):
    def mcp(self, *arguments: str, lines: list[dict[str, Any]]) -> subprocess.CompletedProcess[str]:
        sent = "".join(json.dumps(item) + "\n" for item in lines)
        command = [sys.executable, "-m", "hylogger_bridge.mcp.server", *arguments]
        return subprocess.run(
            command, input=sent, env=env(), timeout=60, capture_output=True, text=True
        )

    def test_the_http_launcher_fails_before_touching_the_book(self) -> None:
        book = self.dir / "book.sqlite3"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            book_server.main(["--db", str(book), "--model", str(self.dir / "nowhere")])
        self.assertTrue(str(stop.exception).startswith("error: "))
        self.assertFalse(book.exists())

    def test_the_mcp_launcher_fails_clearly_with_an_empty_stdout(self) -> None:
        book = self.dir / "book.sqlite3"
        done = self.mcp("--db", str(book), "--model", str(self.dir / "nowhere"), lines=[])
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")
        self.assertIn("model folder not found", done.stderr)
        self.assertFalse(book.exists())

    def test_the_default_mcp_launcher_labels_its_fixture_on_stderr(self) -> None:
        book = self.dir / "book.sqlite3"
        listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        done = self.mcp("--db", str(book), lines=[listing])
        self.assertEqual(done.returncode, 0, done.stderr)
        (line,) = done.stdout.splitlines()
        self.assertEqual(json.loads(line)["id"], 1)
        self.assertIn("Advice provider: fixture", done.stderr)

    def test_mcp_stdout_stays_json_rpc_while_a_model_loads_and_infers(self) -> None:
        book = self.dir / "book.sqlite3"
        page = working(BookStore(book).snapshot())
        ask = {"page_id": page["id"], "expected_revision": page["revision"]}
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "request_assessment", "arguments": ask},
            },
        ]
        model = self.dir / "model"
        model.mkdir()
        command = [sys.executable, "-c", NOISY, "--db", str(book), "--model", str(model)]
        sent = "".join(json.dumps(item) + "\n" for item in lines)
        done = subprocess.run(
            command, input=sent, env=env(), timeout=60, capture_output=True, text=True
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        replies = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2])
        self.assertFalse(replies[1]["result"]["isError"])
        self.assertNotIn("noise", done.stdout)
        self.assertNotIn("banner", done.stdout)
        for text in ("loading", "inference"):
            self.assertIn(f"framework banner during {text}", done.stderr)
            self.assertIn(f"native noise during {text}!", done.stderr)


if __name__ == "__main__":
    unittest.main()
