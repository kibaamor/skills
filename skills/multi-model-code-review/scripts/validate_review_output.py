#!/usr/bin/env python3
"""Validate raw Discovery/Verification JSON against the bundled schema and semantic coverage rules.

The bundled schemas intentionally use a constrained JSON Schema subset validated here with
Python's standard library: type, required, properties, items, enum, const, pattern,
minLength, minItems, and additionalProperties.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

class DuplicateKeyError(ValueError):
    pass

def reject_nonstandard_constant(token):
    raise ValueError(f"non-standard JSON constant is not allowed: {token}")

def no_duplicate_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateKeyError(f"duplicate JSON object key: {key}")
        obj[key] = value
    return obj

def json_type(value):
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, str): return "string"
    if isinstance(value, list): return "array"
    if isinstance(value, dict): return "object"
    return "unknown"

def validate_schema(value, schema, path="$", errors=None):
    if errors is None: errors = []
    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        actual = json_type(value)
        compatible = actual in types or (actual == "integer" and "number" in types)
        if not compatible:
            errors.append(f"{path}: expected type {types}, got {actual}")
            return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in allowed enum {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): errors.append(f"{path}: string shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value): errors.append(f"{path}: string does not match pattern {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): errors.append(f"{path}: array shorter than minItems")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value): validate_schema(item, item_schema, f"{path}[{i}]", errors)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value: errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties: errors.append(f"{path}: unexpected property {key!r}")
        for key, child_schema in properties.items():
            if key in value: validate_schema(value[key], child_schema, f"{path}.{key}", errors)
    return errors

def semantic_checks(data, role, expected):
    errors = []
    if role == "discovery":
        for array_name, prefix in (("findings", "F-"), ("recommendations", "R-")):
            seen = set()
            for i, item in enumerate(data.get(array_name, [])):
                local_id = item.get("local_id")
                if local_id in seen: errors.append(f"$.{array_name}[{i}].local_id: duplicate local ID {local_id}")
                seen.add(local_id)
                if not isinstance(local_id, str) or not local_id.startswith(prefix):
                    errors.append(f"$.{array_name}[{i}].local_id: expected prefix {prefix}")
        check_ids = [x.get("check_id") for x in data.get("checks", [])]
        if len(check_ids) != len(set(check_ids)): errors.append("$.checks: duplicate check_id")
        for i, item in enumerate(data.get("checks", [])):
            status, code = item.get("status"), item.get("exit_code")
            if status == "passed" and code != 0: errors.append(f"$.checks[{i}]: passed requires exit_code 0")
            if status == "failed" and (not isinstance(code, int) or code == 0): errors.append(f"$.checks[{i}]: failed requires a non-zero integer exit_code")
    else:
        if expected is None:
            errors.append("Verification validation requires --expected-candidates")
            expected = {"findings": [], "recommendations": []}
        for array_name, expected_key, prefix in (("finding_assessments", "findings", "C-F-"), ("recommendation_assessments", "recommendations", "C-R-")):
            items = data.get(array_name, [])
            ids = [x.get("candidate_id") for x in items]
            if len(ids) != len(set(ids)):
                duplicates = sorted({x for x in ids if ids.count(x) > 1})
                errors.append(f"$.{array_name}: duplicate candidate IDs {duplicates}")
            want = expected.get(expected_key, [])
            got = set(ids)
            missing, unexpected = sorted(set(want) - got), sorted(got - set(want))
            if missing: errors.append(f"$.{array_name}: missing candidate IDs {missing}")
            if unexpected: errors.append(f"$.{array_name}: unexpected candidate IDs {unexpected}")
            for i, item in enumerate(items):
                verdict = item.get("verdict")
                evidence = item.get("evidence", [])
                rationale = item.get("rationale", "")
                if verdict in ("confirmed", "rejected") and not evidence:
                    errors.append(f"$.{array_name}[{i}]: {verdict} requires evidence")
                if not rationale.strip():
                    errors.append(f"$.{array_name}[{i}]: rationale must be non-empty")
        if set(expected.get("findings", [])) & set(expected.get("recommendations", [])):
            errors.append("expected-candidates manifest contains IDs in both categories")
        check_ids = [x.get("check_id") for x in data.get("checks", [])]
        if len(check_ids) != len(set(check_ids)): errors.append("$.checks: duplicate check_id")
        for i, item in enumerate(data.get("checks", [])):
            status, code = item.get("status"), item.get("exit_code")
            if status == "passed" and code != 0: errors.append(f"$.checks[{i}]: passed requires exit_code 0")
            if status == "failed" and (not isinstance(code, int) or code == 0): errors.append(f"$.checks[{i}]: failed requires non-zero exit_code")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role", required=True, choices=["discovery", "verification"])
    ap.add_argument("--schema", required=True, type=Path)
    ap.add_argument("--input", required=True, type=Path, help="Raw JSON response from the child")
    ap.add_argument("--expected-candidates", type=Path, help="JSON: {\"findings\":[...],\"recommendations\":[...]}; required for Verification")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    errors = []
    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        raw = args.input.read_text(encoding="utf-8")
        data = json.loads(raw, object_pairs_hook=no_duplicate_pairs, parse_constant=reject_nonstandard_constant)
        if not isinstance(data, dict):
            result = {"valid": False, "role": args.role, "errors": ["root JSON value must be an object"]}
            output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(output, encoding="utf-8")
            print(output, end="")
            return 1
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        result = {"valid": False, "role": args.role, "errors": [f"JSON input/schema error: {exc}"]}
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output, encoding="utf-8")
        print(output, end=""); return 1
    errors.extend(validate_schema(data, schema))
    expected = None
    if args.expected_candidates:
        try:
            expected = json.loads(args.expected_candidates.read_text(encoding="utf-8"))
            if not isinstance(expected, dict):
                errors.append("expected-candidates manifest root must be an object")
                expected = None
            else:
                for key in ("findings", "recommendations"):
                    if not isinstance(expected.get(key, []), list) or any(not isinstance(x, str) for x in expected.get(key, [])):
                        errors.append(f"expected-candidates.{key} must be an array of strings")
                        expected = None
                        break
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read expected-candidates manifest: {exc}")
    expected_schema = "discovery-result" if args.role == "discovery" else "verification-result"
    if expected_schema not in str(schema.get("$id", "")):
        errors.append(f"role/schema mismatch: {args.role} requires schema ID containing {expected_schema!r}")
    errors.extend(semantic_checks(data, args.role, expected))
    result = {"valid": not errors, "role": args.role, "schema_version": schema.get("$id"),
              "findings_or_assessments": len(data.get("findings", data.get("finding_assessments", []))),
              "recommendations_or_assessments": len(data.get("recommendations", data.get("recommendation_assessments", []))),
              "checks": len(data.get("checks", [])), "errors": errors}
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
