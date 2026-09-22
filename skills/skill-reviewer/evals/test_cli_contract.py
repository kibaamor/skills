"""Command-line interface contracts: help, exit codes, and the entry guard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    REVIEW,
    SCRIPT,
    junction_or_fail,
    skill_text,
    symlink_or_skip,
    write,
)


class InterfaceTests(unittest.TestCase):
    def test_structured_results_declare_schema_version(self) -> None:
        result = REVIEW.finalize("test", Path("subject"), {}, [], 100)

        self.assertEqual(result["schema_version"], 1)

    def test_junction_creation_failure_is_not_skipped(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["cmd.exe", "mklink"],
            returncode=9,
            stdout="JUNCTION_STDOUT_SENTINEL",
            stderr="JUNCTION_STDERR_SENTINEL",
        )
        link = Path("junction-link")
        target = Path("junction-target")
        with (
            mock.patch.object(os, "name", "nt"),
            mock.patch.object(subprocess, "run", return_value=completed),
            self.assertRaises(self.failureException) as caught,
        ):
            junction_or_fail(self, link, target)

        message = str(caught.exception)
        self.assertIn("exit 9", message)
        self.assertIn(str(link), message)
        self.assertIn(str(target), message)
        self.assertIn("JUNCTION_STDOUT_SENTINEL", message)
        self.assertIn("JUNCTION_STDERR_SENTINEL", message)

    def test_every_subcommand_help_documents_exit_codes(self) -> None:
        for subcommand in (
            "static",
            "validate-evals",
            "validate-triggers",
            "aggregate",
        ):
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), subcommand, "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            normalized_help = " ".join(completed.stdout.split())
            self.assertIn("Exit codes:", normalized_help)
            self.assertIn(
                "2 fatal CLI, filesystem, JSON parse, or output failure",
                normalized_help,
            )

    def test_output_help_does_not_claim_truncated_results_are_complete(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "aggregate", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Also write the rendered result", completed.stdout)
        self.assertNotIn("complete rendered result", completed.stdout)

    def test_validate_evals_accepts_an_explicit_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            target = temporary_root / "target-skill"
            workspace = temporary_root / "review-workspace"
            write(target / "SKILL.md", skill_text("target-skill"))
            evals_path = workspace / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "target-skill",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run one case.",
                                "expected_output": "One result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run another case.",
                                "expected_output": "Another result.",
                            },
                        ],
                    }
                ),
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "validate-evals",
                    str(evals_path),
                    "--skill-root",
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout)["facts"]["target_skill_name"],
            "target-skill",
        )

    def test_validate_evals_rejects_a_missing_explicit_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "review-workspace"
            evals_path = workspace / "evals" / "evals.json"
            write(evals_path, "{}")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "validate-evals",
                    str(evals_path),
                    "--skill-root",
                    str(Path(temporary) / "missing-skill"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Target skill root must exist", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_symlink_loop_is_a_bounded_invalid_path_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            symlink_or_skip(self, path, path.name)
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "validate-triggers", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Error:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_entry_without_sibling_package_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "review_skill.py"
            copy.write_bytes(SCRIPT.read_bytes())
            completed = subprocess.run(
                [sys.executable, "-B", str(copy), "static", temporary],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("skill_review", completed.stderr)
        self.assertIn("Error:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
