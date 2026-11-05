#!/usr/bin/env python3
"""Verify that the exact prompt argument captured from a child dispatch matches its rendered role template."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
ROOT_OUTPUT_KEYS = {
    "discovery": ["schema_version", "reviewer_id", "review_status", "spec_compliance", "findings", "recommendations", "checks", "checks_not_run", "limitations"],
    "verification": ["schema_version", "review_status", "finding_assessments", "recommendation_assessments", "checks", "checks_not_run", "limitations"]
}
NESTED_OUTPUT_KEYS = {
    "discovery": ["local_id", "kind", "location", "evidence", "trigger", "impact", "severity"],
    "verification": ["candidate_id", "verdict", "rationale", "evidence"]
}

def collect_keys(value):
    keys = set()
    if isinstance(value, dict):
        keys.update(value.keys())
        for child in value.values(): keys.update(collect_keys(child))
    elif isinstance(value, list):
        for child in value: keys.update(collect_keys(child))
    return keys
HEADINGS = {
    "discovery": [
        "# Discovery Review", "## Task", "## Review target and intended behavior",
        "## Baseline change package", "## Binding requirements and project constraints",
        "## Relevant technical context", "## Task-specific review focus", "## Review approach",
        "## Executable validation", "## Reportable result categories", "## Output format"
    ],
    "verification": [
        "# Candidate Verification", "## Task", "## Review target and binding requirements",
        "## Baseline change package", "## Candidate Findings — unproven claims",
        "## Candidate Recommendations — unproven proposals", "## Relevant technical context and task-specific checks",
        "## Existing validation evidence", "## How to verify Findings", "## How to assess Recommendations",
        "## Executable validation boundary", "## Output format"
    ]
}

def read_utf8(path: Path) -> str:
    return path.read_bytes().decode("utf-8")

def render(template: str, values: dict[str, str]) -> str:
    needed = set(TOKEN.findall(template))
    missing = sorted(needed - values.keys())
    if missing:
        raise ValueError("missing placeholders: " + ", ".join(missing))
    result = TOKEN.sub(lambda m: values[m.group(1)], template)
    left = sorted(set(TOKEN.findall(result)))
    if left:
        raise ValueError("unresolved placeholders: " + ", ".join(left))
    return result

def first_difference(expected: str, actual: str) -> dict:
    a, b = expected.splitlines(keepends=True), actual.splitlines(keepends=True)
    for i, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return {"line": i, "expected": x[:240], "actual": y[:240]}
    if len(a) != len(b):
        i = min(len(a), len(b)) + 1
        return {"line": i, "expected": a[i-1][:240] if len(a) >= i else "<EOF>", "actual": b[i-1][:240] if len(b) >= i else "<EOF>"}
    return {"line": None, "expected": "", "actual": ""}

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role", required=True, choices=sorted(HEADINGS))
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--values", required=True, type=Path)
    ap.add_argument("--actual-prompt", required=True, type=Path, help="Exact prompt argument captured from the actual child dispatch")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    errors = []
    expected_basename = "discovery-reviewer.md" if args.role == "discovery" else "verification-reviewer.md"
    if args.template.name != expected_basename:
        errors.append(f"role/template mismatch: {args.role} requires {expected_basename}")
    try:
        template = read_utf8(args.template)
        values = json.loads(read_utf8(args.values))
        if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
            raise ValueError("values must be a JSON object with string keys and string values")
        expected = render(template, values)
        actual = read_utf8(args.actual_prompt)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))
        expected = actual = ""
    if expected and actual != expected:
        diff = first_difference(expected, actual)
        errors.append("actual dispatch prompt differs from the rendered template (byte-for-byte comparison failed)")
    else:
        diff = None
    if actual:
        lines = actual.splitlines()
        positions = []
        for heading in HEADINGS[args.role]:
            if heading not in lines:
                errors.append(f"required heading missing: {heading}")
            else:
                positions.append(lines.index(heading))
        if positions != sorted(positions):
            errors.append("required headings are out of template order")
        if TOKEN.search(actual):
            errors.append("unresolved template placeholder remains in actual prompt")
        blocks = re.findall(r"```json\s*(.*?)```", actual, flags=re.DOTALL)
        if not blocks:
            errors.append("role-specific JSON output example is missing")
        else:
            try:
                example = json.loads(blocks[-1])
                if not isinstance(example, dict):
                    errors.append("JSON output example root must be an object")
                else:
                    for key in ROOT_OUTPUT_KEYS[args.role]:
                        if key not in example:
                            errors.append(f"JSON output example missing required root field: {key}")
                    all_keys = collect_keys(example)
                    for key in NESTED_OUTPUT_KEYS[args.role]:
                        if key not in all_keys:
                            errors.append(f"JSON output example missing required nested field: {key}")
                    if example.get("schema_version") != "2.1":
                        errors.append("JSON output example schema_version must be 2.1")
            except json.JSONDecodeError as exc:
                errors.append(f"JSON output example is malformed: {exc}")
        if not actual.endswith("\n"):
            errors.append("actual prompt does not preserve the template's final newline")
    result = {
        "valid": not errors,
        "role": args.role,
        "template": str(args.template),
        "actual_prompt": str(args.actual_prompt),
        "expected_sha256": hashlib.sha256(expected.encode("utf-8")).hexdigest() if expected else None,
        "actual_sha256": hashlib.sha256(actual.encode("utf-8")).hexdigest() if actual else None,
        "first_difference": diff,
        "errors": errors
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
