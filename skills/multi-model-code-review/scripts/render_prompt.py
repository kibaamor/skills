#!/usr/bin/env python3
"""Render a Markdown reviewer prompt with literal {{UPPERCASE_TOKEN}} replacement."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

def render(template: str, values: dict[str, str]) -> str:
    required = set(TOKEN.findall(template))
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError("missing placeholders: " + ", ".join(missing))
    result = TOKEN.sub(lambda m: values[m.group(1)], template)
    unresolved = sorted(set(TOKEN.findall(result)))
    if unresolved:
        raise ValueError("unresolved placeholders: " + ", ".join(unresolved))
    return result

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--values", required=True, type=Path, help="UTF-8 JSON object mapping placeholder names to strings")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    try:
        template = args.template.read_bytes().decode("utf-8")
        values = json.loads(args.values.read_bytes().decode("utf-8"))
        if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
            raise ValueError("values must be a JSON object with string keys and string values")
        result = render(template, values)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(result.encode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"valid": True, "output": str(args.output), "characters": len(result)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
