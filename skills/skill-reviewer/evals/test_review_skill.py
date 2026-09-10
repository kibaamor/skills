#!/usr/bin/env python3
"""Regression tests for the bundled deterministic reviewer."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "review_skill.py"
SPEC = importlib.util.spec_from_file_location("review_skill", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot import {SCRIPT}")
REVIEW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def skill_text(name: str, extra_frontmatter: str = "", body: str = "Do the task.") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: Use this skill when the fixture task applies.\n"
        f"{extra_frontmatter}"
        "---\n\n"
        f"# Fixture\n\n{body}\n"
    )


def grading(results: list[tuple[str, bool, str]]) -> dict[str, object]:
    assertion_results = [
        {"text": text, "passed": passed, "evidence": evidence}
        for text, passed, evidence in results
    ]
    passed_count = sum(int(item[1]) for item in results)
    total = len(results)
    return {
        "assertion_results": assertion_results,
        "summary": {
            "passed": passed_count,
            "failed": total - passed_count,
            "total": total,
            "pass_rate": passed_count / total,
        },
    }


class StaticReviewTests(unittest.TestCase):
    def test_accepts_nested_frontmatter_and_ignores_fenced_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "nested-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "nested-skill",
                    "metadata:\n  short-description: Nested value\n",
                    (
                        "Example only: `scripts/not-real.py`.\n\n"
                        "```markdown\n"
                        "[Example](references/not-real.md)\n"
                        "```"
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["errors"], 0)

    def test_rejects_unbalanced_frontmatter_flow_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "broken-skill"
            write(
                root / "SKILL.md",
                skill_text("broken-skill", "metadata: [\n"),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "frontmatter.malformed",
            {finding["code"] for finding in result["findings"]},
        )

    def test_reports_a_live_missing_markdown_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "linked-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "linked-skill",
                    body="Read [the required guide](references/missing.md).",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )


class EvalsValidationTests(unittest.TestCase):
    def test_rejects_skill_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            write(root / "evals" / "files" / "input.txt", "fixture\n")
            evals = {
                "skill_name": "wrong-skill",
                "evals": [
                    {
                        "id": "one",
                        "prompt": "Use the realistic fixture input.",
                        "expected_output": "A verified result.",
                        "files": ["evals/files/input.txt"],
                    },
                    {
                        "id": "two",
                        "prompt": "Exercise a realistic boundary.",
                        "expected_output": "A safe boundary response.",
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.skill_name_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_accepts_matching_well_formed_evals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            evals = {
                "skill_name": "right-skill",
                "evals": [
                    {
                        "id": "one",
                        "prompt": "Complete this realistic task.",
                        "expected_output": "An observable result.",
                    },
                    {
                        "id": "two",
                        "prompt": "Handle this realistic edge case.",
                        "expected_output": "An observable safe response.",
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["target_skill_name"], "right-skill")


class AggregateTests(unittest.TestCase):
    def write_run(
        self,
        root: Path,
        eval_name: str,
        configuration: str,
        grading_data: dict[str, object],
        tokens: int,
        duration_ms: int,
    ) -> None:
        run = root / eval_name / configuration
        write(run / "grading.json", json.dumps(grading_data))
        write(
            run / "timing.json",
            json.dumps({"total_tokens": tokens, "duration_ms": duration_ms}),
        )

    def test_aggregates_consistent_evidenced_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Has result", True, "Found output.json")]),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["complete"])
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)

    def test_rejects_evidence_free_or_inconsistent_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = {
                "assertion_results": [
                    {"text": "Has result", "passed": True, "evidence": ""}
                ],
                "summary": {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0},
            }
            self.write_run(root, "eval-one", "with_skill", invalid, 1200, 3000)
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )


class InterfaceTests(unittest.TestCase):
    def test_every_subcommand_help_documents_exit_codes(self) -> None:
        for subcommand in ("static", "validate-evals", "aggregate"):
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), subcommand, "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Exit codes:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
