"""Paired-run aggregation and output publication."""

from __future__ import annotations

import hashlib
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
    campaign_id = "campaign-one"
    environment_identity = "test-environment"
    candidate_starting_identity = "sha256:" + ("1" * 64)
    candidate_identity = "sha256:" + ("2" * 64)
    baseline_identity = "sha256:" + ("3" * 64)

    def write_plan_data(self, root: Path, plan: dict[str, object]) -> str:
        plan_text = json.dumps(plan)
        write(root.parent / "evaluation-plan.json", plan_text)
        plan_identity = (
            "sha256:" + hashlib.sha256(plan_text.encode("utf-8")).hexdigest()
        )
        for provenance_path in root.glob("eval-*/*/provenance.json"):
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["plan_identity"] = plan_identity
            write(provenance_path, json.dumps(provenance))
        return plan_identity

    def write_plan(
        self,
        root: Path,
        eval_name: str,
        grading_data: dict[str, object],
    ) -> str:
        path = root.parent / "evaluation-plan.json"
        if path.exists():
            plan = json.loads(path.read_text(encoding="utf-8"))
        else:
            plan = {
                "schema_version": 1,
                "campaign_id": self.campaign_id,
                "environment_identity": self.environment_identity,
                "candidate": {
                    "name": "with_skill",
                    "starting_package_identity": self.candidate_starting_identity,
                },
                "baseline": {
                    "name": "old_skill",
                    "package_identity": self.baseline_identity,
                },
                "acceptance": {
                    "min_candidate_pass_rate": 0,
                    "min_pass_rate_delta": -1,
                },
                "evals": [],
            }
        if not any(item["directory"] == eval_name for item in plan["evals"]):
            assertion_texts = []
            for assertion in grading_data.get("assertion_results", []):
                if not isinstance(assertion, dict):
                    continue
                text = assertion.get("text")
                if isinstance(text, str) and text.strip() not in assertion_texts:
                    assertion_texts.append(text.strip())
            plan["evals"].append(
                {
                    "id": eval_name.removeprefix("eval-"),
                    "directory": eval_name,
                    "assertions": assertion_texts or ["Has result"],
                }
            )
        return self.write_plan_data(root, plan)

    def write_run(
        self,
        root: Path,
        eval_name: str,
        configuration: str,
        grading_data: dict[str, object],
        tokens: int,
        duration_ms: int,
    ) -> None:
        plan_identity = self.write_plan(root, eval_name, grading_data)
        run = root / eval_name / configuration
        write(run / "grading.json", json.dumps(grading_data))
        write(
            run / "timing.json",
            json.dumps({"total_tokens": tokens, "duration_ms": duration_ms}),
        )
        package_identity = (
            self.candidate_identity
            if configuration == "with_skill"
            else self.baseline_identity
        )
        write(
            run / "provenance.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "campaign_id": self.campaign_id,
                    "eval_id": eval_name.removeprefix("eval-"),
                    "configuration": configuration,
                    "plan_identity": plan_identity,
                    "package_identity": package_identity,
                    "environment_identity": self.environment_identity,
                }
            ),
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
            root = Path(temporary) / "iteration"
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
            plan_text = (root.parent / "evaluation-plan.json").read_text(
                encoding="utf-8"
            )
            plan_identity = (
                "sha256:" + hashlib.sha256(plan_text.encode("utf-8")).hexdigest()
            )

        self.assertEqual(status, 0)
        self.assertEqual(result["schema_version"], 1)
        self.assertTrue(result["facts"]["complete"])
        self.assertTrue(result["facts"]["evidence_complete"])
        self.assertEqual(result["facts"]["gate"]["status"], "passed")
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)
        self.assertEqual(
            result["facts"]["campaign"],
            {
                "schema_version": 1,
                "id": self.campaign_id,
                "plan_identity": plan_identity,
                "environment_identity": self.environment_identity,
            },
        )
        self.assertEqual(
            result["facts"]["coverage"],
            {
                "planned": ["eval-one"],
                "discovered": ["eval-one"],
                "matched": ["eval-one"],
            },
        )
        self.assertEqual(
            result["facts"]["identities"],
            {
                "candidate": self.candidate_identity,
                "candidate_starting": self.candidate_starting_identity,
                "baseline": self.baseline_identity,
                "environment": self.environment_identity,
            },
        )
        self.assertEqual(len(result["facts"]["provenance"]), 2)
        self.assertTrue(all(item["valid"] for item in result["facts"]["provenance"]))
        self.assertEqual(
            result["facts"]["gate"]["checks"],
            [
                {
                    "name": "min_candidate_pass_rate",
                    "operator": ">=",
                    "threshold": 0.0,
                    "actual": 1.0,
                    "passed": True,
                },
                {
                    "name": "min_pass_rate_delta",
                    "operator": ">=",
                    "threshold": -1.0,
                    "actual": 1.0,
                    "passed": True,
                },
            ],
        )

    def test_acceptance_failure_preserves_complete_evidence_and_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            failed = grading([("Has result", False, "No output")])
            self.write_run(root, "eval-one", "with_skill", failed, 900, 2000)
            self.write_run(root, "eval-one", "old_skill", failed, 900, 2000)
            plan_path = root.parent / "evaluation-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["acceptance"] = {
                "min_candidate_pass_rate": 0.5,
                "min_pass_rate_delta": 0,
            }
            self.write_plan_data(root, plan)

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)
            truncated, truncated_status = REVIEW.aggregate(
                root, "with_skill", "old_skill", 0
            )
            completed = self.run_aggregate_cli(root)

        self.assertEqual(status, 1)
        self.assertTrue(result["facts"]["evidence_complete"])
        self.assertTrue(result["facts"]["complete"])
        self.assertIsNotNone(result["facts"]["delta"])
        self.assertEqual(result["facts"]["gate"]["status"], "failed")
        checks = {item["name"]: item for item in result["facts"]["gate"]["checks"]}
        self.assertFalse(checks["min_candidate_pass_rate"]["passed"])
        self.assertTrue(checks["min_pass_rate_delta"]["passed"])
        self.assertIn(
            "aggregate.acceptance_failed",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(truncated_status, 1)
        self.assertEqual(truncated["findings"], [])
        self.assertTrue(truncated["summary"]["truncated"])
        self.assertTrue(truncated["facts"]["evidence_complete"])
        self.assertIsNotNone(truncated["facts"]["delta"])
        self.assertEqual(truncated["facts"]["gate"]["status"], "failed")
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout)["facts"]["gate"], result["facts"]["gate"]
        )

    def test_acceptance_numeric_boundaries_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            plan_path = root.parent / "evaluation-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["acceptance"] = {
                "min_candidate_pass_rate": 1,
                "min_pass_rate_delta": 1,
                "max_time_seconds_delta": 1,
                "max_tokens_delta": 300,
                "max_baseline_only": 0,
            }
            self.write_plan_data(root, plan)

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["gate"]["status"], "passed")
        self.assertTrue(
            all(check["passed"] for check in result["facts"]["gate"]["checks"])
        )

    def test_acceptance_does_not_hide_material_near_threshold_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            failed = grading([("Has result", False, "No output")])
            self.write_run(root, "eval-one", "with_skill", failed, 1200, 3000)
            self.write_run(root, "eval-one", "old_skill", failed, 900, 2000)
            plan_path = root.parent / "evaluation-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["acceptance"] = {
                "min_candidate_pass_rate": 1e-10,
                "min_pass_rate_delta": -1,
            }
            self.write_plan_data(root, plan)

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["facts"]["gate"]["status"], "failed")
        self.assertFalse(result["facts"]["gate"]["checks"][0]["passed"])

    def test_rejects_invalid_acceptance_contract(self) -> None:
        mutations = {
            "missing required": {"min_candidate_pass_rate": 0},
            "unknown field": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": -1,
                "custom_rule": 1,
            },
            "candidate below range": {
                "min_candidate_pass_rate": -0.0001,
                "min_pass_rate_delta": -1,
            },
            "candidate above range": {
                "min_candidate_pass_rate": 1.0001,
                "min_pass_rate_delta": -1,
            },
            "delta below range": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": -1.0001,
            },
            "delta above range": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": 1.0001,
            },
            "negative time": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": -1,
                "max_time_seconds_delta": -0.0001,
            },
            "negative tokens": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": -1,
                "max_tokens_delta": -1,
            },
            "fractional baseline only": {
                "min_candidate_pass_rate": 0,
                "min_pass_rate_delta": -1,
                "max_baseline_only": 0.0,
            },
        }
        for label, acceptance in mutations.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "iteration"
                    self.write_complete_pair(root)
                    plan_path = root.parent / "evaluation-plan.json"
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    plan["acceptance"] = acceptance
                    write(plan_path, json.dumps(plan))

                    result, status = REVIEW.aggregate(
                        root, "with_skill", "old_skill", 100
                    )

                self.assertEqual(status, 1)
                self.assertFalse(result["facts"]["evidence_complete"])
                self.assertIsNone(result["facts"]["delta"])
                self.assertEqual(result["facts"]["gate"]["status"], "indeterminate")
                self.assertIn(
                    "aggregate.plan_invalid",
                    {finding["code"] for finding in result["findings"]},
                )

    def test_requires_v1_plan_and_provenance_schema(self) -> None:
        for target in ("plan", "provenance"):
            for label, value in (
                ("missing", None),
                ("boolean", True),
                ("float", 1.0),
                ("other version", 2),
            ):
                with self.subTest(target=target, value=label):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary) / "iteration"
                        self.write_complete_pair(root)
                        path = (
                            root.parent / "evaluation-plan.json"
                            if target == "plan"
                            else root / "eval-one" / "with_skill" / "provenance.json"
                        )
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if label == "missing":
                            data.pop("schema_version")
                        else:
                            data["schema_version"] = value
                        write(path, json.dumps(data))

                        result, status = REVIEW.aggregate(
                            root, "with_skill", "old_skill", 100
                        )

                    self.assertEqual(status, 1)
                    self.assertEqual(result["schema_version"], 1)
                    self.assertFalse(result["facts"]["evidence_complete"])
                    self.assertEqual(result["facts"]["gate"]["status"], "indeterminate")
                    expected = (
                        "aggregate.plan_invalid"
                        if target == "plan"
                        else "aggregate.run_incomplete"
                    )
                    self.assertIn(
                        expected, {finding["code"] for finding in result["findings"]}
                    )

    def test_binds_every_run_to_exact_plan_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            plan_path = root.parent / "evaluation-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["acceptance"]["min_candidate_pass_rate"] = 0.25
            write(plan_path, json.dumps(plan))

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["evidence_complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertEqual(result["facts"]["gate"]["status"], "indeterminate")
        self.assertTrue(
            all(check["passed"] is None for check in result["facts"]["gate"]["checks"])
        )
        self.assertIn(
            "aggregate.provenance_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_requires_sha256_package_identities(self) -> None:
        targets = {
            "candidate plan": ("plan", "candidate", "starting_package_identity"),
            "baseline plan": ("plan", "baseline", "package_identity"),
            "candidate provenance": ("provenance", None, "package_identity"),
        }
        for label, (target, section, field) in targets.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "iteration"
                    self.write_complete_pair(root)
                    path = (
                        root.parent / "evaluation-plan.json"
                        if target == "plan"
                        else root / "eval-one" / "with_skill" / "provenance.json"
                    )
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if section is None:
                        data[field] = "sha256:" + ("a" * 63)
                    else:
                        data[section][field] = "sha256:" + ("a" * 63)
                    write(path, json.dumps(data))

                    result, status = REVIEW.aggregate(
                        root, "with_skill", "old_skill", 100
                    )

                self.assertEqual(status, 1)
                expected = (
                    "aggregate.plan_invalid"
                    if target == "plan"
                    else "aggregate.run_incomplete"
                )
                self.assertIn(
                    expected, {finding["code"] for finding in result["findings"]}
                )

    def test_requires_a_safe_frozen_evaluation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            (root.parent / "evaluation-plan.json").unlink()

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertFalse(result["facts"]["evidence_complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertEqual(
            result["facts"]["gate"], {"status": "indeterminate", "checks": []}
        )
        self.assertIn(
            "aggregate.plan_invalid",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_oversized_plan_and_provenance_files(self) -> None:
        for target in ("plan", "provenance"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "iteration"
                    self.write_complete_pair(root)
                    if target == "plan":
                        path = root.parent / "evaluation-plan.json"
                    else:
                        path = root / "eval-one" / "with_skill" / "provenance.json"
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["padding"] = "x" * 2000
                    oversized = json.dumps(data)
                    write(path, oversized)

                    with mock.patch.object(
                        FS_SAFETY, "MAX_TEXT_FILE_BYTES", len(oversized) - 1
                    ):
                        result, status = REVIEW.aggregate(
                            root, "with_skill", "old_skill", 100
                        )

                self.assertEqual(status, 1)
                self.assertFalse(result["facts"]["complete"])
                self.assertIsNone(result["facts"]["delta"])
                expected = (
                    "aggregate.plan_invalid"
                    if target == "plan"
                    else "aggregate.run_incomplete"
                )
                self.assertIn(expected, {item["code"] for item in result["findings"]})
                self.assertIn("resource exceeds", json.dumps(result).lower())

    def test_requires_exact_planned_eval_coverage(self) -> None:
        for mismatch in ("missing", "extra"):
            with self.subTest(mismatch=mismatch):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "iteration"
                    self.write_complete_pair(root)
                    plan_path = root.parent / "evaluation-plan.json"
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    if mismatch == "missing":
                        plan["evals"].append(
                            {
                                "id": "two",
                                "directory": "eval-two",
                                "assertions": ["Has result"],
                            }
                        )
                        write(plan_path, json.dumps(plan))
                    else:
                        (root / "eval-two").mkdir()

                    result, status = REVIEW.aggregate(
                        root, "with_skill", "old_skill", 100
                    )

                self.assertEqual(status, 1)
                self.assertFalse(result["facts"]["complete"])
                self.assertIsNone(result["facts"]["delta"])
                self.assertIn(
                    "aggregate.coverage_mismatch",
                    {finding["code"] for finding in result["findings"]},
                )

    def test_requires_provenance_for_every_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            (root / "eval-one" / "with_skill" / "provenance.json").unlink()

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_provenance_and_plan_binding_mismatches(self) -> None:
        mutations = {
            "campaign": ("provenance", "campaign_id", "other-campaign"),
            "eval": ("provenance", "eval_id", "other-eval"),
            "configuration": ("provenance", "configuration", "with_skill"),
            "environment": ("provenance", "environment_identity", "other-env"),
            "baseline package": (
                "provenance",
                "package_identity",
                "sha256:" + ("4" * 64),
            ),
            "assertions": ("plan", "assertions", ["Other assertion"]),
        }
        for label, (target, field, value) in mutations.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "iteration"
                    self.write_complete_pair(root)
                    if target == "plan":
                        path = root.parent / "evaluation-plan.json"
                        data = json.loads(path.read_text(encoding="utf-8"))
                        data["evals"][0][field] = value
                    else:
                        path = root / "eval-one" / "old_skill" / "provenance.json"
                        data = json.loads(path.read_text(encoding="utf-8"))
                        data[field] = value
                    write(path, json.dumps(data))

                    result, status = REVIEW.aggregate(
                        root, "with_skill", "old_skill", 100
                    )

                self.assertEqual(status, 1)
                self.assertFalse(result["facts"]["complete"])
                self.assertIsNone(result["facts"]["delta"])
                expected = (
                    "aggregate.assertion_plan_mismatch"
                    if target == "plan"
                    else "aggregate.provenance_mismatch"
                )
                self.assertIn(expected, {item["code"] for item in result["findings"]})

    def test_candidate_package_identity_is_consistent_within_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            for configuration, passed in (("with_skill", True), ("old_skill", False)):
                self.write_run(
                    root,
                    "eval-two",
                    configuration,
                    grading([("Has result", passed, "Retained evidence")]),
                    1000,
                    2000,
                )
            path = root / "eval-two" / "with_skill" / "provenance.json"
            provenance = json.loads(path.read_text(encoding="utf-8"))
            provenance["package_identity"] = "sha256:" + ("4" * 64)
            write(path, json.dumps(provenance))

            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertNotIn("with_skill", result["facts"]["run_summary"])
        self.assertIn(
            "aggregate.provenance_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_reports_per_assertion_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
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
            root = Path(temporary) / "iteration"
            self.write_complete_pair(root)
            (root / "eval-one" / "unselected").mkdir()
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["complete"])
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)
        self.assertNotIn("unselected", result["facts"]["run_summary"])

    def test_aggregate_text_output_includes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
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
        self.assertTrue(metrics["evidence_complete"])
        self.assertEqual(metrics["gate"]["status"], "passed")
        self.assertTrue(metrics["complete"])

    def test_json_output_safely_escapes_unpaired_surrogates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iteration"
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
                result, status = REVIEW.aggregate(alias, "with_skill", "old_skill", 100)
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
            root = Path(temporary) / "iteration"
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
            root = Path(temporary) / "iteration"
            candidate_grading = grading([("Has result", True, "Found output.json")])
            candidate_grading["padding"] = "x" * 2000
            candidate_grading_text = json.dumps(candidate_grading)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                candidate_grading,
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
            root = Path(temporary) / "iteration"
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
            root = Path(temporary) / "iteration"
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
            root = Path(temporary) / "iteration"
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
            root = Path(temporary) / "iteration"
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
            symlink_or_skip(self, linked_config, external, target_is_directory=True)
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
                result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)
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
                result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)
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

    @unittest.skipUnless(os.name == "posix", "symbolic-link output test is POSIX-only")
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

    @unittest.skipUnless(os.name == "posix", "symbolic-link output test is POSIX-only")
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
