"""Tolerant YAML frontmatter extraction for SKILL.md files.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import json
import re

TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")


def decode_scalar(value: str, continuation: list[str]) -> str:
    value = value.strip()
    if value in {">", ">-", ">+", "|", "|-", "|+"}:
        pieces = [line.strip() for line in continuation]
        separator = "\n" if value.startswith("|") else " "
        return separator.join(piece for piece in pieces if piece).strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, str) else value
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def has_unbalanced_flow_delimiters(value: str) -> bool:
    """Catch truncated YAML flow collections without pretending to parse YAML."""
    stripped = value.strip()
    if stripped.startswith(("'", '"')):
        return len(stripped) < 2 or not stripped.endswith(stripped[0])
    stack: list[str] = []
    pairs = {"]": "[", "}": "{"}
    for character in value:
        if character in "[{":
            stack.append(character)
        elif character in "]}":
            if not stack or stack.pop() != pairs[character]:
                return True
    return bool(stack)


def parse_frontmatter(text: str) -> tuple[dict[str, str], int, list[str]]:
    lines = text.splitlines()
    errors: list[str] = []
    if not lines or lines[0].strip() != "---":
        return {}, 0, ["SKILL.md must begin with a YAML frontmatter delimiter (---)."]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, 0, ["SKILL.md has no closing YAML frontmatter delimiter (---)."]

    raw = lines[1:end]
    parsed: dict[str, str] = {}
    i = 0
    while i < len(raw):
        current = raw[i]
        match = TOP_KEY_RE.match(current)
        if not match:
            if (
                current.strip()
                and not current[:1].isspace()
                and not current.lstrip().startswith("#")
            ):
                errors.append(
                    f"Unsupported or malformed top-level frontmatter at line {i + 2}."
                )
            i += 1
            continue
        key, value = match.group(1), match.group(2) or ""
        if has_unbalanced_flow_delimiters(value):
            errors.append(
                f"Unbalanced flow collection or quote in frontmatter at line {i + 2}."
            )
        continuation: list[str] = []
        j = i + 1
        if value.strip() in {">", ">-", ">+", "|", "|-", "|+"}:
            while j < len(raw) and (
                raw[j].startswith((" ", "\t")) or not raw[j].strip()
            ):
                continuation.append(raw[j])
                j += 1
        parsed[key] = decode_scalar(value, continuation)
        i = j if j > i + 1 else i + 1
    return parsed, end + 1, errors
