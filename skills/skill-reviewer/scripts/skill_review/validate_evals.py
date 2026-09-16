"""Validation of evals/evals.json definitions and fixture paths.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .frontmatter import parse_frontmatter
from .fs_safety import (
    TextReadBudget,
    TextReadError,
    is_link_like,
    read_bounded_regular_utf8,
    resolve_package_data_file,
    resolve_within,
    windows_filename_issue,
)
from .report import Finding, add_finding, finalize


def validate_evals(evals_path: Path, max_findings: int) -> tuple[dict[str, Any], int]:
    path, skill_root, path_issue = resolve_package_data_file(evals_path)
    findings: list[Finding] = []
    facts: dict[str, Any] = {
        "skill_name": None,
        "target_skill_name": None,
        "eval_count": 0,
        "assertion_count": 0,
    }
    if path_issue in {"file_symlink", "parent_symlink"}:
        add_finding(
            findings,
            "error",
            "evals.definition_symlink",
            path,
            "The eval definition or one of its package directories is a symbolic link or reparse point and was not inspected.",
            "Use an ordinary evals.json file inside the target skill package.",
        )
        return finalize("validate-evals", path, facts, findings, max_findings), 1
    if path_issue == "missing":
        raise ValueError(f'Evals file must exist; received "{evals_path}".')
    if path_issue == "outside":
        add_finding(
            findings,
            "error",
            "evals.definition_outside_skill",
            path,
            "The eval definition resolves outside the inferred target skill root.",
            "Keep evals.json and its parent directories inside the target skill package.",
        )
        return finalize("validate-evals", path, facts, findings, max_findings), 1

    text_budget = TextReadBudget()
    try:
        data = json.loads(read_bounded_regular_utf8(skill_root, path, text_budget))
    except TextReadError as exc:
        add_finding(
            findings,
            "error",
            exc.code,
            path,
            str(exc),
            "Use an ordinary bounded UTF-8 eval definition inside the target skill package.",
        )
        return finalize("validate-evals", path, facts, findings, max_findings), 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot parse {path} as JSON: {exc}") from exc

    if not isinstance(data, dict):
        add_finding(
            findings,
            "error",
            "evals.root_type",
            path,
            "The eval definition must be a JSON object.",
            "Use an object with skill_name and evals fields.",
        )
        return finalize("validate-evals", path, facts, findings, max_findings), 1

    target_skill_md = skill_root / "SKILL.md"
    target_skill_name = ""
    if is_link_like(target_skill_md):
        add_finding(
            findings,
            "error",
            "evals.target_skill_symlink",
            target_skill_md,
            "The target SKILL.md is a symbolic link or reparse point and was not inspected.",
            "Use an ordinary SKILL.md inside the target skill root.",
        )
    elif not target_skill_md.is_file():
        add_finding(
            findings,
            "error",
            "evals.target_skill_missing",
            target_skill_md,
            "Cannot verify skill_name because the inferred skill root has no SKILL.md.",
            "Place evals/evals.json below the target skill root or provide its SKILL.md.",
        )
    else:
        try:
            target_text = read_bounded_regular_utf8(
                skill_root, target_skill_md, text_budget
            )
            target_frontmatter, _, target_parse_errors = parse_frontmatter(target_text)
        except (OSError, TextReadError, UnicodeError) as exc:
            target_parse_errors = [f"Cannot read target SKILL.md: {exc}"]
            target_frontmatter = {}
        if target_parse_errors:
            add_finding(
                findings,
                "error",
                "evals.target_frontmatter",
                target_skill_md,
                "Cannot verify skill_name against target frontmatter: "
                + " ".join(target_parse_errors),
                "Repair target frontmatter and run the official skill validator.",
            )
        else:
            target_skill_name = target_frontmatter.get("name", "").strip()
            facts["target_skill_name"] = target_skill_name or None
            if not target_skill_name:
                add_finding(
                    findings,
                    "error",
                    "evals.target_name_missing",
                    target_skill_md,
                    "Cannot verify skill_name because target frontmatter has no name.",
                    "Add the required target name and match evals.skill_name to it.",
                )

    skill_name = data.get("skill_name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        add_finding(
            findings,
            "error",
            "evals.skill_name",
            path,
            "skill_name must be a non-empty string.",
            "Set skill_name to the target skill's frontmatter name.",
        )
    else:
        facts["skill_name"] = skill_name
        if target_skill_name and skill_name != target_skill_name:
            add_finding(
                findings,
                "error",
                "evals.skill_name_mismatch",
                path,
                f'skill_name "{skill_name}" does not match target name "{target_skill_name}".',
                "Set skill_name to the name in the target SKILL.md frontmatter.",
            )

    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        add_finding(
            findings,
            "error",
            "evals.list",
            path,
            "evals must be a non-empty array.",
            "Add two or three realistic cases for the first iteration.",
        )
        return finalize("validate-evals", path, facts, findings, max_findings), 1

    facts["eval_count"] = len(evals)
    if len(evals) < 2:
        add_finding(
            findings,
            "warning",
            "evals.too_few_cases",
            path,
            "Only one eval case is defined; an initial set usually needs two or three.",
            "Add a distinct realistic case, including a boundary or ambiguity when useful.",
        )

    seen_ids: set[str] = set()
    for index, case in enumerate(evals):
        label = f"evals[{index}]"
        if not isinstance(case, dict):
            add_finding(
                findings,
                "error",
                "evals.case_type",
                path,
                f"{label} must be an object.",
                "Use id, prompt, expected_output, and optional files/assertions fields.",
            )
            continue
        case_id = case.get("id")
        normalized_id = (
            str(case_id)
            if isinstance(case_id, (str, int)) and not isinstance(case_id, bool)
            else ""
        )
        if not normalized_id:
            add_finding(
                findings,
                "error",
                "evals.id_missing",
                path,
                f"{label}.id must be a non-empty string or integer.",
                "Give every case a stable descriptive identifier.",
            )
        elif normalized_id in seen_ids:
            add_finding(
                findings,
                "error",
                "evals.id_duplicate",
                path,
                f'{label}.id duplicates "{normalized_id}".',
                "Use a unique identifier for every case.",
            )
        else:
            seen_ids.add(normalized_id)

        for field in ("prompt", "expected_output"):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                add_finding(
                    findings,
                    "error",
                    f"evals.{field}",
                    path,
                    f"{label}.{field} must be a non-empty string.",
                    f"Describe a realistic {field.replace('_', ' ')}.",
                )

        files = case.get("files", [])
        if not isinstance(files, list) or any(
            not isinstance(item, str) or not item for item in files
        ):
            add_finding(
                findings,
                "error",
                "evals.files_type",
                path,
                f"{label}.files must be an array of non-empty path strings.",
                "Remove files or list paths relative to the skill root.",
            )
        else:
            for file_value in files:
                fixture = Path(file_value)
                posix_fixture = PurePosixPath(file_value)
                windows_fixture = PureWindowsPath(file_value)
                if (
                    fixture.is_absolute()
                    or posix_fixture.is_absolute()
                    or windows_fixture.is_absolute()
                    or bool(windows_fixture.root)
                ):
                    add_finding(
                        findings,
                        "error",
                        "evals.file_absolute",
                        path,
                        f'{label} uses absolute fixture path "{file_value}".',
                        "Use a fixture path relative to the target skill root.",
                    )
                    continue
                if windows_fixture.drive:
                    add_finding(
                        findings,
                        "error",
                        "evals.file_nonportable",
                        path,
                        f'{label} fixture path "{file_value}" uses a Windows drive prefix.',
                        "Use a portable POSIX-style path relative to the target skill root.",
                    )
                    continue
                if "\\" in file_value:
                    add_finding(
                        findings,
                        "error",
                        "evals.file_nonportable",
                        path,
                        f'{label} fixture path "{file_value}" uses backslash separators.',
                        "Use a portable POSIX-style path relative to the target skill root.",
                    )
                    continue
                if ".." in posix_fixture.parts or ".." in windows_fixture.parts:
                    add_finding(
                        findings,
                        "error",
                        "evals.file_parent_traversal",
                        path,
                        f'{label} fixture path "{file_value}" contains a parent traversal.',
                        "Keep immutable fixtures inside the target skill root.",
                    )
                    continue
                filename_issue = windows_filename_issue(posix_fixture.parts)
                if filename_issue:
                    add_finding(
                        findings,
                        "error",
                        "evals.file_nonportable",
                        path,
                        f'{label} fixture path "{file_value}" is not portable: {filename_issue}.',
                        "Rename the fixture using characters and components valid on Windows.",
                    )
                    continue
                try:
                    resolved = resolve_within(
                        skill_root, skill_root / fixture, strict=False
                    )
                except (OSError, RuntimeError, ValueError):
                    add_finding(
                        findings,
                        "error",
                        "evals.file_outside_skill",
                        path,
                        f'{label} fixture path "{file_value}" resolves outside the target skill root.',
                        "Use a relative fixture that remains inside the target skill root after resolution.",
                    )
                    continue
                if not resolved.is_file():
                    add_finding(
                        findings,
                        "error",
                        "evals.file_missing",
                        path,
                        f'{label} references missing file "{file_value}".',
                        "Correct the path or add the immutable fixture.",
                    )

        assertions = case.get("assertions")
        if assertions is not None:
            if not isinstance(assertions, list) or any(
                not isinstance(item, str) or not item.strip() for item in assertions
            ):
                add_finding(
                    findings,
                    "error",
                    "evals.assertions_type",
                    path,
                    f"{label}.assertions must be an array of non-empty strings.",
                    "Use observable assertions or omit them until first outputs are reviewed.",
                )
            else:
                normalized_assertions = [item.strip() for item in assertions]
                facts["assertion_count"] += len(normalized_assertions)
                if len(set(normalized_assertions)) != len(normalized_assertions):
                    add_finding(
                        findings,
                        "error",
                        "evals.assertion_duplicate",
                        path,
                        f"{label}.assertions contains duplicate text after trimming.",
                        "Keep every assertion within an eval case unique.",
                    )

    result = finalize("validate-evals", path, facts, findings, max_findings)
    return result, 1 if result["summary"]["errors"] else 0
