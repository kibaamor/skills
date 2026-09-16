"""Validation of trigger-query labels and split coverage.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fs_safety import resolve_package_data_file
from .report import Finding, add_finding, finalize

TRIGGER_FIELDS = {"query", "should_trigger", "split", "rationale"}


def validate_triggers(
    triggers_path: Path, max_findings: int
) -> tuple[dict[str, Any], int]:
    path, _, path_issue = resolve_package_data_file(triggers_path)
    findings: list[Finding] = []
    coverage = {
        "train": {"positive": 0, "negative": 0},
        "validation": {"positive": 0, "negative": 0},
    }
    facts: dict[str, Any] = {
        "query_count": 0,
        "unique_query_count": 0,
        "coverage": coverage,
        "split_fractions": {"train": 0.0, "validation": 0.0},
    }
    if path_issue in {"file_symlink", "parent_symlink"}:
        add_finding(
            findings,
            "error",
            "triggers.definition_symlink",
            path,
            "The trigger definition or one of its package directories is a symbolic link or reparse point and was not inspected.",
            "Use an ordinary trigger_queries.json file inside the target skill package.",
        )
        return finalize("validate-triggers", path, facts, findings, max_findings), 1
    if path_issue == "missing":
        raise ValueError(f'Trigger query file must exist; received "{triggers_path}".')
    if path_issue == "outside":
        add_finding(
            findings,
            "error",
            "triggers.definition_outside_skill",
            path,
            "The trigger definition resolves outside the inferred target skill root.",
            "Keep trigger_queries.json and its parent directories inside the target skill package.",
        )
        return finalize("validate-triggers", path, facts, findings, max_findings), 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot parse {path} as JSON: {exc}") from exc

    if not isinstance(data, list):
        add_finding(
            findings,
            "error",
            "triggers.root_type",
            path,
            "The trigger query definition must be a JSON array.",
            "Use an array of query, should_trigger, and split objects.",
        )
        return finalize("validate-triggers", path, facts, findings, max_findings), 1

    facts["query_count"] = len(data)
    seen_queries: set[str] = set()
    for index, case in enumerate(data):
        label = f"queries[{index}]"
        if not isinstance(case, dict):
            add_finding(
                findings,
                "error",
                "triggers.case_type",
                path,
                f"{label} must be an object.",
                "Use query, should_trigger, and split fields for every case.",
            )
            continue

        unknown_fields = sorted(set(case) - TRIGGER_FIELDS)
        if unknown_fields:
            add_finding(
                findings,
                "warning",
                "triggers.unknown_fields",
                path,
                f"{label} has unknown field(s): {', '.join(unknown_fields)}.",
                "Remove misspelled fields or document them in the trigger query contract.",
            )

        query = case.get("query")
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            add_finding(
                findings,
                "error",
                "triggers.query",
                path,
                f"{label}.query must be a non-empty string.",
                "Add a realistic user query.",
            )
        elif normalized_query in seen_queries:
            add_finding(
                findings,
                "error",
                "triggers.query_duplicate",
                path,
                f"{label}.query duplicates an earlier query.",
                "Keep every trigger query unique after trimming whitespace.",
            )
        else:
            seen_queries.add(normalized_query)

        should_trigger = case.get("should_trigger")
        if not isinstance(should_trigger, bool):
            add_finding(
                findings,
                "error",
                "triggers.should_trigger",
                path,
                f"{label}.should_trigger must be a boolean.",
                "Use true for positive queries and false for near misses.",
            )

        split = case.get("split")
        valid_split = isinstance(split, str) and split in coverage
        if not valid_split:
            add_finding(
                findings,
                "error",
                "triggers.split",
                path,
                f'{label}.split must be "train" or "validation".',
                "Assign every query to one fixed split.",
            )

        if isinstance(should_trigger, bool) and valid_split:
            class_name = "positive" if should_trigger else "negative"
            coverage[split][class_name] += 1

        rationale = case.get("rationale")
        if rationale is not None and (
            not isinstance(rationale, str) or not rationale.strip()
        ):
            add_finding(
                findings,
                "error",
                "triggers.rationale",
                path,
                f"{label}.rationale must be a non-empty string when provided.",
                "Explain briefly why the query should or should not trigger.",
            )

    facts["unique_query_count"] = len(seen_queries)
    split_totals = {
        split: sum(class_counts.values()) for split, class_counts in coverage.items()
    }
    classified_query_count = sum(split_totals.values())
    if classified_query_count:
        facts["split_fractions"] = {
            split: count / classified_query_count
            for split, count in split_totals.items()
        }
        validation_fraction = facts["split_fractions"]["validation"]
        if not 0.3 <= validation_fraction <= 0.5:
            add_finding(
                findings,
                "warning",
                "triggers.split_imbalance",
                path,
                (
                    "Validation contains "
                    f"{validation_fraction:.1%} of classified trigger queries; "
                    "the recommended range is 30%-50%."
                ),
                "Move fixed queries between splits while preserving both labels in each split.",
            )
    for split, class_counts in coverage.items():
        for class_name, count in class_counts.items():
            if count == 0:
                add_finding(
                    findings,
                    "error",
                    "triggers.coverage",
                    path,
                    f'The "{split}" split has no {class_name} trigger queries.',
                    "Include both positive and negative queries in each split.",
                )

    result = finalize("validate-triggers", path, facts, findings, max_findings)
    return result, 1 if result["summary"]["errors"] else 0
