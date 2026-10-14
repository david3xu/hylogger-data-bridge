# Purpose: prove the canonical contract accepts its valid fixtures and rejects every invalid one.
import json
import unittest
from pathlib import Path
from typing import Any

from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.contracts.check import ContractError, problems, validate, walk
from hylogger_bridge.contracts.digest import digest
from hylogger_bridge.contracts.load import schema

FIXTURES = Path(__file__).resolve().parents[1] / "schemas" / "fixtures" / "v1"


def load(name: str) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return value


def names() -> list[str]:
    return sorted(path.stem for path in FIXTURES.glob("*.json"))


class FixtureTests(unittest.TestCase):
    def test_files_name_definitions_and_cover_both_outcomes(self) -> None:
        self.assertGreaterEqual(len(names()), 11)
        for name in names():
            with self.subTest(name=name):
                self.assertIn(name, schema()["$defs"])
                self.assertTrue(load(name)["valid"])
                self.assertTrue(load(name)["invalid"])

    def test_valid_cases_pass(self) -> None:
        for name in names():
            for case, value in load(name)["valid"].items():
                with self.subTest(name=name, case=case):
                    self.assertEqual(problems(name, value), [])

    def test_invalid_cases_fail(self) -> None:
        for name in names():
            for case, value in load(name)["invalid"].items():
                with self.subTest(name=name, case=case):
                    self.assertNotEqual(problems(name, value), [])

    def test_book_rules(self) -> None:
        book = load("Book")
        for case, value in book["valid"].items():
            with self.subTest(case=case):
                check_book(value)
        for case, value in book["semantic_invalid"].items():
            with self.subTest(case=case):
                self.assertEqual(problems("Book", value), [])
                with self.assertRaises(ContractError):
                    check_book(value)

    def test_assessment_names_the_exact_request(self) -> None:
        request = load("AssessmentRequest")["valid"]["basic"]
        for case, value in load("Assessment")["valid"].items():
            with self.subTest(case=case):
                self.assertEqual(value["request_hash"], digest(request))

    def test_advice_may_differ_from_the_action_taken(self) -> None:
        page = load("Page")["valid"]["ready-advised"]
        top = min(page["assessment"]["suggestions"], key=lambda item: item["rank"])
        asked = load("AssessmentRequest")["valid"]["basic"]["candidates"]
        candidates = {item["id"]: item["action_type"] for item in asked}
        self.assertNotEqual(candidates[top["candidate_id"]], page["action"]["type"])
        self.assertEqual(page["action"]["assessment_id"], page["assessment"]["id"])
        self.assertEqual(problems("Page", page), [])


class ValidatorTests(unittest.TestCase):
    def test_booleans_are_not_numbers(self) -> None:
        self.assertNotEqual(problems("Revision", True), [])
        self.assertNotEqual(problems("Version", True), [])
        self.assertEqual(problems("Version", 1), [])

    def test_non_finite_numbers_are_rejected(self) -> None:
        self.assertNotEqual(walk({"type": "number"}, float("nan"), schema()), [])
        self.assertNotEqual(walk({"type": "number"}, float("inf"), schema()), [])

    def test_trailing_newline_is_not_an_id(self) -> None:
        self.assertEqual(problems("Id", "page-1"), [])
        self.assertNotEqual(problems("Id", "page-1\n"), [])

    def test_unsupported_keyword_is_a_schema_bug(self) -> None:
        with self.assertRaises(ValueError):
            walk({"format": "date"}, "x", schema())

    def test_unknown_definition_is_a_programming_error(self) -> None:
        with self.assertRaises(ValueError):
            problems("Nope", {})

    def test_validate_raises_with_the_reasons(self) -> None:
        with self.assertRaises(ContractError) as caught:
            validate("Error", {})
        self.assertIn("missing error", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
