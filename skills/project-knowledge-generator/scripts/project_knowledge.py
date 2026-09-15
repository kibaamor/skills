#!/usr/bin/env python3
"""Read-only repository inventory and project-knowledge validation.

The inventory command reports repository facts.  The validate command checks
local Markdown navigation and, when PyYAML is available, source-linked YAML
frontmatter.  Neither command modifies the target repository.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = 2
DEFAULT_MAX_FILES = 100_000
MAX_MARKDOWN_BYTES = 5 * 1024 * 1024
NON_GIT_EXCLUDED_DIRS = {
    ".next",
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
    "venv",
}
MANIFEST_NAMES = {
    "Cargo.toml",
    "Gemfile",
    "Makefile",
    "Package.swift",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "go.mod",
    "meson.build",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
}
LOCKFILE_NAMES = {
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
    "go.sum",
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}
INSTRUCTION_NAMES = {"AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"}
TEST_DIR_NAMES = {"__tests__", "spec", "specs", "test", "tests"}
SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "STALE": 2}
ENTRY_DOCUMENT = "README.md"
REQUIRED_ROOT_DOCUMENTS = ("CONTEXT.md", "ARCHITECTURE.md")
ALLOWED_METADATA_FIELDS = frozenset(
    {
        "id",
        "summary",
        "read_when",
        "source_paths",
        "source_symbols",
        "tests",
        "verified_commit",
        "owner",
    }
)


class OperationalError(RuntimeError):
    """The requested check could not be performed reliably."""


class UnsafePathError(ValueError):
    """A repository-relative path escaped its allowed root."""


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str
    line: Optional[int] = None

    def sort_key(self) -> tuple[Any, ...]:
        return (
            SEVERITY_ORDER[self.severity],
            self.code,
            self.path,
            self.line or 0,
            self.message,
        )


@dataclass
class Document:
    path: Path
    repo_path: str
    knowledge_path: str
    text: str
    metadata: Optional[dict[str, Any]] = None
    source_specs: Optional[list[str]] = None
    test_specs: Optional[list[str]] = None
    verified_commit: Optional[str] = None


def run_process(args: Sequence[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OperationalError(f"required executable not found: {args[0]}") from exc
    except OSError as exc:
        raise OperationalError(f"could not run {args[0]}: {exc}") from exc


def git_result(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return run_process(["git", "-C", str(root), *args])


def is_git_repository(root: Path) -> bool:
    try:
        result = git_result(root, ["rev-parse", "--is-inside-work-tree"])
    except OperationalError:
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


def git_text(root: Path, args: Sequence[str]) -> Optional[str]:
    result = git_result(root, args)
    if result.returncode != 0:
        return None
    return os.fsdecode(result.stdout).strip() or None


def within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


def resolve_inside(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    if not within(resolved, root):
        raise UnsafePathError(f"{label} escapes repository root")
    return resolved


def normalize_relative_spec(raw: str, label: str) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"{label} must be a string")
    value = raw.strip()
    if value.startswith("./"):
        value = value[2:]
    if not value or "\x00" in value:
        raise ValueError(f"{label} is empty or contains NUL")
    if "\\" in value:
        raise ValueError(f"{label} must use POSIX '/' separators")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise UnsafePathError(f"{label} must be repository-relative")
    if any(part == ".." for part in value.split("/")):
        raise UnsafePathError(f"{label} escapes repository root")
    if "[" in value or "]" in value:
        raise ValueError(f"{label} uses unsupported glob syntax; use *, **, or ?")
    return value.rstrip("/") or "."


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile the supported POSIX *, **, and ? path glob subset."""
    out: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    out.append("(?:.*/)?")
                    index += 1
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def spec_matches_path(spec: str, candidate: str, root: Optional[Path] = None) -> bool:
    if "*" in spec or "?" in spec:
        return bool(glob_regex(spec).match(candidate))
    if candidate == spec:
        return True
    # Treat an exact declaration as a possible directory prefix even when the
    # directory was deleted and can no longer be inspected in the work tree.
    if candidate.startswith(spec.rstrip("/") + "/"):
        return True
    if root is not None:
        target = root / spec
        try:
            if target.is_dir():
                return candidate.startswith(spec.rstrip("/") + "/")
        except OSError:
            pass
    return False


def excluded_path(relative: str, patterns: Sequence[str]) -> bool:
    for raw in patterns:
        spec = normalize_relative_spec(raw, "exclude pattern")
        if spec_matches_path(spec, relative):
            return True
        if "*" not in spec and "?" not in spec and relative.startswith(spec + "/"):
            return True
    return False


def git_inventory_paths(root: Path, include_untracked: bool) -> list[str]:
    args = ["ls-files", "-z", "--cached"]
    if include_untracked:
        args.extend(["--others", "--exclude-standard"])
    args.extend(["--", "."])
    result = git_result(root, args)
    if result.returncode != 0:
        message = os.fsdecode(result.stderr).strip()
        raise OperationalError(f"git ls-files failed: {message or 'unknown error'}")
    return sorted({os.fsdecode(item) for item in result.stdout.split(b"\0") if item})


def walk_inventory_paths(root: Path, excludes: Sequence[str], max_files: int) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    skipped_names: set[str] = set()
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        kept_dirs: list[str] = []
        for name in sorted(dirnames):
            candidate = directory_path / name
            relative = candidate.relative_to(root).as_posix()
            try:
                is_link = candidate.is_symlink()
            except OSError:
                is_link = False
            if is_link:
                if not excluded_path(relative, excludes):
                    paths.append(relative)
                continue
            if name in NON_GIT_EXCLUDED_DIRS or excluded_path(relative, excludes):
                skipped_names.add(name)
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in sorted(filenames):
            relative = (directory_path / name).relative_to(root).as_posix()
            if not excluded_path(relative, excludes):
                paths.append(relative)
                if len(paths) > max_files:
                    raise OperationalError(
                        f"inventory exceeds --max-files={max_files}; narrow the root or add --exclude"
                    )
    return sorted(set(paths)), sorted(skipped_names)


def file_record(root: Path, relative: str) -> Optional[dict[str, Any]]:
    candidate = root / relative
    try:
        info = candidate.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode):
        kind = "symlink"
    elif stat.S_ISREG(info.st_mode):
        kind = "file"
    elif stat.S_ISDIR(info.st_mode):
        kind = "directory"
    else:
        kind = "other"
    suffix = Path(relative).suffix.lower() or "<none>"
    return {"path": relative, "kind": kind, "bytes": info.st_size, "suffix": suffix}


def build_inventory(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve(strict=False)
    if not root.is_dir():
        raise OperationalError(f"repository root is not a directory: {args.root}")
    if args.max_files < 1:
        raise OperationalError("--max-files must be positive")

    git_repository = is_git_repository(root)
    skipped_names: list[str] = []
    if git_repository:
        candidates = git_inventory_paths(root, args.include_untracked)
        candidates = [path for path in candidates if not excluded_path(path, args.exclude)]
        scope = "git-tracked-and-untracked" if args.include_untracked else "git-tracked"
    else:
        candidates, skipped_names = walk_inventory_paths(root, args.exclude, args.max_files)
        scope = "filesystem-fallback"
    if len(candidates) > args.max_files:
        raise OperationalError(
            f"inventory has {len(candidates)} paths, exceeding --max-files={args.max_files}"
        )

    records = [record for path in candidates if (record := file_record(root, path))]
    records.sort(key=lambda item: item["path"])
    suffixes = Counter(item["suffix"] for item in records if item["kind"] == "file")
    top_levels = Counter(item["path"].split("/", 1)[0] for item in records)
    all_paths = [item["path"] for item in records]
    test_roots = sorted(
        {
            "/".join(path.split("/")[: index + 1])
            for path in all_paths
            for index, part in enumerate(path.split("/")[:-1])
            if part.lower() in TEST_DIR_NAMES
        }
    )
    ci_files = sorted(
        path
        for path in all_paths
        if path == ".gitlab-ci.yml"
        or path.startswith(".github/workflows/")
        or path.startswith(".circleci/")
        or path.startswith(".buildkite/")
    )
    head = git_text(root, ["rev-parse", "--verify", "HEAD"]) if git_repository else None
    dirty = None
    if git_repository:
        status_args = ["status", "--porcelain=v1", "-z"]
        status_args.append("--untracked-files=normal" if args.include_untracked else "--untracked-files=no")
        result = git_result(root, status_args)
        dirty = bool(result.stdout) if result.returncode == 0 else None

    warnings: list[dict[str, str]] = []
    if not git_repository:
        warnings.append(
            {
                "code": "FILESYSTEM_FALLBACK",
                "message": "Git metadata was unavailable; filesystem fallback exclusions were applied.",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "inventory",
        "scope": scope,
        "vcs": {"kind": "git" if git_repository else "none", "head": head, "dirty": dirty},
        "summary": {
            "paths": len(records),
            "regular_files": sum(item["kind"] == "file" for item in records),
            "symlinks": sum(item["kind"] == "symlink" for item in records),
            "bytes": sum(item["bytes"] for item in records),
        },
        "top_level": [{"path": key, "count": value} for key, value in sorted(top_levels.items())],
        "suffixes": [{"suffix": key, "count": value} for key, value in sorted(suffixes.items())],
        "signals": {
            "manifests": sorted(path for path in all_paths if Path(path).name in MANIFEST_NAMES),
            "lockfiles": sorted(path for path in all_paths if Path(path).name in LOCKFILE_NAMES),
            "ci": ci_files,
            "test_roots": test_roots,
            "instructions": sorted(path for path in all_paths if Path(path).name in INSTRUCTION_NAMES),
        },
        "fallback_excluded_names": skipped_names,
        "files": records,
        "warnings": warnings,
    }


def inventory_text(report: dict[str, Any]) -> str:
    vcs = report["vcs"]
    lines = [
        f"inventory schema={report['schema_version']}",
        f"scope: {report['scope']}",
        f"vcs: {vcs['kind']} head={vcs['head'] or '-'} dirty={str(vcs['dirty']).lower() if vcs['dirty'] is not None else '-'}",
        "files: {regular_files} regular, {symlinks} symlinks, {bytes} bytes".format(**report["summary"]),
        "top-level:",
    ]
    lines.extend(f"  {item['path']}: {item['count']}" for item in report["top_level"])
    lines.append("suffixes:")
    lines.extend(f"  {item['suffix']}: {item['count']}" for item in report["suffixes"])
    lines.append("signals:")
    for name in ("manifests", "lockfiles", "ci", "test_roots", "instructions"):
        values = report["signals"][name]
        lines.append(f"  {name}: {', '.join(values) if values else '-'}")
    for warning in report["warnings"]:
        lines.append(f"WARNING {warning['code']}: {warning['message']}")
    return "\n".join(lines) + "\n"


def markdown_files(directory: Path) -> list[Path]:
    result: list[Path] = []
    for current, dirnames, filenames in os.walk(directory, topdown=True, followlinks=False):
        dirnames[:] = sorted(
            name for name in dirnames if not (Path(current) / name).is_symlink()
        )
        for name in sorted(filenames):
            candidate = Path(current) / name
            if name.lower().endswith(".md") and not candidate.is_symlink():
                result.append(candidate)
    return sorted(result, key=lambda item: item.as_posix())


def read_document(path: Path, root: Path, knowledge_dir: Path) -> Document:
    text = read_markdown_text(path)
    return Document(
        path=path,
        repo_path=path.relative_to(root).as_posix(),
        knowledge_path=path.relative_to(knowledge_dir).as_posix(),
        text=text,
    )


def read_markdown_text(path: Path) -> str:
    try:
        size = path.lstat().st_size
    except OSError as exc:
        raise OperationalError(f"cannot stat {path}: {exc}") from exc
    if size > MAX_MARKDOWN_BYTES:
        raise OperationalError(f"Markdown file exceeds {MAX_MARKDOWN_BYTES} bytes: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OperationalError(f"cannot read UTF-8 Markdown file {path}: {exc}") from exc


def mask_inline_code(line: str) -> str:
    chars = list(line)
    index = 0
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        end_run = index
        while end_run < len(line) and line[end_run] == "`":
            end_run += 1
        marker = line[index:end_run]
        closing = line.find(marker, end_run)
        if closing < 0:
            index = end_run
            continue
        for masked in range(index, closing + len(marker)):
            chars[masked] = " "
        index = closing + len(marker)
    return "".join(chars)


INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)")
REFERENCE_DEFINITION_RE = re.compile(r"^[ ]{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)")
REFERENCE_USE_RE = re.compile(r"!?\[[^\]]+\]\[([^\]]*)\]")
FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
ATX_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}(?:[ \t]+|$)(.*)$")
SETEXT_HEADING_RE = re.compile(r"^[ ]{0,3}(?:=+|-+)[ \t]*$")
INLINE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
INLINE_HEADING_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]*>")


def markdown_targets(text: str) -> list[tuple[int, str]]:
    visible: list[tuple[int, str]] = []
    definitions: dict[str, tuple[int, str]] = {}
    fence_char: Optional[str] = None
    fence_length = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        fence = FENCE_RE.match(raw)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char, fence_length = None, 0
            continue
        if fence_char is not None:
            continue
        line = mask_inline_code(raw)
        definition = REFERENCE_DEFINITION_RE.match(line)
        if definition:
            definitions[definition.group(1).strip().casefold()] = (
                line_number,
                definition.group(2),
            )
            continue
        visible.append((line_number, line))

    targets: list[tuple[int, str]] = []
    for line_number, line in visible:
        targets.extend((line_number, match.group(1)) for match in INLINE_LINK_RE.finditer(line))
        for match in REFERENCE_USE_RE.finditer(line):
            key = (match.group(1) or match.group(0).split("]", 1)[0].lstrip("![")).strip().casefold()
            if key in definitions:
                targets.append((line_number, definitions[key][1]))
    return targets


def local_link_target(raw: str) -> Optional[tuple[str, Optional[str]]]:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or target.startswith("//"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme:
        return None
    path = unquote(parsed.path)
    if path.startswith("/"):
        return None
    fragment = unquote(parsed.fragment) if parsed.fragment else None
    if not path and fragment is None:
        return None
    return path, fragment


def heading_slug(text: str) -> str:
    value = html.unescape(text.strip())
    value = INLINE_IMAGE_RE.sub(r"\1", value)
    value = INLINE_HEADING_LINK_RE.sub(r"\1", value)
    value = HTML_TAG_RE.sub("", value)
    value = value.replace("`", "").replace("\\", "")
    value = value.lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"\s", "-", value)


def markdown_heading_anchors(text: str) -> set[str]:
    lines = text.splitlines()
    frontmatter_end = -1
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                frontmatter_end = index
                break
        else:
            frontmatter_end = len(lines) - 1

    headings: list[str] = []
    fence_char: Optional[str] = None
    fence_length = 0
    previous_line: Optional[str] = None
    for index, raw in enumerate(lines):
        if index <= frontmatter_end:
            continue
        fence = FENCE_RE.match(raw)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char, fence_length = None, 0
            previous_line = None
            continue
        if fence_char is not None:
            continue

        atx = ATX_HEADING_RE.match(raw)
        if atx:
            heading = re.sub(r"[ \t]+#+[ \t]*$", "", atx.group(1)).strip()
            headings.append(heading)
            previous_line = None
            continue
        if SETEXT_HEADING_RE.match(raw) and previous_line and previous_line.strip():
            headings.append(previous_line.strip())
            previous_line = None
            continue
        previous_line = raw if raw.strip() else None

    anchors: set[str] = set()
    for heading in headings:
        base = heading_slug(heading)
        if not base:
            continue
        anchor = base
        suffix = 1
        while anchor in anchors:
            anchor = f"{base}-{suffix}"
            suffix += 1
        anchors.add(anchor)
    return anchors


def extract_frontmatter(text: str) -> tuple[Optional[str], bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, False
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), True
    return None, True


def validate_string_list(
    metadata: dict[str, Any],
    key: str,
    document: Document,
    findings: list[Finding],
    *,
    require_nonempty: bool = False,
) -> Optional[list[str]]:
    if key not in metadata:
        return None
    value = metadata[key]
    if (
        not isinstance(value, list)
        or (require_nonempty and not value)
        or not all(isinstance(item, str) for item in value)
    ):
        qualifier = "a non-empty list of strings" if require_nonempty else "a list of strings"
        findings.append(
            Finding(
                "ERROR",
                "INVALID_METADATA_TYPE",
                document.repo_path,
                f"{key} must be {qualifier}",
                1,
            )
        )
        return None
    if any(not item.strip() for item in value):
        code = (
            "EMPTY_METADATA_PATH"
            if key in {"source_paths", "tests"}
            else "EMPTY_METADATA_VALUE"
        )
        findings.append(
            Finding(
                "ERROR",
                code,
                document.repo_path,
                f"{key} contains an empty string",
                1,
            )
        )
        return None
    return [item.strip() for item in value]


def validate_nonempty_string(
    metadata: dict[str, Any],
    key: str,
    document: Document,
    findings: list[Finding],
    code: str,
) -> Optional[str]:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, str) or not value.strip():
        findings.append(
            Finding(
                "ERROR",
                code,
                document.repo_path,
                f"{key} must be a non-empty string",
                1,
            )
        )
        return None
    return value.strip()


def iter_under(path: Path, limit: int = DEFAULT_MAX_FILES) -> Iterator[Path]:
    count = 0
    if path.exists() or path.is_symlink():
        yield path
        count += 1
    if not path.is_dir() or path.is_symlink():
        return
    for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in {".git", ".hg", ".svn"})
        for name in [*dirnames, *sorted(filenames)]:
            count += 1
            if count > limit:
                raise OperationalError(f"path glob scan exceeds {limit} entries under {path}")
            yield Path(current) / name


def spec_has_match(root: Path, spec: str) -> bool:
    normalized = normalize_relative_spec(spec, "metadata path")
    if "*" not in normalized and "?" not in normalized:
        target = root / normalized
        resolve_inside(root, target, normalized)
        return target.exists() or target.is_symlink()
    components = normalized.split("/")
    fixed: list[str] = []
    for component in components:
        if "*" in component or "?" in component:
            break
        fixed.append(component)
    base = root.joinpath(*fixed) if fixed else root
    resolve_inside(root, base, normalized)
    matcher = glob_regex(normalized)
    for candidate in iter_under(base):
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError:
            continue
        if matcher.match(relative):
            resolve_inside(root, candidate, normalized)
            return True
    return False


def resolve_revision(root: Path, revision: str) -> Optional[str]:
    if not revision or revision.startswith("-") or "\x00" in revision or any(char.isspace() for char in revision):
        return None
    result = git_result(root, ["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"])
    return os.fsdecode(result.stdout).strip() if result.returncode == 0 else None


def changed_paths(root: Path, baseline: str) -> set[str]:
    diff = git_result(root, ["diff", "--name-only", "-z", "--relative", baseline, "--", "."])
    if diff.returncode != 0:
        message = os.fsdecode(diff.stderr).strip()
        raise OperationalError(f"git diff failed for {baseline}: {message or 'unknown error'}")
    untracked = git_result(root, ["ls-files", "-z", "--others", "--exclude-standard", "--", "."])
    if untracked.returncode != 0:
        message = os.fsdecode(untracked.stderr).strip()
        raise OperationalError(f"git ls-files failed: {message or 'unknown error'}")
    return {
        os.fsdecode(item)
        for item in [*diff.stdout.split(b"\0"), *untracked.stdout.split(b"\0")]
        if item
    }


def load_yaml() -> tuple[Optional[Any], Optional[str]]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, "PyYAML is not installed"
    return yaml, None


def build_validation(args: argparse.Namespace) -> tuple[dict[str, Any], list[Finding]]:
    root = Path(args.root).resolve(strict=False)
    if not root.is_dir():
        raise OperationalError(f"repository root is not a directory: {args.root}")
    requested = Path(args.knowledge_dir)
    knowledge_dir = requested.resolve(strict=False) if requested.is_absolute() else (root / requested).resolve(strict=False)
    try:
        resolve_inside(root, knowledge_dir, "knowledge directory")
    except UnsafePathError as exc:
        raise OperationalError(str(exc)) from exc

    findings: list[Finding] = []
    if not knowledge_dir.is_dir():
        findings.append(Finding("ERROR", "KNOWLEDGE_DIR_MISSING", Path(args.knowledge_dir).as_posix(), "knowledge directory does not exist"))
        report = validation_report(args, [], "unavailable", findings)
        return report, findings

    files = markdown_files(knowledge_dir)
    documents = [read_document(path, root, knowledge_dir) for path in files]
    document_by_path = {document.path.resolve(strict=False): document for document in documents}
    document_by_knowledge_path = {document.knowledge_path: document for document in documents}
    if not documents:
        findings.append(Finding("ERROR", "NO_MARKDOWN_DOCUMENTS", knowledge_dir.relative_to(root).as_posix(), "knowledge directory contains no Markdown documents"))

    entry = (knowledge_dir / ENTRY_DOCUMENT).resolve(strict=False)
    if entry not in document_by_path:
        findings.append(
            Finding(
                "ERROR",
                "ENTRY_MISSING",
                ENTRY_DOCUMENT,
                f"knowledge entry must be the top-level {ENTRY_DOCUMENT} file",
            )
        )

    for required_name in REQUIRED_ROOT_DOCUMENTS:
        if required_name not in document_by_knowledge_path:
            required_path = knowledge_dir / required_name
            findings.append(
                Finding(
                    "ERROR",
                    "REQUIRED_DOCUMENT_MISSING",
                    required_path.relative_to(root).as_posix(),
                    f"project knowledge requires a top-level {required_name} file",
                )
            )

    anchors_by_path = {
        document.path.resolve(strict=False): markdown_heading_anchors(document.text)
        for document in documents
    }
    adjacency: dict[Path, set[Path]] = defaultdict(set)
    for document in documents:
        for line, raw_target in markdown_targets(document.text):
            target = local_link_target(raw_target)
            if target is None:
                continue
            target_path, fragment = target
            candidate = (
                document.path.resolve(strict=False)
                if not target_path
                else (document.path.parent / target_path).resolve(strict=False)
            )
            if not within(candidate, root):
                findings.append(Finding("ERROR", "LINK_ESCAPES_REPOSITORY", document.repo_path, f"local link escapes repository: {raw_target}", line))
                continue
            if not candidate.exists():
                findings.append(Finding("ERROR", "BROKEN_LOCAL_LINK", document.repo_path, f"local link target does not exist: {raw_target}", line))
                continue
            target_anchors = anchors_by_path.get(candidate)
            if (
                fragment is not None
                and target_anchors is None
                and candidate.is_file()
                and candidate.suffix.lower() == ".md"
            ):
                target_anchors = markdown_heading_anchors(read_markdown_text(candidate))
                anchors_by_path[candidate] = target_anchors
            if fragment is not None and target_anchors is not None and fragment not in target_anchors:
                findings.append(
                    Finding(
                        "ERROR",
                        "BROKEN_HEADING_ANCHOR",
                        document.repo_path,
                        f"Markdown heading anchor does not exist: {raw_target}",
                        line,
                    )
                )
            if candidate in document_by_path:
                adjacency[document.path.resolve(strict=False)].add(candidate)

    if entry in document_by_path:
        direct_entry_targets = adjacency.get(entry, set())
        for required_name in REQUIRED_ROOT_DOCUMENTS:
            required_document = document_by_knowledge_path.get(required_name)
            if (
                required_document is not None
                and required_document.path.resolve(strict=False) not in direct_entry_targets
            ):
                findings.append(
                    Finding(
                        "ERROR",
                        "REQUIRED_DOCUMENT_NOT_LINKED",
                        document_by_path[entry].repo_path,
                        f"knowledge entry must link directly to {required_name}",
                    )
                )

    if entry in document_by_path:
        reachable = {entry}
        queue: deque[Path] = deque([entry])
        while queue:
            current = queue.popleft()
            for target in sorted(adjacency.get(current, set()), key=lambda item: item.as_posix()):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        for document in documents:
            resolved = document.path.resolve(strict=False)
            if resolved not in reachable and not document.knowledge_path.startswith("generated/"):
                findings.append(Finding("WARNING", "ORPHAN_DOCUMENT", document.repo_path, f"document is not reachable from {ENTRY_DOCUMENT}"))

    yaml_module, yaml_error = load_yaml()
    metadata_state = "enabled" if yaml_module is not None else "skipped"
    if yaml_module is None:
        if args.require_yaml:
            raise OperationalError(f"metadata validation requires PyYAML: {yaml_error}")
        findings.append(Finding("WARNING", "YAML_CHECKS_SKIPPED", knowledge_dir.relative_to(root).as_posix(), f"{yaml_error}; frontmatter, source paths, and stale candidates were not checked"))
    else:
        identifiers: dict[str, str] = {}
        yaml_error_type = getattr(yaml_module, "YAMLError", Exception)
        for document in documents:
            frontmatter, declared = extract_frontmatter(document.text)
            navigation_doc = document.path.name.lower() in {"readme.md", "index.md"}
            generated_doc = document.knowledge_path.startswith("generated/")
            decision_doc = document.knowledge_path.startswith("decisions/")
            managed_topic = not navigation_doc and not generated_doc and not decision_doc
            metadata_required = managed_topic
            if declared and frontmatter is None:
                findings.append(Finding("ERROR", "UNTERMINATED_FRONTMATTER", document.repo_path, "YAML frontmatter has no closing delimiter", 1))
                continue
            if frontmatter is None:
                if metadata_required:
                    findings.append(Finding("ERROR", "FRONTMATTER_REQUIRED", document.repo_path, "project knowledge document requires YAML frontmatter", 1))
                continue
            try:
                metadata = yaml_module.safe_load(frontmatter) or {}
            except yaml_error_type as exc:
                findings.append(Finding("ERROR", "INVALID_YAML", document.repo_path, f"invalid YAML frontmatter: {exc}", 1))
                continue
            if not isinstance(metadata, dict):
                findings.append(Finding("ERROR", "INVALID_FRONTMATTER", document.repo_path, "frontmatter must be a mapping", 1))
                continue
            document.metadata = metadata
            unsupported_fields = sorted(
                (repr(key) if not isinstance(key, str) else key)
                for key in metadata
                if not isinstance(key, str) or key not in ALLOWED_METADATA_FIELDS
            )
            if unsupported_fields:
                preview = ", ".join(unsupported_fields[:10])
                if len(unsupported_fields) > 10:
                    preview += f", ... (+{len(unsupported_fields) - 10})"
                findings.append(
                    Finding(
                        "ERROR",
                        "UNSUPPORTED_METADATA_FIELD",
                        document.repo_path,
                        f"frontmatter contains unsupported fields: {preview}",
                        1,
                    )
                )
            if metadata_required:
                if "id" not in metadata:
                    findings.append(Finding("ERROR", "ID_REQUIRED", document.repo_path, "project knowledge document requires a non-empty id", 1))
                if "summary" not in metadata:
                    findings.append(Finding("ERROR", "SUMMARY_REQUIRED", document.repo_path, "project knowledge document requires a non-empty summary", 1))
                if "source_paths" not in metadata:
                    findings.append(Finding("ERROR", "SOURCE_PATHS_REQUIRED", document.repo_path, "project knowledge document requires a non-empty source_paths list", 1))
            identifier = metadata.get("id")
            if identifier is not None:
                if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", identifier):
                    findings.append(Finding("ERROR", "INVALID_ID", document.repo_path, "id must be a lowercase dot/dash/underscore identifier", 1))
                elif identifier in identifiers:
                    findings.append(Finding("ERROR", "DUPLICATE_ID", document.repo_path, f"id duplicates {identifiers[identifier]}: {identifier}", 1))
                else:
                    identifiers[identifier] = document.repo_path
            validate_nonempty_string(
                metadata, "summary", document, findings, "INVALID_SUMMARY"
            )
            validate_string_list(
                metadata, "read_when", document, findings, require_nonempty=True
            )
            document.source_specs = validate_string_list(
                metadata, "source_paths", document, findings, require_nonempty=True
            )
            validate_string_list(
                metadata, "source_symbols", document, findings, require_nonempty=True
            )
            document.test_specs = validate_string_list(
                metadata, "tests", document, findings, require_nonempty=True
            )
            document.verified_commit = validate_nonempty_string(
                metadata,
                "verified_commit",
                document,
                findings,
                "INVALID_VERIFIED_COMMIT",
            )
            validate_nonempty_string(
                metadata, "owner", document, findings, "INVALID_OWNER"
            )
            for field, specs in (("source_paths", document.source_specs), ("tests", document.test_specs)):
                for index, spec in enumerate(specs or []):
                    try:
                        exists = spec_has_match(root, spec)
                    except (ValueError, UnsafePathError) as exc:
                        findings.append(Finding("ERROR", "UNSAFE_METADATA_PATH", document.repo_path, f"{field}[{index}]: {exc}", 1))
                        continue
                    if not exists:
                        findings.append(Finding("ERROR", "METADATA_PATH_MISSING", document.repo_path, f"{field}[{index}] matches nothing: {spec}", 1))

        git_repository = is_git_repository(root)
        if args.since and not git_repository:
            raise OperationalError("--since requires a Git work tree")
        explicit_baseline: Optional[str] = None
        if args.since:
            explicit_baseline = resolve_revision(root, args.since)
            if explicit_baseline is None:
                raise OperationalError(f"could not resolve --since revision: {args.since}")
        changes_by_baseline: dict[str, set[str]] = {}
        for document in documents:
            specs = [*(document.source_specs or []), *(document.test_specs or [])]
            if not specs:
                continue
            normalized_specs: list[str] = []
            for spec in specs:
                try:
                    normalized_specs.append(normalize_relative_spec(spec, "metadata path"))
                except (ValueError, UnsafePathError):
                    # The invalid declaration already has a precise ERROR
                    # finding; it must not turn stale analysis into exit 2.
                    continue
            if not normalized_specs:
                continue
            baseline_value = explicit_baseline
            if baseline_value is None and document.verified_commit:
                if not git_repository:
                    findings.append(Finding("WARNING", "BASELINE_UNAVAILABLE", document.repo_path, "verified_commit cannot be checked outside a Git work tree"))
                    continue
                baseline_value = resolve_revision(root, document.verified_commit)
                if baseline_value is None:
                    findings.append(Finding("WARNING", "BASELINE_UNRESOLVED", document.repo_path, f"verified_commit cannot be resolved: {document.verified_commit}"))
                    continue
            if baseline_value is None:
                continue
            if baseline_value not in changes_by_baseline:
                changes_by_baseline[baseline_value] = changed_paths(root, baseline_value)
            matched = sorted(
                path
                for path in changes_by_baseline[baseline_value]
                if any(spec_matches_path(spec, path, root) for spec in normalized_specs)
            )
            if matched:
                preview = ", ".join(matched[:5])
                if len(matched) > 5:
                    preview += f", ... (+{len(matched) - 5})"
                findings.append(Finding("STALE", "STALE_CANDIDATE", document.repo_path, f"{len(matched)} declared source/test paths changed since {baseline_value[:12]}: {preview}"))

    findings.sort(key=Finding.sort_key)
    report = validation_report(args, documents, metadata_state, findings)
    return report, findings


def validation_report(
    args: argparse.Namespace,
    documents: Sequence[Document],
    metadata_state: str,
    findings: Sequence[Finding],
) -> dict[str, Any]:
    counts = Counter(finding.severity.lower() for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "validate",
        "knowledge_dir": Path(args.knowledge_dir).as_posix(),
        "documents": len(documents),
        "metadata_checks": metadata_state,
        "counts": {"errors": counts["error"], "warnings": counts["warning"], "stale": counts["stale"]},
        "findings": [asdict(finding) for finding in findings],
    }


def validation_text(report: dict[str, Any]) -> str:
    lines = [
        f"validation schema={report['schema_version']}",
        f"knowledge-dir: {report['knowledge_dir']}",
        f"documents: {report['documents']}",
        f"metadata-checks: {report['metadata_checks']}",
    ]
    for finding in report["findings"]:
        location = finding["path"]
        if finding["line"] is not None:
            location += f":{finding['line']}"
        lines.append(f"{finding['severity']} {finding['code']} {location}: {finding['message']}")
    counts = report["counts"]
    lines.append(f"summary: {counts['errors']} errors, {counts['warnings']} warnings, {counts['stale']} stale candidates")
    return "\n".join(lines) + "\n"


def emit(report: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        sys.stdout.write(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    elif report.get("command") == "inventory":
        sys.stdout.write(inventory_text(report))
    else:
        sys.stdout.write(validation_text(report))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="report deterministic repository facts")
    inventory.add_argument("--root", default=".", help="project root (default: current directory)")
    inventory.add_argument("--include-untracked", action="store_true", help="include non-ignored Git untracked files")
    inventory.add_argument("--exclude", action="append", default=[], metavar="PATTERN", help="exclude a repository-relative *, **, or ? path pattern")
    inventory.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    inventory.add_argument("--format", choices=("text", "json"), default="text")

    validate = subparsers.add_parser(
        "validate",
        help="validate project-knowledge navigation and source links",
        description=(
            "Validate a project-knowledge directory whose fixed entrypoint is "
            f"the top-level {ENTRY_DOCUMENT} file."
        ),
    )
    validate.add_argument("--root", default=".", help="project root (default: current directory)")
    validate.add_argument("--knowledge-dir", default="docs/project-knowledge", help="repository-relative knowledge directory")
    validate.add_argument("--entry", dest="unsupported_entry", help=argparse.SUPPRESS)
    validate.add_argument("--since", help="Git revision used to report source-linked stale candidates")
    validate.add_argument("--require-yaml", action="store_true", help="exit 2 instead of degrading when PyYAML is unavailable")
    validate.add_argument("--fail-on-warning", action="store_true")
    validate.add_argument("--fail-on-stale", action="store_true")
    validate.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            report = build_inventory(args)
            emit(report, args.format)
            return 0
        if args.unsupported_entry is not None:
            raise OperationalError(
                f"--entry is unsupported; the knowledge entry is fixed at {ENTRY_DOCUMENT}"
            )
        report, findings = build_validation(args)
        emit(report, args.format)
        if any(finding.severity == "ERROR" for finding in findings):
            return 1
        if args.fail_on_warning and any(finding.severity == "WARNING" for finding in findings):
            return 1
        if args.fail_on_stale and any(finding.severity == "STALE" for finding in findings):
            return 1
        return 0
    except (OperationalError, UnsafePathError, ValueError) as exc:
        if getattr(args, "format", "text") == "json":
            sys.stdout.write(json.dumps({"schema_version": SCHEMA_VERSION, "command": args.command, "operational_error": str(exc)}, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        else:
            sys.stderr.write(f"operational error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
