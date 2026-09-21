"""Paired-run aggregation and output publication."""

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
    FS_SAFETY,
    OUTPUT_MODULE,
    REVIEW,
    SCRIPT,
    grading,
    junction_or_fail,
    symlink_or_skip,
    write,
)


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

    def write_complete_pair(self, root: Path) -> None:
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

    def run_aggregate_cli(
        self,
        root: Path,
        *extra_arguments: str,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "aggregate",
                str(root),
                "--candidate",
                "with_skill",
                "--baseline",
                "old_skill",
                *extra_arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )

    def test_aggregates_consistent_evidenced_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([(" Has result ", True, "Found output.json")]),
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

    def test_reports_per_assertion_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading(
                    [
                        ("Candidate gain", True, "Found candidate output"),
                        ("Baseline advantage", False, "Candidate omitted detail"),
                        ("Non-discriminating pass", True, "Both produce JSON"),
                        ("Shared failure", False, "Candidate misses requirement"),
                    ]
                ),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading(
                    [
                        ("Candidate gain", False, "Baseline has no output"),
                        ("Baseline advantage", True, "Baseline includes detail"),
                        ("Non-discriminating pass", True, "Both produce JSON"),
                        ("Shared failure", False, "Baseline misses requirement"),
                    ]
                ),
                900,
                2000,
            )

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertEqual(
            result["facts"]["assertion_summary"],
            {
                "candidate_only": 1,
                "baseline_only": 1,
                "both_pass": 1,
                "both_fail": 1,
            },
        )
        analysis = result["facts"]["assertion_analysis"]
        self.assertEqual(len(analysis), 1)
        self.assertEqual(analysis[0]["eval"], "eval-one")
        self.assertEqual(analysis[0]["counts"], result["facts"]["assertion_summary"])
        self.assertEqual(
            {item["text"]: item["outcome"] for item in analysis[0]["assertions"]},
            {
                "Baseline advantage": "baseline_only",
                "Candidate gain": "candidate_only",
                "Non-discriminating pass": "both_pass",
                "Shared failure": "both_fail",
            },
        )
        candidate_gain = next(
            item
            for item in analysis[0]["assertions"]
            if item["text"] == "Candidate gain"
        )
        self.assertEqual(
            candidate_gain,
            {
                "text": "Candidate gain",
                "outcome": "candidate_only",
                "candidate_passed": True,
                "candidate_evidence": "Found candidate output",
                "baseline_passed": False,
                "baseline_evidence": "Baseline has no output",
            },
        )

    def test_aggregate_ignores_unselected_configuration_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_complete_pair(root)
            (root / "eval-one" / "unselected").mkdir()
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["complete"])
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)
        self.assertNotIn("unselected", result["facts"]["run_summary"])

    def test_aggregate_text_output_includes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_complete_pair(root)
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)
            rendered = REVIEW.render_text(result)

        self.assertEqual(status, 0)
        metrics_line = next(
            line for line in rendered.splitlines() if line.startswith("metrics=")
        )
        metrics = json.loads(metrics_line.removeprefix("metrics="))
        self.assertIn("with_skill", metrics["run_summary"])
        self.assertEqual(metrics["delta"]["pass_rate"], 1.0)
        self.assertEqual(metrics["assertion_summary"]["candidate_only"], 1)
        self.assertTrue(metrics["complete"])

    def test_json_output_safely_escapes_unpaired_surrogates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = "Evidence \ud800"
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Has result", True, evidence)]),
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
            output = root / "benchmark.json"

            completed = self.run_aggregate_cli(root, "--output", str(output))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            rendered = output.read_text(encoding="utf-8")

        self.assertEqual(completed.stderr, "")
        self.assertEqual(completed.stdout, rendered)
        self.assertIn("\\ud800", rendered)
        result = json.loads(rendered)
        assertion = result["facts"]["assertion_analysis"][0]["assertions"][0]
        self.assertEqual(assertion["candidate_evidence"], evidence)

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_accepts_iteration_root_junction_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            alias = temporary_root / "selected-iteration-alias"
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
            expected_subject = str(root.resolve())
            junction_or_fail(self, alias, root)
            try:
                result, status = REVIEW.aggregate(
                    alias, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(alias):
                    os.rmdir(alias)
            self.assertTrue((root / "eval-one" / "with_skill").is_dir())

        self.assertEqual(status, 0)
        self.assertEqual(result["subject"], expected_subject)
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

    def test_rejects_oversized_run_data_without_unbounded_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "eval-one" / "with_skill"
            candidate.mkdir(parents=True)
            candidate_grading = grading([("Has result", True, "Found output.json")])
            candidate_grading["padding"] = "x" * 2000
            candidate_grading_text = json.dumps(candidate_grading)
            write(candidate / "grading.json", candidate_grading_text)
            write(
                candidate / "timing.json",
                json.dumps({"total_tokens": 1200, "duration_ms": 3000}),
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            with mock.patch.object(
                FS_SAFETY, "MAX_TEXT_FILE_BYTES", len(candidate_grading_text) - 1
            ):
                result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertIn("resource exceeds", json.dumps(result).lower())

    def test_rejects_mismatched_paired_assertion_texts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Candidate assertion", True, "Found output.json")]),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Baseline assertion", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertEqual(result["facts"]["assertion_analysis"], [])
        self.assertTrue(
            all(count == 0 for count in result["facts"]["assertion_summary"].values())
        )
        self.assertIn(
            "aggregate.assertion_set_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_duplicate_assertions_within_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = grading(
                [
                    ("Has result", True, "Found output.json"),
                    (" Has result ", True, "Found the same output.json"),
                ]
            )
            self.write_run(root, "eval-one", "with_skill", duplicate, 1200, 3000)
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

    def test_huge_numeric_value_is_a_bounded_aggregate_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Has result", True, "Found output.json")]),
                10**1000,
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
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "aggregate",
                    str(root),
                    "--candidate",
                    "with_skill",
                    "--baseline",
                    "old_skill",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("aggregate.run_incomplete", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)

    def test_aggregates_multiple_large_finite_values_without_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for eval_name in ("eval-one", "eval-two"):
                self.write_run(
                    root,
                    eval_name,
                    "with_skill",
                    grading([("Has result", True, "Found output.json")]),
                    10**308,
                    3000,
                )
                self.write_run(
                    root,
                    eval_name,
                    "old_skill",
                    grading([("Has result", False, "output.json is absent")]),
                    900,
                    2000,
                )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertEqual(
            result["facts"]["run_summary"]["with_skill"]["tokens"]["mean"],
            float(10**308),
        )

    def test_rejects_linked_configuration_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-config"
            write(
                external / "grading.json",
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            write(
                external / "timing.json",
                json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
            )
            linked_config = root / "eval-one" / "with_skill"
            linked_config.parent.mkdir(parents=True)
            symlink_or_skip(
                self, linked_config, external, target_is_directory=True
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

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.path_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertNotIn("with_skill", result["facts"]["run_summary"])

    def test_rejects_linked_run_data_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external_grading = temporary_root / "external-grading.json"
            write(
                external_grading,
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            candidate = root / "eval-one" / "with_skill"
            candidate.mkdir(parents=True)
            symlink_or_skip(self, candidate / "grading.json", external_grading)
            write(
                candidate / "timing.json",
                json.dumps({"total_tokens": 1200, "duration_ms": 3000}),
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

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )
        candidate_runs = [
            run
            for run in result["facts"]["runs"]
            if run["configuration"] == "with_skill"
        ]
        self.assertEqual(
            candidate_runs,
            [
                {
                    "eval": "eval-one",
                    "configuration": "with_skill",
                    "complete": False,
                }
            ],
        )

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_junctioned_configuration_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-config"
            write(
                external / "grading.json",
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            write(
                external / "timing.json",
                json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
            )
            linked_config = root / "eval-one" / "with_skill"
            linked_config.parent.mkdir(parents=True)
            junction_or_fail(self, linked_config, external)
            try:
                self.write_run(
                    root,
                    "eval-one",
                    "old_skill",
                    grading([("Has result", False, "output.json is absent")]),
                    900,
                    2000,
                )
                result, status = REVIEW.aggregate(
                    root, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(linked_config):
                    os.rmdir(linked_config)
            self.assertTrue((external / "grading.json").is_file())
            self.assertTrue((external / "timing.json").is_file())

        self.assertEqual(status, 1)
        self.assertTrue(
            {"aggregate.path_symlink", "aggregate.configuration_missing"}.issubset(
                {finding["code"] for finding in result["findings"]}
            )
        )
        self.assertNotIn("with_skill", result["facts"]["run_summary"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertNotIn("424242", json.dumps(result))

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_junctioned_eval_directory_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-eval"
            root.mkdir()
            for configuration, passed in (("with_skill", True), ("old_skill", False)):
                write(
                    external / configuration / "grading.json",
                    json.dumps(
                        grading(
                            [
                                (
                                    "Has result",
                                    passed,
                                    "External result sentinel",
                                )
                            ]
                        )
                    ),
                )
                write(
                    external / configuration / "timing.json",
                    json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
                )
            link = root / "eval-one"
            junction_or_fail(self, link, external)
            try:
                result, status = REVIEW.aggregate(
                    root, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue((external / "with_skill" / "grading.json").is_file())
            self.assertTrue((external / "old_skill" / "timing.json").is_file())

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.path_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(result["facts"]["runs"], [])
        self.assertEqual(result["facts"]["run_summary"], {})
        self.assertIsNone(result["facts"]["delta"])
        self.assertFalse(result["facts"]["complete"])
        self.assertNotIn("424242", json.dumps(result))

    @unittest.skipUnless(
        os.name == "posix", "symbolic-link output test is POSIX-only"
    )
    def test_output_rejects_final_symlink_without_touching_target(self) -> None:
        for force_arguments in ((), ("--force",)):
            with self.subTest(force=bool(force_arguments)):
                with tempfile.TemporaryDirectory() as temporary:
                    temporary_root = Path(temporary)
                    root = temporary_root / "iteration"
                    external = temporary_root / "external.json"
                    output = root / "benchmark.json"
                    self.write_complete_pair(root)
                    write(external, "EXTERNAL_OUTPUT_SENTINEL")
                    output.symlink_to(external)

                    completed = self.run_aggregate_cli(
                        root,
                        "--output",
                        str(output),
                        *force_arguments,
                    )

                    self.assertEqual(
                        external.read_text(encoding="utf-8"),
                        "EXTERNAL_OUTPUT_SENTINEL",
                    )
                    self.assertTrue(output.is_symlink())

                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("Error:", completed.stderr)
                self.assertNotIn("unrecognized arguments", completed.stderr)
                self.assertTrue(
                    "symbolic link" in completed.stderr.lower()
                    or "reparse" in completed.stderr.lower(),
                    completed.stderr,
                )
                self.assertNotIn("Traceback", completed.stderr)

    @unittest.skipUnless(
        os.name == "posix", "symbolic-link output test is POSIX-only"
    )
    def test_output_rejects_symlinked_parent_without_writing_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-reports"
            linked_parent = root / "reports"
            external.mkdir()
            self.write_complete_pair(root)
            linked_parent.symlink_to(external, target_is_directory=True)
            external_output = external / "benchmark.json"

            completed = self.run_aggregate_cli(
                root,
                "--output",
                str(linked_parent / "benchmark.json"),
                "--force",
            )

            self.assertFalse(external_output.exists())
            self.assertTrue(linked_parent.is_symlink())

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertNotIn("unrecognized arguments", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_output_rejects_junctioned_parent_without_writing_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-reports"
            linked_parent = root / "reports"
            external.mkdir()
            self.write_complete_pair(root)
            junction_or_fail(self, linked_parent, external)
            external_output = external / "benchmark.json"
            try:
                completed = self.run_aggregate_cli(
                    root,
                    "--output",
                    str(linked_parent / "benchmark.json"),
                    "--force",
                )
                self.assertFalse(external_output.exists())
                self.assertTrue(REVIEW.is_link_like(linked_parent))
            finally:
                if os.path.lexists(linked_parent):
                    os.rmdir(linked_parent)

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertNotIn("unrecognized arguments", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_output_must_remain_inside_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            outside = temporary_root / "benchmark.json"
            self.write_complete_pair(root)

            completed = self.run_aggregate_cli(
                root,
                "--output",
                str(outside),
            )

            self.assertFalse(outside.exists())

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("iteration", completed.stderr.lower())
        self.assertNotIn("Traceback", completed.stderr)

    def test_output_refuses_existing_regular_file_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            output = root / "benchmark.json"
            self.write_complete_pair(root)
            write(output, "EXISTING_OUTPUT_SENTINEL")

            completed = self.run_aggregate_cli(root, "--output", str(output))

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "EXISTING_OUTPUT_SENTINEL",
            )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--force", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_output_new_file_matches_stdout_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            output = root / "benchmark.json"
            self.write_complete_pair(root)

            completed = self.run_aggregate_cli(root, "--output", str(output))

            self.assertEqual(completed.stdout, output.read_text(encoding="utf-8"))
            self.assertFalse(list(root.glob(".skill-review-*.tmp")))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        json.loads(completed.stdout)
        self.assertEqual(completed.stderr, "")

    @unittest.skipUnless(os.name == "posix", "long NAME_MAX test requires POSIX")
    def test_output_supports_a_long_valid_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            output = root / (("x" * 235) + ".json")
            self.write_complete_pair(root)

            completed = self.run_aggregate_cli(root, "--output", str(output))

            self.assertEqual(completed.stdout, output.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        json.loads(completed.stdout)

    @unittest.skipUnless(os.name == "posix", "symbolic links require POSIX")
    def test_output_uses_the_iteration_root_fixed_before_alias_retarget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            original = temporary_root / "original"
            replacement = temporary_root / "replacement"
            alias = temporary_root / "iteration-alias"
            original.mkdir()
            replacement.mkdir()
            alias.symlink_to(original, target_is_directory=True)
            fixed_info = os.lstat(original)
            alias.unlink()
            alias.symlink_to(replacement, target_is_directory=True)

            REVIEW.write_aggregate_output(
                str(alias),
                str(alias / "benchmark.json"),
                "EXPECTED\n",
                force=False,
                resolved_iteration=original,
                expected_root_info=fixed_info,
            )

            self.assertEqual(
                (original / "benchmark.json").read_text(encoding="utf-8"),
                "EXPECTED\n",
            )
            self.assertFalse((replacement / "benchmark.json").exists())

    @unittest.skipUnless(
        os.name == "posix" and REVIEW.output_dir_fd_supported(),
        "directory-descriptor publication requires POSIX dir_fd support",
    )
    def test_output_parent_swap_cannot_publish_attacker_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            reports = root / "reports"
            moved_reports = Path(temporary) / "moved-reports"
            reports.mkdir(parents=True)
            fixed_info = os.lstat(root)
            original_validate = REVIEW.validate_output_entry_info
            validations = 0

            def swapping_validate(
                destination: Path,
                info: os.stat_result | None,
                *,
                force: bool,
            ) -> None:
                nonlocal validations
                original_validate(destination, info, force=force)
                validations += 1
                if validations == 2:
                    reports.rename(moved_reports)
                    reports.mkdir()
                    temporary_name = next(
                        moved_reports.glob(".skill-review-*.tmp")
                    ).name
                    write(reports / temporary_name, "ATTACKER\n")

            with (
                mock.patch.object(
                    OUTPUT_MODULE,
                    "validate_output_entry_info",
                    side_effect=swapping_validate,
                ),
                self.assertRaisesRegex(ValueError, "parent changed"),
            ):
                REVIEW.write_aggregate_output(
                    str(root),
                    str(reports / "benchmark.json"),
                    "EXPECTED\n",
                    force=False,
                    resolved_iteration=root,
                    expected_root_info=fixed_info,
                )

            self.assertEqual(validations, 2)
            self.assertFalse((reports / "benchmark.json").exists())
            self.assertFalse((moved_reports / "benchmark.json").exists())
            attacker_files = list(reports.glob(".skill-review-*.tmp"))
            self.assertEqual(len(attacker_files), 1)
            self.assertEqual(
                attacker_files[0].read_text(encoding="utf-8"), "ATTACKER\n"
            )
            self.assertFalse(list(moved_reports.glob(".skill-review-*.tmp")))

    @unittest.skipUnless(
        os.name == "posix" and REVIEW.output_dir_fd_supported(),
        "directory-descriptor publication requires POSIX dir_fd support",
    )
    def test_output_parent_swap_rolls_back_forced_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            reports = root / "reports"
            moved_reports = Path(temporary) / "moved-reports"
            destination = reports / "benchmark.json"
            write(destination, "ORIGINAL\n")
            fixed_info = os.lstat(root)
            original_validate = REVIEW.validate_output_entry_info
            validations = 0

            def swapping_validate(
                output: Path,
                info: os.stat_result | None,
                *,
                force: bool,
            ) -> None:
                nonlocal validations
                original_validate(output, info, force=force)
                validations += 1
                if validations == 2:
                    reports.rename(moved_reports)
                    reports.mkdir()

            with (
                mock.patch.object(
                    OUTPUT_MODULE,
                    "validate_output_entry_info",
                    side_effect=swapping_validate,
                ),
                self.assertRaisesRegex(ValueError, "parent changed"),
            ):
                REVIEW.write_aggregate_output(
                    str(root),
                    str(destination),
                    "REPLACEMENT\n",
                    force=True,
                    resolved_iteration=root,
                    expected_root_info=fixed_info,
                )

            self.assertEqual(validations, 2)
            self.assertFalse(destination.exists())
            self.assertEqual(
                (moved_reports / "benchmark.json").read_text(encoding="utf-8"),
                "ORIGINAL\n",
            )
            self.assertFalse(list(moved_reports.glob(".skill-review-*.tmp")))

    def test_output_force_replaces_entry_without_mutating_hardlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external.json"
            output = root / "benchmark.json"
            self.write_complete_pair(root)
            write(external, "EXTERNAL_HARDLINK_SENTINEL")
            try:
                os.link(external, output)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"hard links are unavailable: {exc}")
            self.assertTrue(os.path.samefile(external, output))

            completed = self.run_aggregate_cli(
                root,
                "--output",
                str(output),
                "--force",
            )

            self.assertEqual(
                external.read_text(encoding="utf-8"),
                "EXTERNAL_HARDLINK_SENTINEL",
            )
            self.assertFalse(os.path.samefile(external, output))
            self.assertEqual(completed.stdout, output.read_text(encoding="utf-8"))
            self.assertFalse(list(root.glob(".skill-review-*.tmp")))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        json.loads(completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_output_dash_is_identical_to_stdout_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            self.write_complete_pair(root)

            ordinary = self.run_aggregate_cli(root, cwd=temporary_root)
            explicit_stdout = self.run_aggregate_cli(
                root,
                "--output",
                "-",
                cwd=temporary_root,
            )

            self.assertFalse((temporary_root / "-").exists())

        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual(explicit_stdout.returncode, 0, explicit_stdout.stderr)
        self.assertEqual(explicit_stdout.stdout, ordinary.stdout)
        json.loads(explicit_stdout.stdout)


if __name__ == "__main__":
    unittest.main()
