#!/usr/bin/env python3
"""Deterministic helpers for reviewing Agent Skills.

The tool never executes code from the target skill. Data is written to stdout;
fatal diagnostics are written to stderr.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import statistics
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
RESOURCE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:scripts|references|assets|evals)/"
    r"[A-Za-z0-9_./-]+(?:\.[A-Za-z0-9_-]+)?)"
)
INTERACTIVE_PATTERNS = (
    (re.compile(r"\binput\s*\("), "Python input() call"),
    (re.compile(r"\bgetpass(?:\.getpass)?\s*\("), "password prompt"),
    (re.compile(r"\bread\s+-[A-Za-z]*p\b"), "shell read -p prompt"),
    (re.compile(r"\bselect\s+\w+\s+in\b"), "shell select prompt"),
    (re.compile(r"\bread-host\b", re.IGNORECASE), "PowerShell Read-Host prompt"),
    (re.compile(r"\bset\s+/p\b", re.IGNORECASE), "cmd.exe set /p prompt"),
)
SCRIPT_SUFFIXES = {
    ".bash",
    ".bat",
    ".cmd",
    ".js",
    ".mjs",
    ".ps1",
    ".py",
    ".rb",
    ".sh",
    ".ts",
}
TRIGGER_FIELDS = {"query", "should_trigger", "split", "rationale"}
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "CONIN$",
    "CONOUT$",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    "COM\u00b9",
    "COM\u00b2",
    "COM\u00b3",
    "LPT\u00b9",
    "LPT\u00b2",
    "LPT\u00b3",
}
WINDOWS_INVALID_FILENAME_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
SHELL_FENCE_LANGUAGES = {
    "bash",
    "bat",
    "batch",
    "cmd",
    "console",
    "fish",
    "powershell",
    "ps1",
    "pwsh",
    "sh",
    "shell",
    "shell-session",
    "terminal",
    "zsh",
}
SESSION_FENCE_LANGUAGES = {"console", "shell-session", "terminal"}
SHELL_PROMPT_RE = re.compile(
    r"^\s*(?:PS(?:\s+[^>\r\n]*)?>|[A-Za-z]:[\\/][^>\r\n]*>|"
    r"[^$>\r\n]+\$|[$>])[ \t]*",
    re.IGNORECASE,
)
SHELL_SCRIPT_CALL_RE = re.compile(
    r"^\s*@?(?:(?:call|source)\s+|[.&]\s+)?(?:sudo\s+)?(?:env\s+)?"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
    r"(?:(?:(?:python(?:3(?:\.\d+)?)?|py|bash|sh|zsh|fish|node|deno|"
    r"ruby|pwsh|powershell|cmd)(?:\.exe)?|uv(?:\.exe)?\s+run)"
    r"(?:\s+(?!['\"]?(?:\.[\\/])?scripts[\\/])\S+){0,16}\s+)?"
    r"['\"]?(?:\.[\\/])?"
    r"(?P<path>scripts[\\/][A-Za-z0-9_.\\/-]+)['\"]?"
    r"(?=\s|$|[;&|])",
    re.IGNORECASE,
)
EXIT_CODES = (
    "Exit codes: 0 completed without error findings; 1 completed with error "
    "findings; 2 fatal CLI, filesystem, JSON parse, or output failure."
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


def split_markdown_fences(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return non-fenced text and language-tagged fenced lines."""
    output: list[str] = []
    fenced_lines: list[tuple[str, str]] = []
    fence_character: str | None = None
    fence_length = 0
    fence_language = ""
    for line in text.splitlines():
        match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
        marker = match.group(1) if match else ""
        if fence_character is None and marker:
            fence_character = marker[0]
            fence_length = len(marker)
            info = match.group(2).strip()
            fence_language = info.split(maxsplit=1)[0].casefold() if info else ""
            output.append("")
            continue
        if (
            fence_character is not None
            and marker
            and marker[0] == fence_character
            and len(marker) >= fence_length
            and not match.group(2).strip()
        ):
            fence_character = None
            fence_length = 0
            fence_language = ""
            output.append("")
            continue
        if fence_character is None:
            output.append(line)
        else:
            output.append("")
            fenced_lines.append((fence_language, line))
    return "\n".join(output), fenced_lines


def outside_fenced_code(text: str) -> str:
    """Return text outside Markdown fences while preserving line numbers."""
    return split_markdown_fences(text)[0]


def markdown_link_target(raw_target: str) -> str:
    """Extract a Markdown link destination without confusing titles or URIs."""
    value = raw_target.strip()
    if value.startswith("<"):
        closing = value.find(">", 1)
        target = value[1:closing] if closing != -1 else value[1:]
    else:
        target = value.split(maxsplit=1)[0]
    return target.split("#", 1)[0]


def shell_script_path(language: str, line: str) -> str | None:
    """Return a package script invoked by one shell-fence command line."""
    prompt_match = SHELL_PROMPT_RE.match(line)
    if language in SESSION_FENCE_LANGUAGES and prompt_match is None:
        return None
    command = line[prompt_match.end() :] if prompt_match else line
    stripped = command.lstrip()
    if (
        not stripped
        or stripped.startswith(("#", "::"))
        or re.match(r"(?i)^@?rem(?:\s|$)", stripped)
    ):
        return None
    match = SHELL_SCRIPT_CALL_RE.match(command)
    if match is None:
        return None
    return match.group("path").replace("\\", "/")


def extract_paths(text: str) -> dict[str, bool]:
    """Map resource paths to whether a real Markdown pointer requires them."""
    instruction_text, fenced_lines = split_markdown_fences(text)
    paths = {path: False for path in RESOURCE_PATH_RE.findall(instruction_text)}
    for language, line in fenced_lines:
        if language not in SHELL_FENCE_LANGUAGES:
            continue
        script_path = shell_script_path(language, line)
        if script_path:
            paths[script_path] = False
    for raw_target in MARKDOWN_LINK_RE.findall(instruction_text):
        target = markdown_link_target(raw_target)
        windows_target = PureWindowsPath(target)
        if target and (
            windows_target.drive
            or windows_target.root
            or not URI_SCHEME_RE.match(target)
        ):
            paths[target] = True
    return paths


def is_link_like(path: Path) -> bool:
    """Return whether a path is a symlink or Windows reparse point."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT
    )


def first_link_like_component(root: Path, candidate: Path) -> Path | None:
    """Find a redirecting component below root without dereferencing it."""
    lexical_root = Path(os.path.abspath(os.fspath(root)))
    lexical_candidate = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = lexical_candidate.relative_to(lexical_root)
    except ValueError:
        return None
    current = lexical_root
    for part in relative.parts:
        current /= part
        if is_link_like(current):
            return current
    return None


def resolve_within(root: Path, candidate: Path, *, strict: bool) -> Path:
    """Resolve candidate and require it to remain below resolved root."""
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=strict)
    resolved.relative_to(resolved_root)
    return resolved


def windows_filename_issue(parts: tuple[str, ...]) -> str | None:
    """Describe the first Windows-incompatible relative path component."""
    for part in parts:
        if part in {".", ".."}:
            continue
        if part.endswith((" ", ".")):
            return f'component "{part}" ends with a space or period'
        if WINDOWS_INVALID_FILENAME_RE.search(part):
            return f'component "{part}" contains a Windows-invalid character'
        device_name = part.split(".", 1)[0].rstrip(" .").upper()
        if device_name in WINDOWS_RESERVED_NAMES:
            return f'component "{part}" uses reserved Windows name "{device_name}"'
    return None


def iter_files(
    root: Path,
    directory: str,
    errors: list[tuple[Path, str]] | None = None,
) -> list[Path]:
    base = root / directory
    try:
        info = os.lstat(base)
    except FileNotFoundError:
        return []
    except OSError as exc:
        if errors is not None:
            errors.append((base, str(exc)))
        return []
    if stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT
    ):
        return [base]
    if not stat.S_ISDIR(info.st_mode):
        return []

    def record_walk_error(exc: OSError) -> None:
        if errors is None:
            return
        problem_path = Path(exc.filename) if exc.filename else base
        errors.append((problem_path, str(exc)))

    discovered: list[Path] = []
    for current_root, directory_names, file_names in os.walk(
        base, topdown=True, onerror=record_walk_error, followlinks=False
    ):
        current = Path(current_root)
        retained_directories: list[str] = []
        for name in directory_names:
            path = current / name
            if "__pycache__" in path.parts:
                continue
            if is_link_like(path):
                if path.suffix.lower() not in {".pyc", ".pyo"}:
                    discovered.append(path)
                continue
            retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            path = current / name
            if (
                "__pycache__" not in path.parts
                and path.suffix.lower() not in {".pyc", ".pyo"}
            ):
                discovered.append(path)
    return sorted(discovered)


def resolve_package_data_file(source: Path) -> tuple[Path, Path, str | None]:
    """Resolve a package data file without trusting links below its skill root."""
    path = Path(os.path.abspath(os.fspath(source)))
    lexical_skill_root = (
        path.parent.parent if path.parent.name.casefold() == "evals" else path.parent
    )
    redirect = first_link_like_component(lexical_skill_root, path)
    if redirect == path:
        try:
            path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f'Cannot resolve package data file "{source}": {exc}') from exc
        return path, lexical_skill_root, "file_symlink"
    if redirect is not None:
        return path, lexical_skill_root, "parent_symlink"
    if not path.is_file():
        return path, lexical_skill_root, "missing"

    try:
        skill_root = lexical_skill_root.resolve(strict=True)
        resolved_path = resolve_within(skill_root, path, strict=True)
        relative_path = path.relative_to(lexical_skill_root)
    except (OSError, RuntimeError, ValueError):
        return path, lexical_skill_root, "outside"
    if resolved_path != skill_root / relative_path:
        return path, skill_root, "parent_symlink"
    return path, skill_root, None


def first_actionable_match(text: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """Ignore regex declarations that quote the warning pattern itself."""
    for match in pattern.finditer(text):
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.end())
        line = text[start:] if end == -1 else text[start:end]
        if "re.compile" not in line:
            return match
    return None


def script_help_detected(path: Path, text: str) -> bool:
    """Recognize common help interfaces for supported script runtimes."""
    folded = text.casefold()
    if "--help" in folded or "argparse" in folded:
        return True
    if path.suffix.casefold() == ".ps1":
        return any(marker in folded for marker in (".synopsis", "get-help", "-?"))
    if path.suffix.casefold() in {".bat", ".cmd"}:
        return "/?" in folded
    return False


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
    if is_link_like(skill_md):
        add_finding(
            findings,
            "error",
            "package.skill_md_symlink",
            skill_md,
            "The root SKILL.md is a symbolic link or reparse point and was not inspected.",
            "Replace it with an ordinary file inside the skill package.",
        )
        return finalize("static", root, facts, findings, max_findings), 1
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
    inventory_errors: list[tuple[Path, str]] = []
    for directory in ("references", "scripts", "assets", "evals"):
        files = iter_files(root, directory, inventory_errors)
        all_resource_files[directory] = files
        facts["resource_files"][directory] = len(files)

    for problem_path, message in inventory_errors:
        add_finding(
            findings,
            "error",
            "package.resource_unreadable",
            problem_path,
            f"A package resource directory could not be inventoried: {message}.",
            "Restore read access and rerun the package-boundary preflight.",
        )

    for files in all_resource_files.values():
        for path in files:
            if is_link_like(path):
                add_finding(
                    findings,
                    "warning",
                    "package.resource_symlink",
                    path,
                    "A package resource is a symbolic link or reparse point and was not inspected.",
                    "Replace it with an ordinary package-local file before relying on it.",
                )

    instruction_files = [skill_md] + [
        path
        for path in all_resource_files["references"]
        if not is_link_like(path) and path.suffix.lower() in {".md", ".txt"}
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
            windows_pointer = PureWindowsPath(raw_path)
            if (
                windows_pointer.drive
                or windows_pointer.root
                or PurePosixPath(raw_path).is_absolute()
            ):
                add_finding(
                    findings,
                    "error",
                    "pointer.target_outside",
                    source,
                    f'Referenced path "{raw_path}" is drive-qualified, rooted, or absolute.',
                    "Use a package-relative pointer with forward-slash separators.",
                    line_number(source_text, raw_path),
                )
                continue
            if raw_path.startswith(("scripts/", "references/", "assets/", "evals/")):
                candidate = root / raw_path
            else:
                candidate = source.parent / raw_path
            redirect = first_link_like_component(root, candidate)
            try:
                resolved = resolve_within(root, candidate, strict=False)
            except (OSError, RuntimeError, ValueError):
                add_finding(
                    findings,
                    "error",
                    "pointer.target_outside",
                    source,
                    f'Referenced path "{raw_path}" resolves outside the skill package.',
                    "Keep review resources inside the target skill root.",
                    line_number(source_text, raw_path),
                )
                continue
            if redirect is not None:
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
        if is_link_like(path):
            continue
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
        if is_link_like(path):
            continue
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
        except (OSError, UnicodeError) as exc:
            add_finding(
                findings,
                "warning",
                "script.unreadable",
                path,
                f"The script could not be read as UTF-8: {exc}.",
                "Restore read access or use a documented text encoding before review.",
            )
            continue
        if not script_help_detected(path, script_text):
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
    metadata_redirect = first_link_like_component(root, openai_yaml)
    if metadata_redirect is not None:
        add_finding(
            findings,
            "warning",
            "package.metadata_symlink",
            openai_yaml,
            "Agent metadata or one of its parent directories is a symbolic link or reparse point and was not inspected.",
            "Replace it with an ordinary package-local file.",
        )
        try:
            metadata_redirect.resolve(strict=True).relative_to(root)
        except ValueError:
            add_finding(
                findings,
                "error",
                "package.metadata_outside",
                openai_yaml,
                "Agent metadata redirects outside the skill package and was not inspected.",
                "Keep agents/openai.yaml and all of its parent directories inside the package.",
            )
        except (OSError, RuntimeError):
            pass
    elif openai_yaml.is_file() and name:
        try:
            openai_text = openai_yaml.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add_finding(
                findings,
                "warning",
                "metadata.unreadable",
                openai_yaml,
                f"Agent metadata could not be read as UTF-8: {exc}.",
                "Restore read access or use UTF-8 metadata before review.",
            )
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


def parse_run(root: Path, config_dir: Path) -> dict[str, Any]:
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
        for config_dir in sorted(eval_dir.iterdir()):
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
                parsed = parse_run(root, config_dir)
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
            help=(
                "Also write the rendered result to FILE; findings remain subject to "
                "--max-findings. Use - for stdout only."
            ),
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

    triggers_parser = subparsers.add_parser(
        "validate-triggers",
        help="Validate a trigger query JSON definition and its coverage.",
        epilog=EXIT_CODES,
    )
    triggers_parser.add_argument(
        "trigger_queries_json", help="Path to evals/trigger_queries.json."
    )
    add_output_options(triggers_parser)

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
        elif args.command == "validate-triggers":
            result, status = validate_triggers(
                Path(args.trigger_queries_json), args.max_findings
            )
        else:
            result, status = aggregate(
                Path(args.iteration),
                args.candidate,
                args.baseline,
                args.max_findings,
            )
        write_result(result, args)
        return status
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.stderr.write(f"Try: {Path(sys.argv[0]).name} {args.command} --help\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
