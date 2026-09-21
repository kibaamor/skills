"""Findings, evidence line lookup, and deterministic report rendering.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int | None
    message: str
    suggestion: str


def add_finding(
    findings: list[Finding],
    severity: str,
    code: str,
    path: Path | str,
    message: str,
    suggestion: str,
    line: int | None = None,
) -> None:
    findings.append(Finding(severity, code, str(path), line, message, suggestion))


def line_number(text: str, needle: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def finalize(
    operation: str,
    subject: Path,
    facts: dict[str, Any],
    findings: Iterable[Finding],
    max_findings: int,
) -> dict[str, Any]:
    ordered = sorted(
        findings,
        key=lambda item: (
            {"error": 0, "warning": 1, "info": 2}.get(item.severity, 3),
            item.path,
            item.line or 0,
            item.code,
        ),
    )
    counts = Counter(item.severity for item in ordered)
    visible = ordered[:max_findings]
    return {
        "tool": "skill-reviewer/review_skill.py",
        "operation": operation,
        "subject": str(subject),
        "summary": {
            "errors": counts["error"],
            "warnings": counts["warning"],
            "info": counts["info"],
            "total": len(ordered),
            "returned": len(visible),
            "truncated": len(visible) < len(ordered),
        },
        "facts": facts,
        "findings": [asdict(item) for item in visible],
    }


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"{result['operation']}: {result['subject']}",
        (
            f"errors={summary['errors']} warnings={summary['warnings']} "
            f"info={summary['info']} total={summary['total']}"
        ),
    ]
    if result["operation"] == "aggregate":
        facts = result["facts"]
        metrics = {
            "candidate": facts["candidate"],
            "baseline": facts["baseline"],
            "run_summary": facts["run_summary"],
            "delta": facts["delta"],
            "assertion_summary": facts["assertion_summary"],
            "complete": facts["complete"],
        }
        lines.append(
            "metrics="
            + json.dumps(metrics, ensure_ascii=False, separators=(",", ":"))
        )
    for finding in result["findings"]:
        location = finding["path"]
        if finding["line"] is not None:
            location += f":{finding['line']}"
        lines.append(
            f"[{finding['severity'].upper()}] {finding['code']} {location}: "
            f"{finding['message']} Suggestion: {finding['suggestion']}"
        )
    if summary["truncated"]:
        lines.append("Findings were truncated; raise --max-findings to inspect more.")
    return "\n".join(lines)
