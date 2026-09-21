"""Paired-run aggregation of grading and timing evidence.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .fs_safety import (
    TextReadBudget,
    first_link_like_component,
    is_link_like,
    read_bounded_regular_utf8,
    resolve_within,
)
from .report import Finding, add_finding, finalize


def numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    try:
        converted = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be finite and non-negative") from exc
    if not math.isfinite(converted) or converted < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return converted


def metric(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        # statistics.mean avoids fmean's intermediate float overflow for
        # individually finite values near the platform maximum.
        "mean": statistics.mean(values),
        "stddev": statistics.stdev(values) if len(values) > 1 else None,
    }


def nonempty_string(data: dict[str, Any], field: str, label: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value


def parse_plan(
    workspace: Path,
    candidate: str,
    baseline: str,
    text_budget: TextReadBudget,
) -> dict[str, Any]:
    path = workspace / "evaluation-plan.json"
    try:
        plan = json.loads(read_bounded_regular_utf8(workspace, path, text_budget))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"evaluation-plan.json is missing or unsafe: {exc}") from exc
    if not isinstance(plan, dict):
        raise ValueError("evaluation-plan.json must be an object")

    campaign_id = nonempty_string(plan, "campaign_id", "evaluation-plan.json")
    environment = nonempty_string(plan, "environment_identity", "evaluation-plan.json")
    candidate_plan = plan.get("candidate")
    baseline_plan = plan.get("baseline")
    if not isinstance(candidate_plan, dict):
        raise ValueError("evaluation-plan.json.candidate must be an object")
    if not isinstance(baseline_plan, dict):
        raise ValueError("evaluation-plan.json.baseline must be an object")
    candidate_name = nonempty_string(candidate_plan, "name", "candidate")
    candidate_starting = nonempty_string(
        candidate_plan, "starting_package_identity", "candidate"
    )
    baseline_name = nonempty_string(baseline_plan, "name", "baseline")
    baseline_identity = nonempty_string(baseline_plan, "package_identity", "baseline")
    if candidate_name != candidate or baseline_name != baseline:
        raise ValueError(
            "plan configuration names must match --candidate and --baseline"
        )

    evals = plan.get("evals")
    if not isinstance(evals, list) or not evals:
        raise ValueError("evaluation-plan.json.evals must be a non-empty array")
    by_directory: dict[str, dict[str, Any]] = {}
    eval_ids: set[str] = set()
    for index, item in enumerate(evals):
        label = f"evaluation-plan.json.evals[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        eval_id = nonempty_string(item, "id", label)
        directory = nonempty_string(item, "directory", label)
        if (
            not directory.startswith("eval-")
            or Path(directory).name != directory
            or "/" in directory
            or "\\" in directory
        ):
            raise ValueError(f"{label}.directory must be one eval-* directory name")
        if eval_id in eval_ids:
            raise ValueError(f'{label}.id duplicates "{eval_id}"')
        if directory in by_directory:
            raise ValueError(f'{label}.directory duplicates "{directory}"')
        assertions = item.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"{label}.assertions must be a non-empty array")
        normalized_assertions: set[str] = set()
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, str) or not assertion.strip():
                raise ValueError(
                    f"{label}.assertions[{assertion_index}] must be a non-empty string"
                )
            normalized = assertion.strip()
            if normalized in normalized_assertions:
                raise ValueError(f'{label}.assertions duplicates "{normalized}"')
            normalized_assertions.add(normalized)
        eval_ids.add(eval_id)
        by_directory[directory] = {
            "id": eval_id,
            "assertions": normalized_assertions,
        }
    return {
        "campaign_id": campaign_id,
        "environment_identity": environment,
        "candidate_starting_identity": candidate_starting,
        "baseline_identity": baseline_identity,
        "evals": by_directory,
    }


def parse_run(
    root: Path, config_dir: Path, text_budget: TextReadBudget
) -> dict[str, Any]:
    grading_path = config_dir / "grading.json"
    timing_path = config_dir / "timing.json"
    provenance_path = config_dir / "provenance.json"
    redirected = [
        path.name
        for path in (grading_path, timing_path, provenance_path)
        if first_link_like_component(root, path) is not None
    ]
    if redirected:
        raise ValueError(
            f"{', '.join(redirected)} must not be symbolic links or reparse points"
        )
    missing = [
        path.name
        for path in (grading_path, timing_path, provenance_path)
        if not path.is_file()
    ]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    try:
        for path in (grading_path, timing_path, provenance_path):
            resolve_within(root, path, strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("run data must resolve inside the iteration root") from exc
    try:
        grading = json.loads(read_bounded_regular_utf8(root, grading_path, text_budget))
        timing = json.loads(read_bounded_regular_utf8(root, timing_path, text_budget))
        provenance = json.loads(
            read_bounded_regular_utf8(root, provenance_path, text_budget)
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(grading, dict):
        raise ValueError("grading.json must be an object")
    if not isinstance(timing, dict):
        raise ValueError("timing.json must be an object")
    if not isinstance(provenance, dict):
        raise ValueError("provenance.json must be an object")
    for field in (
        "campaign_id",
        "eval_id",
        "configuration",
        "package_identity",
        "environment_identity",
    ):
        nonempty_string(provenance, field, "provenance.json")

    assertion_results = grading.get("assertion_results")
    if not isinstance(assertion_results, list) or not assertion_results:
        raise ValueError(
            "grading.json must contain a non-empty assertion_results array"
        )
    passed = 0
    assertion_texts: set[str] = set()
    assertions: dict[str, dict[str, Any]] = {}
    for index, assertion in enumerate(assertion_results):
        label = f"assertion_results[{index}]"
        if not isinstance(assertion, dict):
            raise ValueError(f"{label} must be an object")
        if not isinstance(assertion.get("text"), str) or not assertion["text"].strip():
            raise ValueError(f"{label}.text must be a non-empty string")
        normalized_text = assertion["text"].strip()
        if normalized_text in assertion_texts:
            raise ValueError(f"{label}.text duplicates an earlier assertion")
        assertion_texts.add(normalized_text)
        if not isinstance(assertion.get("passed"), bool):
            raise ValueError(f"{label}.passed must be a boolean")
        if (
            not isinstance(assertion.get("evidence"), str)
            or not assertion["evidence"].strip()
        ):
            raise ValueError(f"{label}.evidence must be a non-empty string")
        assertions[normalized_text] = {
            "passed": assertion["passed"],
            "evidence": assertion["evidence"].strip(),
        }
        passed += int(assertion["passed"])

    summary = grading.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("grading.json must contain a summary object")
    total = len(assertion_results)
    expected_counts = {"passed": passed, "failed": total - passed, "total": total}
    for key, expected in expected_counts.items():
        actual = summary.get(key)
        if (
            isinstance(actual, bool)
            or not isinstance(actual, int)
            or actual != expected
        ):
            raise ValueError(f"summary.{key} must equal {expected}")
    pass_rate = numeric(summary.get("pass_rate"), "summary.pass_rate")
    expected_pass_rate = passed / total
    if not math.isclose(pass_rate, expected_pass_rate, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"summary.pass_rate must equal {expected_pass_rate}")
    return {
        "pass_rate": expected_pass_rate,
        "time_seconds": numeric(timing.get("duration_ms"), "duration_ms") / 1000,
        "tokens": numeric(timing.get("total_tokens"), "total_tokens"),
        "assertion_texts": assertion_texts,
        "assertions": assertions,
        "provenance": provenance,
    }


def aggregate(
    iteration: Path,
    candidate: str,
    baseline: str,
    max_findings: int,
) -> tuple[dict[str, Any], int]:
    root = iteration.resolve()
    if not root.is_dir():
        raise ValueError(
            f'Iteration must be an existing directory; received "{iteration}".'
        )
    if (
        not isinstance(candidate, str)
        or not candidate.strip()
        or not isinstance(baseline, str)
        or not baseline.strip()
        or candidate == baseline
    ):
        raise ValueError(
            "Candidate and baseline must be distinct non-empty directory names."
        )

    findings: list[Finding] = []
    text_budget = TextReadBudget()
    workspace = root.parent
    plan: dict[str, Any] | None
    try:
        plan = parse_plan(workspace, candidate, baseline, text_budget)
    except ValueError as exc:
        plan = None
        add_finding(
            findings,
            "error",
            "aggregate.plan_invalid",
            workspace / "evaluation-plan.json",
            f"The frozen evaluation plan is missing or malformed: {exc}.",
            "Add a safe evaluation-plan.json with the frozen campaign contract.",
        )
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"pass_rate": [], "time_seconds": [], "tokens": []}
    )
    runs: list[dict[str, Any]] = []
    provenance_facts: list[dict[str, Any]] = []
    candidate_identities: set[str] = set()
    assertion_analysis: list[dict[str, Any]] = []
    assertion_summary = {
        "candidate_only": 0,
        "baseline_only": 0,
        "both_pass": 0,
        "both_fail": 0,
    }
    eval_dirs = sorted(
        path for path in root.glob("eval-*") if is_link_like(path) or path.is_dir()
    )
    discovered_directories = {path.name for path in eval_dirs}
    planned_directories = set(plan["evals"]) if plan is not None else set()
    if plan is not None and discovered_directories != planned_directories:
        missing = sorted(planned_directories - discovered_directories)
        extra = sorted(discovered_directories - planned_directories)
        add_finding(
            findings,
            "error",
            "aggregate.coverage_mismatch",
            root,
            f"Discovered eval directories do not match the plan; missing={missing}, extra={extra}.",
            "Run exactly the eval directories frozen in evaluation-plan.json.",
        )
    elif plan is None and not eval_dirs:
        add_finding(
            findings,
            "error",
            "aggregate.coverage_mismatch",
            root,
            "No eval-* directories were found.",
            "Add the complete planned eval directory set before aggregating.",
        )

    for eval_dir in eval_dirs:
        if is_link_like(eval_dir):
            add_finding(
                findings,
                "error",
                "aggregate.path_symlink",
                eval_dir,
                "An eval directory is a symbolic link or reparse point and was not inspected.",
                "Use ordinary run directories inside the iteration root.",
            )
            continue
        try:
            resolve_within(root, eval_dir, strict=True)
        except (OSError, RuntimeError, ValueError):
            add_finding(
                findings,
                "error",
                "aggregate.path_outside",
                eval_dir,
                "An eval directory resolves outside the iteration root and was not inspected.",
                "Keep every eval directory inside the iteration root.",
            )
            continue

        config_dirs: list[Path] = []
        required_configurations = {candidate, baseline}
        for config_dir in sorted(eval_dir.iterdir()):
            if config_dir.name not in required_configurations:
                continue
            if is_link_like(config_dir):
                add_finding(
                    findings,
                    "error",
                    "aggregate.path_symlink",
                    config_dir,
                    "A configuration path is a symbolic link or reparse point and was not inspected.",
                    "Use ordinary configuration directories inside the iteration root.",
                )
                continue
            if not config_dir.is_dir():
                continue
            try:
                resolve_within(root, config_dir, strict=True)
            except (OSError, RuntimeError, ValueError):
                add_finding(
                    findings,
                    "error",
                    "aggregate.path_outside",
                    config_dir,
                    "A configuration directory resolves outside the iteration root and was not inspected.",
                    "Keep every configuration directory inside the iteration root.",
                )
                continue
            config_dirs.append(config_dir)
        present = {path.name for path in config_dirs}
        parsed_configs: dict[str, dict[str, Any]] = {}
        for required in (candidate, baseline):
            if required not in present:
                add_finding(
                    findings,
                    "error",
                    "aggregate.configuration_missing",
                    eval_dir,
                    f'Configuration directory "{required}" is missing.',
                    "Complete both sides of the paired run before comparing them.",
                )
        for config_dir in config_dirs:
            try:
                parsed = parse_run(root, config_dir, text_budget)
            except ValueError as exc:
                add_finding(
                    findings,
                    "error",
                    "aggregate.run_incomplete",
                    config_dir,
                    f"Run is incomplete or malformed: {exc}.",
                    "Add valid grading.json, timing.json, and provenance.json; do not silently drop the run.",
                )
                runs.append(
                    {
                        "eval": eval_dir.name,
                        "configuration": config_dir.name,
                        "complete": False,
                    }
                )
                continue
            provenance = parsed["provenance"]
            provenance_record = {
                "eval": eval_dir.name,
                "configuration": config_dir.name,
                "campaign_id": provenance["campaign_id"],
                "eval_id": provenance["eval_id"],
                "package_identity": provenance["package_identity"],
                "environment_identity": provenance["environment_identity"],
                "valid": False,
            }
            provenance_facts.append(provenance_record)
            if config_dir.name == candidate:
                candidate_identities.add(provenance["package_identity"])

            planned_eval = (
                plan["evals"].get(eval_dir.name) if plan is not None else None
            )
            provenance_mismatches: list[str] = []
            if plan is not None and planned_eval is not None:
                expected = {
                    "campaign_id": plan["campaign_id"],
                    "eval_id": planned_eval["id"],
                    "configuration": config_dir.name,
                    "environment_identity": plan["environment_identity"],
                }
                if config_dir.name == baseline:
                    expected["package_identity"] = plan["baseline_identity"]
                provenance_mismatches = [
                    field
                    for field, expected_value in expected.items()
                    if provenance[field] != expected_value
                ]
            provenance_valid = (
                plan is not None
                and planned_eval is not None
                and not provenance_mismatches
            )
            if provenance_mismatches:
                add_finding(
                    findings,
                    "error",
                    "aggregate.provenance_mismatch",
                    config_dir / "provenance.json",
                    "Provenance does not match the frozen plan or run: "
                    + ", ".join(provenance_mismatches)
                    + ".",
                    "Regenerate provenance from the frozen campaign, eval, configuration, package, and environment identities.",
                )
            provenance_record["valid"] = provenance_valid

            assertions_valid = (
                planned_eval is not None
                and parsed["assertion_texts"] == planned_eval["assertions"]
            )
            if planned_eval is not None and not assertions_valid:
                add_finding(
                    findings,
                    "error",
                    "aggregate.assertion_plan_mismatch",
                    config_dir / "grading.json",
                    "Grading assertions do not match the frozen eval assertions.",
                    "Grade this configuration with exactly the assertions in evaluation-plan.json.",
                )
            parsed["bound"] = provenance_valid and assertions_valid
            parsed_configs[config_dir.name] = parsed
            metrics = {
                key: parsed[key] for key in ("pass_rate", "time_seconds", "tokens")
            }
            if parsed["bound"]:
                for key, value in metrics.items():
                    values[config_dir.name][key].append(value)
            runs.append(
                {
                    "eval": eval_dir.name,
                    "configuration": config_dir.name,
                    "complete": parsed["bound"],
                    **metrics,
                }
            )

        if candidate in parsed_configs and baseline in parsed_configs:
            candidate_assertions = parsed_configs[candidate]["assertion_texts"]
            baseline_assertions = parsed_configs[baseline]["assertion_texts"]
            if candidate_assertions != baseline_assertions:
                add_finding(
                    findings,
                    "error",
                    "aggregate.assertion_set_mismatch",
                    eval_dir,
                    (
                        f'Configurations "{candidate}" and "{baseline}" use different '
                        "assertion text sets."
                    ),
                    "Grade both sides of a paired eval with the same assertions.",
                )
            elif (
                parsed_configs[candidate]["bound"] and parsed_configs[baseline]["bound"]
            ):
                counts = {key: 0 for key in assertion_summary}
                assertion_details: list[dict[str, Any]] = []
                for text in sorted(candidate_assertions):
                    candidate_result = parsed_configs[candidate]["assertions"][text]
                    baseline_result = parsed_configs[baseline]["assertions"][text]
                    candidate_passed = candidate_result["passed"]
                    baseline_passed = baseline_result["passed"]
                    if candidate_passed:
                        outcome = "both_pass" if baseline_passed else "candidate_only"
                    else:
                        outcome = "baseline_only" if baseline_passed else "both_fail"
                    counts[outcome] += 1
                    assertion_summary[outcome] += 1
                    assertion_details.append(
                        {
                            "text": text,
                            "outcome": outcome,
                            "candidate_passed": candidate_passed,
                            "candidate_evidence": candidate_result["evidence"],
                            "baseline_passed": baseline_passed,
                            "baseline_evidence": baseline_result["evidence"],
                        }
                    )
                assertion_analysis.append(
                    {
                        "eval": eval_dir.name,
                        "counts": counts,
                        "assertions": assertion_details,
                    }
                )

    candidate_identity = (
        next(iter(candidate_identities)) if len(candidate_identities) == 1 else None
    )
    if len(candidate_identities) > 1:
        add_finding(
            findings,
            "error",
            "aggregate.provenance_mismatch",
            root,
            "Candidate package identity is inconsistent across evals: "
            + ", ".join(sorted(candidate_identities))
            + ".",
            "Use one exact candidate package identity throughout an iteration.",
        )
        for item in provenance_facts:
            if item["configuration"] == candidate:
                item["valid"] = False
        for run in runs:
            if run["configuration"] == candidate:
                run["complete"] = False
        values.pop(candidate, None)
        assertion_analysis = []
        assertion_summary = {key: 0 for key in assertion_summary}

    run_summary: dict[str, Any] = {}
    for configuration in sorted(values):
        run_summary[configuration] = {
            key: metric(metric_values)
            for key, metric_values in values[configuration].items()
        }

    delta = None
    has_incomplete_runs = any(item.severity == "error" for item in findings)
    if not has_incomplete_runs and candidate in run_summary and baseline in run_summary:
        delta = {
            key: run_summary[candidate][key]["mean"]
            - run_summary[baseline][key]["mean"]
            for key in ("pass_rate", "time_seconds", "tokens")
        }
    elif not has_incomplete_runs:
        add_finding(
            findings,
            "error",
            "aggregate.delta_unavailable",
            root,
            f'Cannot compute delta without complete "{candidate}" and "{baseline}" runs.',
            "Finish or repair the paired configurations and aggregate again.",
        )

    result = finalize(
        "aggregate",
        root,
        {
            "candidate": candidate,
            "baseline": baseline,
            "campaign": {
                "id": plan["campaign_id"] if plan is not None else None,
                "environment_identity": (
                    plan["environment_identity"] if plan is not None else None
                ),
            },
            "coverage": {
                "planned": sorted(planned_directories),
                "discovered": sorted(discovered_directories),
                "matched": sorted(planned_directories & discovered_directories),
            },
            "provenance": provenance_facts,
            "identities": {
                "candidate": candidate_identity,
                "candidate_starting": (
                    plan["candidate_starting_identity"] if plan is not None else None
                ),
                "baseline": (plan["baseline_identity"] if plan is not None else None),
                "environment": (
                    plan["environment_identity"] if plan is not None else None
                ),
            },
            "weighting": "Each complete run has equal weight.",
            "runs": runs,
            "run_summary": run_summary,
            "delta": delta,
            "assertion_summary": assertion_summary,
            "assertion_analysis": assertion_analysis,
            "complete": not any(item.severity == "error" for item in findings),
        },
        findings,
        max_findings,
    )
    return result, 1 if result["summary"]["errors"] else 0
