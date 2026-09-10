#!/usr/bin/env python3
"""Deterministic helpers for reviewing Agent Skills.

The tool never executes code from the target skill. Data is written to stdout;
fatal diagnostics are written to stderr.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
RESOURCE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:scripts|references|assets|evals)/"
    r"[A-Za-z0-9_./-]+(?:\.[A-Za-z0-9_-]+)?)"
)
INTERACTIVE_PATTERNS = (
    (re.compile(r"\binput\s*\("), "Python input() call"),
    (re.compile(r"\bgetpass(?:\.getpass)?\s*\("), "password prompt"),
    (re.compile(r"\bread\s+-[A-Za-z]*p\b"), "shell read -p prompt"),
    (re.compile(r"\bselect\s+\w+\s+in\b"), "shell select prompt"),
)
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".rb"}
EXIT_CODES = (
    "Exit codes: 0 completed without error findings; 1 completed with error "
    "findings; 2 invalid arguments, paths, input, or output."
)


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


def outside_fenced_code(text: str) -> str:
    """Return text outside Markdown fences while preserving line numbers."""
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        marker = match.group(1) if match else ""
        if fence_character is None and marker:
            fence_character = marker[0]
            fence_length = len(marker)
            output.append("")
            continue
        if (
            fence_character is not None
            and marker
            and marker[0] == fence_character
            and len(marker) >= fence_length
        ):
            fence_character = None
            fence_length = 0
            output.append("")
            continue
        output.append(line if fence_character is None else "")
    return "\n".join(output)


def extract_paths(text: str) -> dict[str, bool]:
    """Map resource paths to whether a real Markdown pointer requires them."""
    paths = {path: False for path in RESOURCE_PATH_RE.findall(text)}
    for raw_target in MARKDOWN_LINK_RE.findall(outside_fenced_code(text)):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        target = target.split("#", 1)[0]
        if target and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            paths[target] = True
    return paths


def iter_files(root: Path, directory: str) -> list[Path]:
    base = root / directory
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def first_actionable_match(text: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """Ignore regex declarations that quote the warning pattern itself."""
    for match in pattern.finditer(text):
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.end())
        line = text[start:] if end == -1 else text[start:end]
        if "re.compile" not in line:
            return match
    return None


def static_review(target: Path, max_findings: int) -> tuple[dict[str, Any], int]:
    root = target.resolve()
    findings: list[Finding] = []
    facts: dict[str, Any] = {
        "skill_name": None,
        "description_characters": 0,
        "skill_md_lines": 0,
        "resource_files": {},
    }

    if not root.is_dir():
        raise ValueError(
            f'Target must be an existing skill directory; received "{target}".'
        )

    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        add_finding(
            findings,
            "error",
            "structure.skill_md_missing",
            skill_md,
            "The target directory has no SKILL.md.",
            "Point to the skill directory or add the required SKILL.md.",
        )
        return finalize("static", root, facts, findings, max_findings), 1

    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Cannot read {skill_md}: {exc}") from exc

    facts["skill_md_lines"] = len(text.splitlines())
    frontmatter, body_start, parse_errors = parse_frontmatter(text)
    for error in parse_errors:
        add_finding(
            findings,
            "error",
            "frontmatter.malformed",
            skill_md,
            error,
            "Repair the YAML frontmatter before reviewing behavior.",
        )

    name = frontmatter.get("name", "").strip()
    description = frontmatter.get("description", "").strip()
    facts["skill_name"] = name or None
    facts["description_characters"] = len(description)

    if not name:
        add_finding(
            findings,
            "error",
            "frontmatter.name_missing",
            skill_md,
            "Required frontmatter field 'name' is missing or empty.",
            "Add a concise lowercase hyphen-case name.",
        )
    else:
        name_line = line_number(text, "name:")
        if len(name) > 64:
            add_finding(
                findings,
                "error",
                "frontmatter.name_too_long",
                skill_md,
                f"The name has {len(name)} characters; the maximum is 64.",
                "Shorten the name without losing its discovery intent.",
                name_line,
            )
        if not NAME_RE.fullmatch(name):
            add_finding(
                findings,
                "error",
                "frontmatter.name_invalid",
                skill_md,
                f'Name "{name}" is not lowercase hyphen-case.',
                "Use lowercase letters, digits, and single hyphens between terms.",
                name_line,
            )
        if root.name != name:
            add_finding(
                findings,
                "error",
                "structure.folder_name_mismatch",
                skill_md,
                f'Folder "{root.name}" does not match frontmatter name "{name}".',
                "Rename the folder or frontmatter so they match.",
                name_line,
            )

    description_line = line_number(text, "description:")
    if not description:
        add_finding(
            findings,
            "error",
            "frontmatter.description_missing",
            skill_md,
            "Required frontmatter field 'description' is missing or empty.",
            "Describe the user intent that should invoke this skill.",
        )
    else:
        if len(description) > 1024:
            add_finding(
                findings,
                "error",
                "frontmatter.description_too_long",
                skill_md,
                f"The description has {len(description)} characters; the maximum is 1,024.",
                "Compress it to distinct trigger intents and adjacent-task boundaries.",
                description_line,
            )
        if "TODO" in description or "[TODO" in description:
            add_finding(
                findings,
                "error",
                "frontmatter.description_placeholder",
                skill_md,
                "The description still contains scaffold placeholder text.",
                "Replace the placeholder with an intent-focused trigger description.",
                description_line,
            )
        if not re.match(r"^Use\b", description, re.IGNORECASE):
            add_finding(
                findings,
                "warning",
                "description.imperative_not_detected",
                skill_md,
                "The description does not start with an imperative 'Use ...' trigger.",
                "Review whether imperative, intent-focused phrasing would route more reliably.",
                description_line,
            )

    body = "\n".join(text.splitlines()[body_start:]).strip() if body_start else ""
    if not body:
        add_finding(
            findings,
            "error",
            "body.empty",
            skill_md,
            "SKILL.md has no instruction body after frontmatter.",
            "Add only the workflow, constraints, and routing needed when invoked.",
        )
    if "[TODO" in body or re.search(r"\bTODO\b", body):
        add_finding(
            findings,
            "error",
            "body.placeholder",
            skill_md,
            "The instruction body contains unfinished TODO text.",
            "Complete or remove scaffold placeholders.",
            line_number(text, "TODO"),
        )
    if facts["skill_md_lines"] > 500:
        add_finding(
            findings,
            "warning",
            "context.skill_md_over_500_lines",
            skill_md,
            f"SKILL.md has {facts['skill_md_lines']} lines; 500 is the progressive-disclosure guideline.",
            "Check whether branch-specific detail belongs behind conditioned references.",
        )

    all_resource_files: dict[str, list[Path]] = {}
    for directory in ("references", "scripts", "assets", "evals"):
        files = iter_files(root, directory)
        all_resource_files[directory] = files
        facts["resource_files"][directory] = len(files)

    instruction_files = [skill_md] + [
        path
        for path in all_resource_files["references"]
        if path.suffix.lower() in {".md", ".txt"}
    ]
    file_texts: dict[Path, str] = {skill_md: text}
    for path in instruction_files[1:]:
        try:
            file_texts[path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add_finding(
                findings,
                "warning",
                "reference.unreadable",
                path,
                f"The instruction-bearing resource could not be read as UTF-8: {exc}",
                "Use a readable text format or document why the binary resource is needed.",
            )

    mentioned: set[Path] = set()
    reachable_references: set[Path] = set()
    queue: deque[Path] = deque([skill_md])
    visited: set[Path] = set()
    while queue:
        source = queue.popleft()
        if source in visited or source not in file_texts:
            continue
        visited.add(source)
        source_text = file_texts[source]
        for raw, required_pointer in extract_paths(source_text).items():
            raw_path = raw.split("#", 1)[0]
            if not raw_path:
                continue
            if raw_path.startswith(("scripts/", "references/", "assets/", "evals/")):
                resolved = (root / raw_path).resolve()
            else:
                resolved = (source.parent / raw_path).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            mentioned.add(resolved)
            if not resolved.exists() and required_pointer:
                add_finding(
                    findings,
                    "error",
                    "pointer.target_missing",
                    source,
                    f'Referenced path "{raw_path}" does not exist.',
                    "Correct the pointer or add the required resource.",
                    line_number(source_text, raw_path),
                )
            elif resolved.exists() and resolved in file_texts and resolved not in visited:
                reachable_references.add(resolved)
                queue.append(resolved)

    for path in all_resource_files["references"]:
        if path not in reachable_references and path not in mentioned:
            add_finding(
                findings,
                "warning",
                "reference.orphaned",
                path,
                "This reference is not reachable from SKILL.md through a Markdown pointer.",
                "Add a conditioned pointer or remove the unused resource.",
            )

    for path in all_resource_files["scripts"]:
        relative = path.relative_to(root)
        if path.resolve() not in mentioned:
            add_finding(
                findings,
                "warning",
                "script.unreferenced",
                path,
                "This script is not named by SKILL.md or a reachable reference.",
                "Document when to run it or remove it if it has no caller.",
            )
        if path.suffix.lower() not in SCRIPT_SUFFIXES:
            continue
        try:
            script_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if "--help" not in script_text and "argparse" not in script_text:
            add_finding(
                findings,
                "warning",
                "script.help_not_detected",
                path,
                f"No --help interface was detected for {relative}.",
                "If this is an agent-facing CLI, provide concise non-interactive help.",
            )
        for pattern, label in INTERACTIVE_PATTERNS:
            match = first_actionable_match(script_text, pattern)
            if match:
                add_finding(
                    findings,
                    "warning",
                    "script.interactive_pattern",
                    path,
                    f"Detected a possible {label}; agent shells are non-interactive.",
                    "Inspect the code and replace true prompts with flags, environment, or stdin.",
                    script_text.count("\n", 0, match.start()) + 1,
                )

    openai_yaml = root / "agents" / "openai.yaml"
    if openai_yaml.is_file() and name:
        try:
            openai_text = openai_yaml.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            openai_text = ""
        default_prompt_match = re.search(
            r"^\s*default_prompt:\s*['\"]?(.*?)['\"]?\s*$",
            openai_text,
            re.MULTILINE,
        )
        if default_prompt_match and f"${name}" not in default_prompt_match.group(1):
            add_finding(
                findings,
                "error",
                "metadata.default_prompt_missing_skill",
                openai_yaml,
                f"interface.default_prompt does not mention ${name}.",
                "Include the explicit $skill-name token in the example prompt.",
                line_number(openai_text, "default_prompt:"),
            )

    result = finalize("static", root, facts, findings, max_findings)
    return result, 1 if result["summary"]["errors"] else 0


def validate_evals(evals_path: Path, max_findings: int) -> tuple[dict[str, Any], int]:
    path = evals_path.resolve()
    findings: list[Finding] = []
    facts: dict[str, Any] = {
        "skill_name": None,
        "target_skill_name": None,
        "eval_count": 0,
        "assertion_count": 0,
    }
    if not path.is_file():
        raise ValueError(f'Evals file must exist; received "{evals_path}".')
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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

    skill_root = path.parent.parent if path.parent.name == "evals" else path.parent
    target_skill_md = skill_root / "SKILL.md"
    target_skill_name = ""
    if target_skill_md.is_file():
        try:
            target_text = target_skill_md.read_text(encoding="utf-8")
            target_frontmatter, _, target_parse_errors = parse_frontmatter(target_text)
        except (OSError, UnicodeError) as exc:
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
                resolved = fixture if fixture.is_absolute() else skill_root / fixture
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
                facts["assertion_count"] += len(assertions)

    result = finalize("validate-evals", path, facts, findings, max_findings)
    return result, 1 if result["summary"]["errors"] else 0


def numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return converted


def metric(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "stddev": statistics.stdev(values) if len(values) > 1 else None,
    }


def parse_run(config_dir: Path) -> dict[str, float]:
    grading_path = config_dir / "grading.json"
    timing_path = config_dir / "timing.json"
    missing = [path.name for path in (grading_path, timing_path) if not path.is_file()]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    try:
        grading = json.loads(grading_path.read_text(encoding="utf-8"))
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
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
    for index, assertion in enumerate(assertion_results):
        label = f"assertion_results[{index}]"
        if not isinstance(assertion, dict):
            raise ValueError(f"{label} must be an object")
        if not isinstance(assertion.get("text"), str) or not assertion["text"].strip():
            raise ValueError(f"{label}.text must be a non-empty string")
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
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"pass_rate": [], "time_seconds": [], "tokens": []}
    )
    runs: list[dict[str, Any]] = []
    eval_dirs = sorted(path for path in root.glob("eval-*") if path.is_dir())
    if not eval_dirs:
        raise ValueError(f"No eval-* directories were found under {root}.")

    for eval_dir in eval_dirs:
        config_dirs = sorted(path for path in eval_dir.iterdir() if path.is_dir())
        present = {path.name for path in config_dirs}
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
                parsed = parse_run(config_dir)
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
            for key, value in parsed.items():
                values[config_dir.name][key].append(value)
            runs.append(
                {
                    "eval": eval_dir.name,
                    "configuration": config_dir.name,
                    "complete": True,
                    **parsed,
                }
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


def write_result(result: dict[str, Any], args: argparse.Namespace) -> None:
    if args.format == "text":
        rendered = render_text(result) + "\n"
    else:
        rendered = (
            json.dumps(
                result,
                indent=2 if args.pretty else None,
                ensure_ascii=False,
                sort_keys=False,
            )
            + "\n"
        )
    output = getattr(args, "output", None)
    if output and output != "-":
        destination = Path(output).resolve()
        if not destination.parent.is_dir():
            raise ValueError(
                f'Output parent must already exist; received "{destination.parent}".'
            )
        destination.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def add_output_options(
    parser: argparse.ArgumentParser, allow_output: bool = False
) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--max-findings",
        type=positive_int,
        default=100,
        help="Maximum findings returned; summary counts remain complete (default: 100).",
    )
    if allow_output:
        parser.add_argument(
            "--output",
            metavar="FILE",
            help="Also write the complete rendered result to FILE; use - for stdout only.",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic, non-executing checks for Agent Skill reviews.",
        epilog=EXIT_CODES,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    static_parser = subparsers.add_parser(
        "static", help="Inspect a skill without executing its scripts.", epilog=EXIT_CODES
    )
    static_parser.add_argument("target", help="Path to the target skill directory.")
    add_output_options(static_parser)

    evals_parser = subparsers.add_parser(
        "validate-evals",
        help="Validate an evals/evals.json definition and fixture paths.",
        epilog=EXIT_CODES,
    )
    evals_parser.add_argument("evals_json", help="Path to evals/evals.json.")
    add_output_options(evals_parser)

    aggregate_parser = subparsers.add_parser(
        "aggregate",
        help="Aggregate paired grading.json and timing.json run data.",
        epilog=EXIT_CODES,
    )
    aggregate_parser.add_argument(
        "iteration", help="Path containing eval-* run directories."
    )
    aggregate_parser.add_argument(
        "--candidate",
        default="with_skill",
        help="Candidate configuration name (default: with_skill).",
    )
    aggregate_parser.add_argument(
        "--baseline",
        default="without_skill",
        help="Baseline configuration name (default: without_skill).",
    )
    add_output_options(aggregate_parser, allow_output=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "static":
            result, status = static_review(Path(args.target), args.max_findings)
        elif args.command == "validate-evals":
            result, status = validate_evals(Path(args.evals_json), args.max_findings)
        else:
            result, status = aggregate(
                Path(args.iteration),
                args.candidate,
                args.baseline,
                args.max_findings,
            )
        write_result(result, args)
        return status
    except (OSError, UnicodeError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.stderr.write(f"Try: {Path(sys.argv[0]).name} {args.command} --help\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
