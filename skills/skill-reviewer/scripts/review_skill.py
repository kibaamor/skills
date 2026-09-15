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
import secrets
import stat
import statistics
import sys
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
COMMONMARK_BACKSLASH_ESCAPE_RE = re.compile(
    r"""\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])"""
)
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
POWERSHELL_FENCE_LANGUAGES = {"powershell", "ps1", "pwsh"}
SHELL_PROMPT_RE = re.compile(
    r"^\s*(?:PS(?:\s+[^>\r\n]*)?>|\\\\[^>\r\n]+>|[A-Za-z]:[\\/][^>\r\n]*>|"
    r"[^$>\r\n]+\$(?=[ \t])|[$>](?=[ \t]))[ \t]*",
    re.IGNORECASE,
)
SHELL_SCRIPT_CALL_RE = re.compile(
    r"^\s*@?(?:(?:call|source)\s+|[.&]\s+)?(?:sudo\s+)?(?:env\s+)?"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
    r"(?:(?:(?:python(?:3(?:\.\d+)?)?|py|bash|sh|zsh|fish|node|deno|"
    r"ruby|pwsh|powershell|cmd)(?:\.exe)?|uv(?:\.exe)?\s+run)"
    r"(?:\s+(?!['\"]?(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]"
    r"|%~dp0[\\/]?)?"
    r"(?:\.[\\/])?scripts[\\/])\S+){0,16}\s+)?"
    r"(?:"
    r'"(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]|%~dp0[\\/]?)?'
    r"(?:\.[\\/])?(?P<double_path>scripts[\\/][^\"\r\n]+)\"|"
    r"'(?:\.[\\/])?(?P<single_path>scripts[\\/][^'\r\n]+)'|"
    r"(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]|%~dp0[\\/]?)?"
    r"(?:\.[\\/])?(?P<unquoted_path>scripts[\\/][A-Za-z0-9_.\\/-]+)"
    r")"
    r"(?=\s|$|[;&|])",
    re.IGNORECASE,
)
EXIT_CODES = (
    "Exit codes: 0 completed without error findings; 1 completed with error "
    "findings; 2 fatal CLI, filesystem, JSON parse, or output failure."
)

MAX_RESOURCE_ENTRIES = 4096
MAX_RESOURCE_DEPTH = 32
MAX_TEXT_FILE_BYTES = 1 << 20
MAX_TOTAL_TEXT_BYTES = 8 << 20
MAX_MARKDOWN_LINK_CANDIDATES = 4096
MAX_MARKDOWN_TARGET_CHARACTERS = 1 << 20
READ_CHUNK_BYTES = 64 << 10


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int | None
    message: str
    suggestion: str


@dataclass
class _MarkdownLinkCandidate:
    open_paren: int
    start: int
    angle: bool
    first_space: int | None = None
    close: int | None = None


@dataclass
class _MarkdownScanBudget:
    candidates: int = 0
    target_characters: int = 0


class MarkdownScanLimitError(ValueError):
    """Raised when inline-link extraction exceeds a deterministic budget."""


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
    if value.startswith("<") and value.endswith(">"):
        target = value[1:-1]
    else:
        target = value.split(maxsplit=1)[0]
    return target


def commonmark_unescape(value: str) -> str:
    """Decode punctuation escapes that are valid in CommonMark destinations."""
    return COMMONMARK_BACKSLASH_ESCAPE_RE.sub(r"\1", value)


def commonmark_path(value: str) -> str:
    """Return the filesystem path part of a CommonMark link destination."""
    return commonmark_unescape(value).split("#", 1)[0]


def _append_markdown_target(
    targets: list[str],
    line: str,
    start: int,
    end: int,
    budget: _MarkdownScanBudget,
) -> None:
    target_length = end - start
    if budget.target_characters + target_length > MAX_MARKDOWN_TARGET_CHARACTERS:
        raise MarkdownScanLimitError(
            "Markdown link destinations exceed the "
            f"{MAX_MARKDOWN_TARGET_CHARACTERS}-character scan budget"
        )
    budget.target_characters += target_length
    targets.append(line[start:end])


def _markdown_link_targets_on_line(
    line: str, budget: _MarkdownScanBudget
) -> list[str]:
    """Preserve the supported inline-link subset in output-sensitive linear time."""
    length = len(line)
    candidates: list[_MarkdownLinkCandidate] = []

    # Linear equivalent of the former ``(?<!!)\[[^\]\r\n]+\]\(`` search.
    pending_open_bracket: int | None = None
    index = 0
    while index < length:
        character = line[index]
        if character == "[":
            if pending_open_bracket is None and (
                index == 0 or line[index - 1] != "!"
            ):
                pending_open_bracket = index
        elif character == "]":
            if (
                pending_open_bracket is not None
                and index > pending_open_bracket + 1
                and index + 1 < length
                and line[index + 1] == "("
            ):
                budget.candidates += 1
                if budget.candidates > MAX_MARKDOWN_LINK_CANDIDATES:
                    raise MarkdownScanLimitError(
                        "Markdown link candidates exceed the "
                        f"{MAX_MARKDOWN_LINK_CANDIDATES}-candidate scan budget"
                    )
                open_paren = index + 1
                start = open_paren + 1
                while start < length and line[start] in " \t":
                    start += 1
                candidates.append(
                    _MarkdownLinkCandidate(
                        open_paren=open_paren,
                        start=start,
                        angle=start < length and line[start] == "<",
                    )
                )
                pending_open_bracket = None
                index += 1
            else:
                pending_open_bracket = None
        index += 1

    if not candidates:
        return []

    escaped = bytearray(length)
    preceding_backslashes = 0
    for index, character in enumerate(line):
        escaped[index] = preceding_backslashes % 2
        if character == "\\":
            preceding_backslashes += 1
        else:
            preceding_backslashes = 0

    by_open_paren = {candidate.open_paren: candidate for candidate in candidates}
    parenthesis_stack: list[int] = []
    for index, character in enumerate(line):
        if escaped[index]:
            continue
        if character == "(":
            parenthesis_stack.append(index)
        elif character in " \t":
            if parenthesis_stack:
                candidate = by_open_paren.get(parenthesis_stack[-1])
                if (
                    candidate is not None
                    and not candidate.angle
                    and index >= candidate.start
                    and candidate.first_space is None
                ):
                    candidate.first_space = index
        elif character == ")" and parenthesis_stack:
            open_paren = parenthesis_stack.pop()
            candidate = by_open_paren.get(open_paren)
            if candidate is not None:
                candidate.close = index

    next_gt = [-1] * (length + 1)
    next_close = [-1] * (length + 1)
    nearest_gt = -1
    nearest_close = -1
    for index in range(length - 1, -1, -1):
        if not escaped[index]:
            if line[index] == ">":
                nearest_gt = index
            if line[index] == ")":
                nearest_close = index
        next_gt[index] = nearest_gt
        next_close[index] = nearest_close

    targets: list[str] = []
    for candidate in candidates:
        if candidate.start >= length:
            continue
        if candidate.angle:
            end = next_gt[candidate.start + 1]
            if end != -1 and next_close[end + 1] != -1:
                _append_markdown_target(
                    targets, line, candidate.start, end + 1, budget
                )
        elif candidate.first_space is not None:
            if next_close[candidate.first_space + 1] != -1:
                _append_markdown_target(
                    targets,
                    line,
                    candidate.start,
                    candidate.first_space,
                    budget,
                )
        elif candidate.close is not None:
            _append_markdown_target(
                targets, line, candidate.start, candidate.close, budget
            )
    return targets


def markdown_link_targets(text: str) -> list[str]:
    """Extract inline-link destinations without repeatedly scanning suffixes."""
    targets: list[str] = []
    budget = _MarkdownScanBudget()
    line_start = 0
    for index, character in enumerate(text):
        if character in "\r\n":
            targets.extend(
                _markdown_link_targets_on_line(text[line_start:index], budget)
            )
            line_start = index + 1
    targets.extend(_markdown_link_targets_on_line(text[line_start:], budget))
    return targets


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
    powershell_prompt = bool(
        language in SESSION_FENCE_LANGUAGES
        and re.match(r"^\s*PS(?:\s+[^>\r\n]*)?>", line, re.IGNORECASE)
    )
    if (
        language in POWERSHELL_FENCE_LANGUAGES or powershell_prompt
    ) and stripped.startswith(("'", '"')):
        return None
    match = SHELL_SCRIPT_CALL_RE.match(command)
    if match is None:
        return None
    path = next(
        value
        for value in (
            match.group("double_path"),
            match.group("single_path"),
            match.group("unquoted_path"),
        )
        if value is not None
    )
    return path.replace("\\", "/")


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
    for raw_target in markdown_link_targets(instruction_text):
        target = markdown_link_target(raw_target)
        comparison_target = commonmark_path(target)
        windows_target = PureWindowsPath(comparison_target)
        if comparison_target and (
            windows_target.drive
            or windows_target.root
            or not URI_SCHEME_RE.match(comparison_target)
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


@dataclass(frozen=True)
class InventoryIssue:
    path: Path
    code: str
    message: str


@dataclass
class InventoryState:
    entries_scanned: int = 0
    complete: bool = True
    entry_limit_reported: bool = False


@dataclass
class TextReadBudget:
    bytes_read: int = 0


class TextReadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def file_type_name(mode: int) -> str:
    if stat.S_ISFIFO(mode):
        return "FIFO"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISBLK(mode):
        return "block device"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "regular file"
    return "non-regular file"


def is_reparse_stat(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT)


def stable_file_signature(info: os.stat_result) -> tuple[int, ...]:
    """Return mutation-sensitive metadata that ordinary reads do not change."""
    if os.name == "nt":
        return (info.st_size, info.st_mtime_ns)
    return (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def iter_files(
    root: Path,
    directory: str,
    issues: list[InventoryIssue] | None = None,
    state: InventoryState | None = None,
) -> list[Path]:
    """Inventory ordinary resources without following links or special files."""
    if state is None:
        state = InventoryState()
    if not state.complete and state.entry_limit_reported:
        return []
    base = root / directory
    try:
        info = os.lstat(base)
    except FileNotFoundError:
        return []
    except OSError as exc:
        if issues is not None:
            issues.append(
                InventoryIssue(base, "package.resource_unreadable", str(exc))
            )
        state.complete = False
        return []
    if stat.S_ISLNK(info.st_mode) or is_reparse_stat(info):
        state.complete = False
        if issues is not None:
            issues.append(
                InventoryIssue(
                    base,
                    "package.resource_symlink",
                    "A resource directory is a symbolic link or reparse point and was not inspected.",
                )
            )
        return [base]
    if not stat.S_ISDIR(info.st_mode):
        if issues is not None:
            issues.append(
                InventoryIssue(
                    base,
                    "package.resource_special_file",
                    f"Expected a resource directory but found a {file_type_name(info.st_mode)}.",
                )
            )
        state.complete = False
        return []

    discovered: list[Path] = []
    pending: list[tuple[Path, int]] = [(base, 0)]
    while pending and not state.entry_limit_reported:
        current, depth = pending.pop()
        try:
            current_info = os.lstat(current)
        except OSError as exc:
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        current,
                        "package.resource_changed",
                        f"A queued resource directory changed before inspection: {exc}",
                    )
                )
            state.complete = False
            continue
        if (
            stat.S_ISLNK(current_info.st_mode)
            or is_reparse_stat(current_info)
            or not stat.S_ISDIR(current_info.st_mode)
        ):
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        current,
                        "package.resource_changed",
                        "A queued resource directory changed before inspection.",
                    )
                )
            state.complete = False
            continue
        try:
            entries = os.scandir(current)
        except OSError as exc:
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        Path(exc.filename) if exc.filename else current,
                        "package.resource_unreadable",
                        str(exc),
                    )
                )
            state.complete = False
            continue
        try:
            opened_info = os.lstat(current)
        except OSError as exc:
            entries.close()
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        current,
                        "package.resource_changed",
                        f"A resource directory changed while it was being opened: {exc}",
                    )
                )
            state.complete = False
            continue
        if (
            stat.S_ISLNK(opened_info.st_mode)
            or is_reparse_stat(opened_info)
            or not stat.S_ISDIR(opened_info.st_mode)
            or not os.path.samestat(current_info, opened_info)
            or stable_file_signature(current_info)
            != stable_file_signature(opened_info)
        ):
            entries.close()
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        current,
                        "package.resource_changed",
                        "A resource directory changed while it was being opened.",
                    )
                )
            state.complete = False
            continue
        discovered_start = len(discovered)
        pending_start = len(pending)
        issues_start = len(issues) if issues is not None else 0
        try:
            with entries:
                for entry in entries:
                    path = Path(entry.path)
                    if state.entries_scanned >= MAX_RESOURCE_ENTRIES:
                        state.complete = False
                        state.entry_limit_reported = True
                        if issues is not None:
                            issues.append(
                                InventoryIssue(
                                    root,
                                    "package.resource_entry_limit",
                                    "Resource inventory stopped after "
                                    f"{MAX_RESOURCE_ENTRIES} entries.",
                                )
                            )
                        break
                    state.entries_scanned += 1
                    try:
                        entry_info = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        state.complete = False
                        if issues is not None:
                            issues.append(
                                InventoryIssue(
                                    path,
                                    "package.resource_unreadable",
                                    str(exc),
                                )
                            )
                        continue

                    relative_parts = path.relative_to(base).parts
                    ignored = (
                        "__pycache__" in relative_parts
                        or path.suffix.lower() in {".pyc", ".pyo"}
                    )
                    if stat.S_ISLNK(entry_info.st_mode) or is_reparse_stat(entry_info):
                        if not ignored:
                            state.complete = False
                            discovered.append(path)
                            if issues is not None:
                                issues.append(
                                    InventoryIssue(
                                        path,
                                        "package.resource_symlink",
                                        "A package resource is a symbolic link or reparse point and was not inspected.",
                                    )
                                )
                        continue
                    if stat.S_ISDIR(entry_info.st_mode):
                        if ignored:
                            continue
                        child_depth = depth + 1
                        if child_depth > MAX_RESOURCE_DEPTH:
                            state.complete = False
                            if issues is not None:
                                issues.append(
                                    InventoryIssue(
                                        path,
                                        "package.resource_depth_limit",
                                        "Resource directory depth exceeds the "
                                        f"configured limit of {MAX_RESOURCE_DEPTH}.",
                                    )
                                )
                            continue
                        pending.append((path, child_depth))
                        continue
                    if stat.S_ISREG(entry_info.st_mode):
                        if not ignored:
                            discovered.append(path)
                        continue
                    state.complete = False
                    if issues is not None:
                        issues.append(
                            InventoryIssue(
                                path,
                                "package.resource_special_file",
                                f"A {file_type_name(entry_info.st_mode)} resource was not inspected.",
                            )
                        )
        except OSError as exc:
            state.complete = False
            if issues is not None:
                issues.append(
                    InventoryIssue(
                        Path(exc.filename) if exc.filename else current,
                        "package.resource_unreadable",
                        str(exc),
                    )
                )
        else:
            try:
                current_after = os.lstat(current)
            except OSError as exc:
                current_after = None
                changed_message = (
                    f"A resource directory changed during inspection: {exc}"
                )
            else:
                changed_message = "A resource directory changed during inspection."
            if (
                current_after is None
                or stat.S_ISLNK(current_after.st_mode)
                or is_reparse_stat(current_after)
                or not stat.S_ISDIR(current_after.st_mode)
                or not os.path.samestat(opened_info, current_after)
                or stable_file_signature(opened_info)
                != stable_file_signature(current_after)
            ):
                del discovered[discovered_start:]
                del pending[pending_start:]
                if issues is not None:
                    del issues[issues_start:]
                    issues.append(
                        InventoryIssue(
                            current,
                            "package.resource_changed",
                            changed_message,
                        )
                    )
                state.complete = False
    return sorted(discovered)


def read_bounded_regular_utf8(
    root: Path,
    path: Path,
    budget: TextReadBudget,
) -> str:
    """Read one stable package-local ordinary file within shared byte limits."""
    lexical_root = Path(os.path.abspath(os.fspath(root)))
    path = Path(os.path.abspath(os.fspath(path)))
    try:
        path.relative_to(lexical_root)
    except ValueError as exc:
        raise TextReadError(
            "package.resource_changed",
            f'Resource path is outside the package root "{lexical_root}".',
        ) from exc
    redirect = first_link_like_component(lexical_root, path)
    if redirect is not None:
        raise TextReadError(
            "package.resource_changed",
            f'Path redirects through symbolic link or reparse point "{redirect}".',
        )
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise TextReadError(
            "package.resource_unreadable", f"Cannot inspect the resource: {exc}"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or is_reparse_stat(before):
        raise TextReadError(
            "package.resource_changed",
            "The resource became a symbolic link or reparse point.",
        )
    if not stat.S_ISREG(before.st_mode):
        raise TextReadError(
            "package.resource_special_file",
            f"A {file_type_name(before.st_mode)} resource was not inspected.",
        )
    if before.st_size > MAX_TEXT_FILE_BYTES:
        raise TextReadError(
            "package.resource_too_large",
            f"The resource exceeds the {MAX_TEXT_FILE_BYTES}-byte per-file limit.",
        )

    remaining = MAX_TOTAL_TEXT_BYTES - budget.bytes_read
    if remaining <= 0 or before.st_size > remaining:
        raise TextReadError(
            "package.resource_text_budget",
            f"The package exceeds the {MAX_TOTAL_TEXT_BYTES}-byte text-read budget.",
        )
    maximum = min(MAX_TEXT_FILE_BYTES, remaining)
    flags = os.O_RDONLY
    for flag_name in (
        "O_BINARY",
        "O_CLOEXEC",
        "O_NOCTTY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
    ):
        flags |= getattr(os, flag_name, 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise TextReadError(
            "package.resource_unreadable", f"Cannot open the resource safely: {exc}"
        ) from exc

    chunks: list[bytes] = []
    bytes_read = 0
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise TextReadError(
                "package.resource_special_file",
                f"A {file_type_name(opened.st_mode)} resource was not inspected.",
            )
        if (
            not os.path.samestat(before, opened)
            or stable_file_signature(before) != stable_file_signature(opened)
        ):
            raise TextReadError(
                "package.resource_changed",
                "The resource changed while it was being opened.",
            )
        redirect = first_link_like_component(lexical_root, path)
        try:
            current = os.lstat(path)
        except OSError as exc:
            raise TextReadError(
                "package.resource_changed",
                f"The resource changed while it was being opened: {exc}",
            ) from exc
        if (
            redirect is not None
            or not os.path.samestat(current, opened)
            or stable_file_signature(current) != stable_file_signature(opened)
        ):
            raise TextReadError(
                "package.resource_changed",
                "The resource path changed while it was being opened.",
            )

        while bytes_read <= maximum:
            request_size = min(READ_CHUNK_BYTES, maximum + 1 - bytes_read)
            if request_size <= 0:
                break
            chunk = os.read(descriptor, request_size)
            if not chunk:
                break
            chunks.append(chunk)
            bytes_read += len(chunk)
            budget.bytes_read += len(chunk)

        opened_after = os.fstat(descriptor)
        redirect = first_link_like_component(lexical_root, path)
        try:
            current_after = os.lstat(path)
        except OSError as exc:
            raise TextReadError(
                "package.resource_changed",
                f"The resource changed while it was being read: {exc}",
            ) from exc
        if (
            redirect is not None
            or not os.path.samestat(opened, opened_after)
            or not os.path.samestat(current_after, opened_after)
            or stable_file_signature(opened_after) != stable_file_signature(opened)
            or stable_file_signature(current_after)
            != stable_file_signature(opened_after)
        ):
            raise TextReadError(
                "package.resource_changed",
                "The resource changed while it was being read.",
            )
    except OSError as exc:
        raise TextReadError(
            "package.resource_unreadable", f"Cannot read the resource safely: {exc}"
        ) from exc
    finally:
        os.close(descriptor)

    if bytes_read > MAX_TEXT_FILE_BYTES:
        raise TextReadError(
            "package.resource_too_large",
            f"The resource exceeds the {MAX_TEXT_FILE_BYTES}-byte per-file limit.",
        )
    if bytes_read > remaining:
        raise TextReadError(
            "package.resource_text_budget",
            f"The package exceeds the {MAX_TOTAL_TEXT_BYTES}-byte text-read budget.",
        )
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeError as exc:
        raise TextReadError(
            "package.resource_unreadable", f"The resource is not valid UTF-8: {exc}"
        ) from exc


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


def add_text_read_error(
    findings: list[Finding],
    path: Path,
    error: TextReadError,
    reported_limits: set[str],
) -> None:
    if error.code == "package.resource_text_budget":
        if error.code in reported_limits:
            return
        reported_limits.add(error.code)
    add_finding(
        findings,
        "error",
        error.code,
        path,
        str(error),
        "Replace it with a stable, ordinary UTF-8 file within the documented limits.",
    )


def static_review(target: Path, max_findings: int) -> tuple[dict[str, Any], int]:
    root = target.resolve()
    findings: list[Finding] = []
    text_budget = TextReadBudget()
    reported_limits: set[str] = set()
    facts: dict[str, Any] = {
        "skill_name": None,
        "description_characters": 0,
        "skill_md_lines": 0,
        "resource_files": {},
        "resource_entries_scanned": 0,
        "resource_inventory_complete": False,
        "text_bytes_read": 0,
        "text_inspection_complete": False,
        "limits": {
            "resource_entries": MAX_RESOURCE_ENTRIES,
            "resource_depth": MAX_RESOURCE_DEPTH,
            "text_file_bytes": MAX_TEXT_FILE_BYTES,
            "total_text_bytes": MAX_TOTAL_TEXT_BYTES,
            "markdown_link_candidates": MAX_MARKDOWN_LINK_CANDIDATES,
            "markdown_target_characters": MAX_MARKDOWN_TARGET_CHARACTERS,
        },
    }

    if not root.is_dir():
        raise ValueError(
            f'Target must be an existing skill directory; received "{target}".'
        )

    skill_md = root / "SKILL.md"
    try:
        skill_info = os.lstat(skill_md)
    except FileNotFoundError:
        skill_info = None
    except OSError as exc:
        raise ValueError(f"Cannot inspect {skill_md}: {exc}") from exc
    if skill_info is not None and (
        stat.S_ISLNK(skill_info.st_mode) or is_reparse_stat(skill_info)
    ):
        add_finding(
            findings,
            "error",
            "package.skill_md_symlink",
            skill_md,
            "The root SKILL.md is a symbolic link or reparse point and was not inspected.",
            "Replace it with an ordinary file inside the skill package.",
        )
        return finalize("static", root, facts, findings, max_findings), 1
    if skill_info is None:
        add_finding(
            findings,
            "error",
            "structure.skill_md_missing",
            skill_md,
            "The target directory has no SKILL.md.",
            "Point to the skill directory or add the required SKILL.md.",
        )
        return finalize("static", root, facts, findings, max_findings), 1
    if not stat.S_ISREG(skill_info.st_mode):
        add_finding(
            findings,
            "error",
            "package.resource_special_file",
            skill_md,
            f"The root SKILL.md is a {file_type_name(skill_info.st_mode)} and was not inspected.",
            "Replace it with an ordinary UTF-8 file inside the skill package.",
        )
        facts["resource_inventory_complete"] = False
        facts["text_inspection_complete"] = False
        return finalize("static", root, facts, findings, max_findings), 1
    try:
        text = read_bounded_regular_utf8(root, skill_md, text_budget)
    except TextReadError as exc:
        add_text_read_error(findings, skill_md, exc, reported_limits)
        facts["text_bytes_read"] = text_budget.bytes_read
        facts["text_inspection_complete"] = False
        return finalize("static", root, facts, findings, max_findings), 1

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
    inventory_issues: list[InventoryIssue] = []
    inventory_state = InventoryState()
    for directory in ("references", "scripts", "assets", "evals"):
        files = iter_files(root, directory, inventory_issues, inventory_state)
        all_resource_files[directory] = files
        facts["resource_files"][directory] = len(files)

    facts["resource_entries_scanned"] = inventory_state.entries_scanned
    facts["resource_inventory_complete"] = inventory_state.complete
    for issue in inventory_issues:
        add_finding(
            findings,
            "error",
            issue.code,
            issue.path,
            issue.message,
            "Use ordinary package-local files and keep the package within the documented limits.",
        )

    instruction_files = [skill_md] + [
        path
        for path in all_resource_files["references"]
        if not is_link_like(path) and path.suffix.lower() in {".md", ".txt"}
    ]
    file_texts: dict[Path, str] = {skill_md: text}
    text_inspection_complete = True
    for path in instruction_files[1:]:
        try:
            file_texts[path] = read_bounded_regular_utf8(root, path, text_budget)
        except TextReadError as exc:
            text_inspection_complete = False
            add_text_read_error(findings, path, exc, reported_limits)

    attempted_companions: set[Path] = set()
    companion_files_attempted = 0
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
        try:
            extracted_paths = extract_paths(source_text)
        except MarkdownScanLimitError as exc:
            text_inspection_complete = False
            add_finding(
                findings,
                "error",
                "pointer.scan_limited",
                source,
                f"Pointer inspection stopped: {exc}.",
                "Reduce pathological inline-link nesting or split the instructions into focused references.",
            )
            continue
        for raw, required_pointer in extracted_paths.items():
            raw_path = raw
            if not raw_path:
                continue
            source_path = raw_path
            if required_pointer:
                raw_path = commonmark_path(raw_path)
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
                    f'Referenced path "{source_path}" is drive-qualified, rooted, or absolute.',
                    "Use a package-relative pointer with forward-slash separators.",
                    line_number(source_text, source_path),
                )
                continue
            if "\\" in raw_path:
                add_finding(
                    findings,
                    "error",
                    "pointer.target_nonportable",
                    source,
                    f'Referenced path "{source_path}" uses backslash separators.',
                    "Use forward-slash separators in package-relative Markdown pointers.",
                    line_number(source_text, source_path),
                )
                continue
            filename_issue = windows_filename_issue(PurePosixPath(raw_path).parts)
            if filename_issue is not None:
                add_finding(
                    findings,
                    "error",
                    "pointer.target_nonportable",
                    source,
                    f'Referenced path "{source_path}" is not Windows-portable: '
                    f"{filename_issue}.",
                    "Use Windows-portable names in package-relative Markdown pointers.",
                    line_number(source_text, source_path),
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
                    f'Referenced path "{source_path}" resolves outside the skill package.',
                    "Keep review resources inside the target skill root.",
                    line_number(source_text, source_path),
                )
                continue
            candidate_path = Path(os.path.abspath(candidate))
            is_root_companion = (
                required_pointer
                and resolved.exists()
                and candidate_path.parent == root
                and candidate_path.suffix.lower() in {".md", ".txt"}
            )
            should_read_companion = is_root_companion and (
                redirect is not None or resolved not in file_texts
            )
            if should_read_companion and candidate_path not in attempted_companions:
                attempted_companions.add(candidate_path)
                if companion_files_attempted >= MAX_RESOURCE_ENTRIES:
                    text_inspection_complete = False
                    limit_code = "package.resource_entry_limit"
                    if limit_code not in reported_limits:
                        reported_limits.add(limit_code)
                        add_finding(
                            findings,
                            "error",
                            limit_code,
                            candidate_path,
                            "Companion instruction traversal stopped after "
                            f"{MAX_RESOURCE_ENTRIES} files.",
                            "Consolidate root companion documents or remove "
                            "unneeded pointers.",
                        )
                else:
                    companion_files_attempted += 1
                    try:
                        file_texts[resolved] = read_bounded_regular_utf8(
                            root, candidate_path, text_budget
                        )
                    except TextReadError as exc:
                        text_inspection_complete = False
                        add_text_read_error(
                            findings, candidate_path, exc, reported_limits
                        )
            if redirect is not None:
                continue
            mentioned.add(resolved)
            if not resolved.exists() and required_pointer:
                add_finding(
                    findings,
                    "error",
                    "pointer.target_missing",
                    source,
                    f'Referenced path "{source_path}" does not exist.',
                    "Correct the pointer or add the required resource.",
                    line_number(source_text, source_path),
                )
            elif (
                resolved.exists() and resolved in file_texts and resolved not in visited
            ):
                reachable_references.add(resolved)
                queue.append(resolved)

    integrity_complete = inventory_state.complete and text_inspection_complete
    if integrity_complete:
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
        if integrity_complete and path not in mentioned:
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
            script_text = read_bounded_regular_utf8(root, path, text_budget)
        except TextReadError as exc:
            text_inspection_complete = False
            add_text_read_error(findings, path, exc, reported_limits)
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
        text_inspection_complete = False
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
    else:
        try:
            metadata_info = os.lstat(openai_yaml)
        except FileNotFoundError:
            metadata_info = None
        except NotADirectoryError as exc:
            metadata_info = None
            text_inspection_complete = False
            add_finding(
                findings,
                "error",
                "package.resource_special_file",
                openai_yaml,
                f"Agent metadata has a non-directory parent and was not inspected: {exc}.",
                "Use an ordinary agents directory containing an ordinary UTF-8 openai.yaml file.",
            )
        except OSError as exc:
            metadata_info = None
            text_inspection_complete = False
            add_finding(
                findings,
                "error",
                "package.resource_unreadable",
                openai_yaml,
                f"Agent metadata could not be inspected: {exc}.",
                "Restore read access and rerun the package-boundary preflight.",
            )
        if metadata_info is not None and not stat.S_ISREG(metadata_info.st_mode):
            text_inspection_complete = False
            add_finding(
                findings,
                "error",
                "package.resource_special_file",
                openai_yaml,
                f"Agent metadata is a {file_type_name(metadata_info.st_mode)} and was not inspected.",
                "Replace it with an ordinary UTF-8 file inside the skill package.",
            )
        elif metadata_info is not None and name:
            try:
                openai_text = read_bounded_regular_utf8(
                    root, openai_yaml, text_budget
                )
            except TextReadError as exc:
                text_inspection_complete = False
                add_text_read_error(findings, openai_yaml, exc, reported_limits)
                openai_text = ""
            default_prompt_match = re.search(
                r"^\s*default_prompt:\s*['\"]?(.*?)['\"]?\s*$",
                openai_text,
                re.MULTILINE,
            )
            if default_prompt_match and f"${name}" not in default_prompt_match.group(
                1
            ):
                add_finding(
                    findings,
                    "error",
                    "metadata.default_prompt_missing_skill",
                    openai_yaml,
                    f"interface.default_prompt does not mention ${name}.",
                    "Include the explicit $skill-name token in the example prompt.",
                    line_number(openai_text, "default_prompt:"),
                )

    facts["text_bytes_read"] = text_budget.bytes_read
    facts["text_inspection_complete"] = text_inspection_complete
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


def aggregate_output_destination(
    iteration: str, output: str, resolved_iteration: Path
) -> tuple[Path, Path]:
    """Map an output below the selected iteration to its fixed resolved root."""
    selected_root = Path(os.path.abspath(os.fspath(iteration)))
    resolved_root = Path(os.path.abspath(os.fspath(resolved_iteration)))
    selected_output = Path(os.path.abspath(os.fspath(output)))
    relative: Path | None = None
    for allowed_root in (selected_root, resolved_root):
        try:
            relative = selected_output.relative_to(allowed_root)
            break
        except ValueError:
            continue
    if relative is None:
        raise ValueError(
            f'Aggregate output must remain inside iteration "{resolved_root}"; '
            f'received "{selected_output}".'
        )
    destination = resolved_root / relative
    if destination == resolved_root:
        raise ValueError("Aggregate output must name a file below the iteration root.")
    return resolved_root, destination


def validate_output_root(
    root: Path, expected_info: os.stat_result | None
) -> os.stat_result:
    try:
        root_info = os.lstat(root)
    except OSError as exc:
        raise ValueError(f'Cannot inspect fixed iteration root "{root}": {exc}') from exc
    if (
        stat.S_ISLNK(root_info.st_mode)
        or is_reparse_stat(root_info)
        or not stat.S_ISDIR(root_info.st_mode)
    ):
        raise ValueError(f'Fixed iteration root is no longer an ordinary directory: "{root}".')
    if expected_info is not None and not os.path.samestat(expected_info, root_info):
        raise ValueError(f'Iteration root changed before output publication: "{root}".')
    return root_info


def validate_output_parent(
    root: Path,
    destination: Path,
    expected_root_info: os.stat_result | None,
) -> os.stat_result:
    validate_output_root(root, expected_root_info)
    redirect = first_link_like_component(root, destination.parent)
    if redirect is not None:
        raise ValueError(
            f'Output parent redirects through symbolic link or reparse point "{redirect}".'
        )
    try:
        parent_info = os.lstat(destination.parent)
    except OSError as exc:
        raise ValueError(
            f'Output parent must already exist; received "{destination.parent}": {exc}'
        ) from exc
    if not stat.S_ISDIR(parent_info.st_mode) or is_reparse_stat(parent_info):
        raise ValueError(
            f'Output parent must be an ordinary directory; received "{destination.parent}".'
        )
    return parent_info


def validate_output_entry_info(
    destination: Path, info: os.stat_result | None, *, force: bool
) -> None:
    if info is None:
        return
    if stat.S_ISLNK(info.st_mode) or is_reparse_stat(info):
        raise ValueError(
            f'Output path must not be a symbolic link or reparse point: "{destination}".'
        )
    if not force:
        raise ValueError(
            f'Output already exists: "{destination}". Use --force to replace it safely.'
        )
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(
            f'--force can replace only an ordinary file; received "{destination}".'
        )


def validate_output_entry(
    destination: Path, *, force: bool
) -> os.stat_result | None:
    try:
        info = os.lstat(destination)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise ValueError(f'Cannot inspect output path "{destination}": {exc}') from exc
    validate_output_entry_info(destination, info, force=force)
    return info


def output_dir_fd_supported() -> bool:
    required = {os.open, os.link, os.rename, os.stat, os.unlink}
    return (
        os.name == "posix"
        and hasattr(os, "O_DIRECTORY")
        and required.issubset(os.supports_dir_fd)
        and os.stat in os.supports_follow_symlinks
        and os.link in os.supports_follow_symlinks
    )


def write_output_descriptor(descriptor: int, rendered: str) -> None:
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor_open = False
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor_open:
            os.close(descriptor)


def write_aggregate_output_with_dir_fd(
    root: Path,
    destination: Path,
    rendered: str,
    *,
    force: bool,
    expected_root_info: os.stat_result | None,
) -> None:
    parent_before = validate_output_parent(
        root, destination, expected_root_info
    )
    parent_flags = os.O_RDONLY | os.O_DIRECTORY
    for flag_name in ("O_CLOEXEC", "O_NOCTTY", "O_NOFOLLOW"):
        parent_flags |= getattr(os, flag_name, 0)
    parent_descriptor = os.open(destination.parent, parent_flags)
    temporary_name: str | None = None
    backup_name: str | None = None
    published = False
    try:
        opened_parent = os.fstat(parent_descriptor)
        parent_after = validate_output_parent(
            root, destination, expected_root_info
        )
        if (
            not os.path.samestat(parent_before, opened_parent)
            or not os.path.samestat(parent_after, opened_parent)
        ):
            raise ValueError("Output parent changed while it was being opened.")

        try:
            destination_info = os.stat(
                destination.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            destination_info = None
        validate_output_entry_info(destination, destination_info, force=force)

        temporary_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        for flag_name in ("O_CLOEXEC", "O_NOCTTY", "O_NOFOLLOW"):
            temporary_flags |= getattr(os, flag_name, 0)
        for _ in range(128):
            candidate_name = f".skill-review-{secrets.token_hex(8)}.tmp"
            try:
                temporary_descriptor = os.open(
                    candidate_name,
                    temporary_flags,
                    0o600,
                    dir_fd=parent_descriptor,
                )
            except FileExistsError:
                continue
            temporary_name = candidate_name
            break
        else:
            raise OSError("Could not allocate a unique temporary output file.")

        write_output_descriptor(temporary_descriptor, rendered)
        parent_current = validate_output_parent(
            root, destination, expected_root_info
        )
        if not os.path.samestat(parent_current, opened_parent):
            raise ValueError("Output parent changed before publication.")
        try:
            destination_info = os.stat(
                destination.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            destination_info = None
        validate_output_entry_info(destination, destination_info, force=force)

        if force and destination_info is not None:
            for _ in range(128):
                candidate_name = f".skill-review-backup-{secrets.token_hex(8)}.tmp"
                try:
                    os.link(
                        destination.name,
                        candidate_name,
                        src_dir_fd=parent_descriptor,
                        dst_dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    continue
                backup_name = candidate_name
                break
            else:
                raise OSError("Could not allocate a unique output backup entry.")

        try:
            if force:
                os.replace(
                    temporary_name,
                    destination.name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
                published = True
            else:
                os.link(
                    temporary_name,
                    destination.name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                published = True
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            temporary_name = None
            parent_final = validate_output_parent(
                root, destination, expected_root_info
            )
            if not os.path.samestat(parent_final, opened_parent):
                raise ValueError("Output parent changed during publication.")
        except BaseException:
            if published:
                if backup_name is not None:
                    os.replace(
                        backup_name,
                        destination.name,
                        src_dir_fd=parent_descriptor,
                        dst_dir_fd=parent_descriptor,
                    )
                    backup_name = None
                else:
                    os.unlink(destination.name, dir_fd=parent_descriptor)
                published = False
            raise
        if backup_name is not None:
            os.unlink(backup_name, dir_fd=parent_descriptor)
            backup_name = None
    finally:
        try:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=parent_descriptor)
                except FileNotFoundError:
                    pass
            if backup_name is not None:
                try:
                    os.unlink(backup_name, dir_fd=parent_descriptor)
                except FileNotFoundError:
                    pass
        finally:
            os.close(parent_descriptor)


def write_aggregate_output_with_paths(
    root: Path,
    destination: Path,
    rendered: str,
    *,
    force: bool,
    expected_root_info: os.stat_result | None,
) -> None:
    validate_output_parent(root, destination, expected_root_info)
    validate_output_entry(destination, force=force)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".skill-review-", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        write_output_descriptor(descriptor, rendered)
        validate_output_parent(root, destination, expected_root_info)
        validate_output_entry(destination, force=force)
        if force:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination, follow_symlinks=False)
            os.unlink(temporary)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_aggregate_output(
    iteration: str,
    output: str,
    rendered: str,
    *,
    force: bool,
    resolved_iteration: Path,
    expected_root_info: os.stat_result | None,
) -> None:
    root, destination = aggregate_output_destination(
        iteration, output, resolved_iteration
    )
    if output_dir_fd_supported():
        write_aggregate_output_with_dir_fd(
            root,
            destination,
            rendered,
            force=force,
            expected_root_info=expected_root_info,
        )
    else:
        write_aggregate_output_with_paths(
            root,
            destination,
            rendered,
            force=force,
            expected_root_info=expected_root_info,
        )


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
        iteration = getattr(args, "iteration", None)
        if iteration is None:
            raise ValueError("File output is supported only for aggregate results.")
        resolved_iteration = Path(
            getattr(args, "_resolved_iteration", result["subject"])
        )
        write_aggregate_output(
            iteration,
            output,
            rendered,
            force=bool(getattr(args, "force", False)),
            resolved_iteration=resolved_iteration,
            expected_root_info=getattr(args, "_iteration_root_info", None),
        )
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
                "Also write the rendered result atomically to FILE inside the "
                "iteration; existing entries require --force and findings remain "
                "subject to --max-findings. Use - for stdout only."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Safely replace an existing ordinary output file; links are rejected.",
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
            resolved_iteration = Path(args.iteration).resolve(strict=True)
            iteration_root_info = os.lstat(resolved_iteration)
            if not stat.S_ISDIR(iteration_root_info.st_mode) or is_reparse_stat(
                iteration_root_info
            ):
                raise ValueError(
                    "Resolved iteration root must be an ordinary directory."
                )
            args._resolved_iteration = resolved_iteration
            args._iteration_root_info = iteration_root_info
            result, status = aggregate(
                resolved_iteration,
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
