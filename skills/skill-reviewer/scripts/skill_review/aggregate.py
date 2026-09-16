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


def parse_run(
    root: Path, config_dir: Path, text_budget: TextReadBudget
) -> dict[str, Any]:
    grading_path = config_dir / "grading.json"
    timing_path = config_dir / "timing.json"
    redirected = [
        path.name
        for path in (grading_path, timing_path)
        if first_link_like_component(root, path) is not None
    ]
    if redirected:
        raise ValueError(
            f"{', '.join(redirected)} must not be symbolic links or reparse points"
        )
    missing = [path.name for path in (grading_path, timing_path) if not path.is_file()]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    try:
        for path in (grading_path, timing_path):
            resolve_within(root, path, strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("run data must resolve inside the iteration root") from exc
    try:
        grading = json.loads(
            read_bounded_regular_utf8(root, grading_path, text_budget)
        )
        timing = json.loads(
            read_bounded_regular_utf8(root, timing_path, text_budget)
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(grading, dict):
        raise ValueError("grading.json must be an object")
    if not isinstance(timing, dict):
        raise ValueError("timing.json must be an object")

    assertion_results = grading.get("assertion_results")
    if not isinstance(assertion_results, list) or not assertion_results:
        raise ValueError("grading.json must contain a non-empty assertion_results array")
    passed = 0
    assertion_texts: set[str] = set()
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
        if not isinstance(assertion.get("evidence"), str) or not assertion[
            "evidence"
        ].strip():
            raise ValueError(f"{label}.evidence must be a non-empty string")
        passed += int(assertion["passed"])

    summary = grading.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("grading.json must contain a summary object")
    total = len(assertion_results)
    expected_counts = {"passed": passed, "failed": total - passed, "total": total}
    for key, expected in expected_counts.items():
        actual = summary.get(key)
        if isinstance(actual, bool) or not isinstance(actual, int) or actual != expected:
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
    if not candidate or not baseline or candidate == baseline:
        raise ValueError("Candidate and baseline must be distinct non-empty directory names.")

    findings: list[Finding] = []
    text_budget = TextReadBudget()
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"pass_rate": [], "time_seconds": [], "tokens": []}
    )
    runs: list[dict[str, Any]] = []
    eval_dirs = sorted(
        path
        for path in root.glob("eval-*")
        if is_link_like(path) or path.is_dir()
    )
    if not eval_dirs:
        raise ValueError(f"No eval-* directories were found under {root}.")

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
                    "Add valid grading.json and timing.json; do not silently drop the run.",
                )
                runs.append(
                    {
                        "eval": eval_dir.name,
                        "configuration": config_dir.name,
                        "complete": False,
                    }
                )
                continue
            parsed_configs[config_dir.name] = parsed
            metrics = {
                key: parsed[key] for key in ("pass_rate", "time_seconds", "tokens")
            }
            for key, value in metrics.items():
                values[config_dir.name][key].append(value)
            runs.append(
                {
                    "eval": eval_dir.name,
                    "configuration": config_dir.name,
                    "complete": True,
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
            "weighting": "Each complete run has equal weight.",
            "runs": runs,
            "run_summary": run_summary,
            "delta": delta,
            "complete": not any(item.severity == "error" for item in findings),
        },
        findings,
        max_findings,
    )
    return result, 1 if result["summary"]["errors"] else 0
