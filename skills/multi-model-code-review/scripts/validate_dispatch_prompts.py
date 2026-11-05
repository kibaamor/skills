#!/usr/bin/env python3
"""Validate every captured Reviewer prompt argument in a dispatch audit manifest."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ALLOWED_CAPTURE_METHODS = {"dispatch_argument_capture", "exact_argument_variable"}

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, type=Path, help="Dispatch audit JSON manifest")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    base = args.manifest.resolve().parent
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    errors, records = [], []
    expected_discovery = manifest.get("expected_discovery_reviewers", [])
    verification_expected = bool(manifest.get("verification_expected", False))
    if not isinstance(expected_discovery, list) or not expected_discovery:
        errors.append("expected_discovery_reviewers must be a non-empty array")
        expected_discovery = []
    expected_ids = set(expected_discovery)
    if len(expected_ids) != len(expected_discovery):
        errors.append("expected_discovery_reviewers contains duplicates")
    dispatches = manifest.get("dispatches", [])
    if not isinstance(dispatches, list):
        errors.append("dispatches must be an array")
        dispatches = []
    seen_ids, seen_dispatch_ids = set(), set()
    for index, item in enumerate(dispatches):
        label = f"dispatches[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        reviewer_id, role = item.get("reviewer_id"), item.get("role")
        if not isinstance(reviewer_id, str) or not reviewer_id:
            errors.append(f"{label}: reviewer_id is required")
            continue
        if reviewer_id in seen_ids:
            errors.append(f"{label}: duplicate reviewer_id {reviewer_id}")
        seen_ids.add(reviewer_id)
        if role not in ("discovery", "verification"):
            errors.append(f"{label}: role must be discovery or verification")
            continue
        if not isinstance(item.get("model_route"), str) or not item["model_route"].strip():
            errors.append(f"{label}: exact model_route is required")
        dispatch_id = item.get("dispatch_id")
        if not isinstance(dispatch_id, str) or not dispatch_id.strip():
            errors.append(f"{label}: dispatch_id is required to tie prompt capture to a child dispatch")
        elif dispatch_id in seen_dispatch_ids:
            errors.append(f"{label}: duplicate dispatch_id {dispatch_id}")
        else:
            seen_dispatch_ids.add(dispatch_id)
        if item.get("capture_method") not in ALLOWED_CAPTURE_METHODS:
            errors.append(f"{label}: capture_method must prove the actual argument (dispatch_argument_capture or exact_argument_variable)")
        expected_template = "discovery-reviewer.md" if role == "discovery" else "verification-reviewer.md"
        template = item.get("template_path")
        if not isinstance(template, str) or Path(template).name != expected_template:
            errors.append(f"{label}: {role} must use {expected_template}")
        paths = {}
        for key in ("template_path", "values_path", "prompt_argument_path"):
            val = item.get(key)
            if not isinstance(val, str) or not val:
                errors.append(f"{label}: {key} is required")
                paths[key] = None
            else:
                p = Path(val)
                paths[key] = p if p.is_absolute() else (base / p).resolve()
                if not paths[key].is_file():
                    errors.append(f"{label}: {key} file not found: {paths[key]}")
        child_evidence = item.get("fresh_context_evidence")
        if not isinstance(child_evidence, str) or not child_evidence.strip():
            errors.append(f"{label}: fresh_context_evidence is required")
        if all(paths.get(k) and paths[k].is_file() for k in paths):
            cmd = [sys.executable, str(Path(__file__).with_name("validate_prompt.py")),
                   "--role", role, "--template", str(paths["template_path"]),
                   "--values", str(paths["values_path"]), "--actual-prompt", str(paths["prompt_argument_path"])]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            try:
                prompt_report = json.loads(proc.stdout)
            except json.JSONDecodeError:
                prompt_report = {"valid": False, "errors": [proc.stderr or proc.stdout or "validator returned no JSON"]}
            if proc.returncode != 0:
                errors.extend(f"{label}: {message}" for message in prompt_report.get("errors", ["prompt validation failed"]))
            records.append({"reviewer_id": reviewer_id, "role": role, "model_route": item.get("model_route"),
                            "dispatch_id": dispatch_id, "prompt_validation": prompt_report})
    discovery_seen = {r.get("reviewer_id") for r in dispatches if isinstance(r, dict) and r.get("role") == "discovery"}
    for missing in sorted(expected_ids - discovery_seen):
        errors.append(f"missing Discovery dispatch: {missing}")
    for extra in sorted(discovery_seen - expected_ids):
        errors.append(f"unexpected Discovery dispatch: {extra}")
    verification_seen = [r for r in dispatches if isinstance(r, dict) and r.get("role") == "verification"]
    if verification_expected and len(verification_seen) != 1:
        errors.append(f"expected exactly one Verification dispatch, found {len(verification_seen)}")
    if not verification_expected and verification_seen:
        errors.append("Verification dispatch exists although verification_expected is false")
    result = {"valid": not errors, "expected_discovery_reviewers": expected_discovery,
              "verification_expected": verification_expected, "validated_dispatches": records, "errors": errors}
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
