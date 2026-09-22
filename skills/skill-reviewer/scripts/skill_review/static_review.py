"""Static package inspection checks for one target skill.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import ast
import os
import re
import stat
from collections import deque
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .frontmatter import parse_frontmatter
from .fs_safety import (
    MAX_DIGEST_FILE_BYTES,
    MAX_RESOURCE_DEPTH,
    MAX_RESOURCE_ENTRIES,
    MAX_TEXT_FILE_BYTES,
    MAX_TOTAL_DIGEST_BYTES,
    MAX_TOTAL_TEXT_BYTES,
    DigestBudget,
    DigestError,
    InventoryIssue,
    InventoryState,
    TextReadBudget,
    TextReadError,
    digest_package_files,
    file_type_name,
    first_link_like_component,
    is_link_like,
    is_reparse_stat,
    iter_files,
    read_bounded_regular_utf8,
    resolve_within,
    windows_filename_issue,
)
from .markdown_scan import (
    MAX_MARKDOWN_BRACKET_DEPTH,
    MAX_MARKDOWN_CODE_SPAN_DELIMITERS,
    MAX_MARKDOWN_CONTAINER_DEPTH,
    MAX_MARKDOWN_LINK_CANDIDATES,
    MAX_MARKDOWN_TARGET_CHARACTERS,
    MarkdownScanLimitError,
    commonmark_path,
    extract_paths,
)
from .report import Finding, add_finding, finalize, line_number

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
CACHE_DIRECTORY_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
CACHE_FILE_NAMES = frozenset({".ds_store", "thumbs.db"})
CACHE_FILE_SUFFIXES = frozenset({".pyc", ".pyo"})


def is_cache_artifact(path: Path, root: Path) -> bool:
    """Return whether path is a regenerated cache artifact, not package content."""
    relative = path.relative_to(root)
    return (
        any(part.lower() in CACHE_DIRECTORY_NAMES for part in relative.parts)
        or relative.name.lower() in CACHE_FILE_NAMES
        or path.suffix.lower() in CACHE_FILE_SUFFIXES
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


def reachable_python_files(
    scripts_root: Path,
    entrypoints: set[Path],
    script_texts: dict[Path, str],
) -> set[Path]:
    """Follow package-local imports from documented Python entrypoints."""
    module_paths: dict[tuple[str, ...], set[Path]] = {}
    package_inits: dict[tuple[str, ...], Path] = {}
    path_modules: dict[Path, tuple[tuple[str, ...], bool]] = {}
    for path in script_texts:
        if path.suffix.lower() != ".py":
            continue
        relative = path.relative_to(scripts_root)
        if relative.name == "__init__.py":
            module = relative.parts[:-1]
            package_inits[module] = path
            is_package = True
        else:
            module = (*relative.parts[:-1], relative.stem)
            is_package = False
        module_paths.setdefault(module, set()).add(path)
        path_modules[path] = (module, is_package)

    reachable = {path for path in entrypoints if path in path_modules}
    queue: deque[Path] = deque(reachable)

    def include_module(module: tuple[str, ...]) -> None:
        targets = set(module_paths.get(module, ()))
        targets.update(
            package_inits[prefix]
            for length in range(1, len(module))
            if (prefix := module[:length]) in package_inits
        )
        for target in targets - reachable:
            reachable.add(target)
            queue.append(target)

    while queue:
        source = queue.popleft()
        try:
            tree = ast.parse(script_texts[source])
        except (SyntaxError, ValueError, MemoryError, RecursionError):
            continue
        source_module, is_package = path_modules[source]
        package = source_module if is_package else source_module[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    include_module(tuple(alias.name.split(".")))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parents = node.level - 1
                    if parents > len(package):
                        continue
                    module = package[: len(package) - parents]
                else:
                    module = ()
                if node.module:
                    module += tuple(node.module.split("."))
                include_module(module)
                for alias in node.names:
                    if alias.name != "*":
                        include_module((*module, alias.name))

    return reachable


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
        "package_files": 0,
        "package_entries_scanned": 0,
        "resource_entries_scanned": 0,
        "package_inventory_complete": False,
        "resource_inventory_complete": False,
        "resource_inventory_scope": "entire_package",
        "package_identity": None,
        "package_digest_scope": "entire_package",
        "package_digest_algorithm": "sha256",
        "package_digest_format": "skill-package-manifest-v1",
        "package_digest_bytes": 0,
        "package_digest_complete": False,
        "text_bytes_read": 0,
        "text_inspection_complete": False,
        "limits": {
            "resource_entries": MAX_RESOURCE_ENTRIES,
            "resource_depth": MAX_RESOURCE_DEPTH,
            "text_file_bytes": MAX_TEXT_FILE_BYTES,
            "total_text_bytes": MAX_TOTAL_TEXT_BYTES,
            "digest_file_bytes": MAX_DIGEST_FILE_BYTES,
            "total_digest_bytes": MAX_TOTAL_DIGEST_BYTES,
            "markdown_link_candidates": MAX_MARKDOWN_LINK_CANDIDATES,
            "markdown_bracket_depth": MAX_MARKDOWN_BRACKET_DEPTH,
            "markdown_code_span_delimiters": MAX_MARKDOWN_CODE_SPAN_DELIMITERS,
            "markdown_container_depth": MAX_MARKDOWN_CONTAINER_DEPTH,
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

    inventory_issues: list[InventoryIssue] = []
    inventory_state = InventoryState()
    package_files = [
        path
        for path in iter_files(root, ".", inventory_issues, inventory_state)
        if not is_cache_artifact(path, root)
    ]
    all_resource_files: dict[str, list[Path]] = {}
    for directory in ("references", "scripts", "assets", "evals"):
        base = root / directory
        try:
            base_info = os.lstat(base)
        except OSError:
            base_info = None
        if base_info is not None and stat.S_ISREG(base_info.st_mode):
            inventory_state.complete = False
            inventory_issues.append(
                InventoryIssue(
                    base,
                    "package.resource_special_file",
                    "Expected a resource directory but found a regular file.",
                )
            )
            files = []
        else:
            files = [
                path for path in package_files if path == base or base in path.parents
            ]
        all_resource_files[directory] = files
        facts["resource_files"][directory] = len(files)

    facts["package_files"] = sum(not is_link_like(path) for path in package_files)
    facts["package_entries_scanned"] = inventory_state.entries_scanned
    facts["resource_entries_scanned"] = inventory_state.entries_scanned
    facts["package_inventory_complete"] = inventory_state.complete
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

    digest_budget = DigestBudget()
    if inventory_state.complete:
        try:
            identity = digest_package_files(root, package_files, digest_budget)
        except DigestError as exc:
            add_finding(
                findings,
                "error",
                exc.code,
                exc.path,
                str(exc),
                "Keep stable ordinary package files within the documented digest limits.",
            )
        else:
            facts["package_identity"] = identity
            facts["package_digest_complete"] = True
    facts["package_digest_bytes"] = digest_budget.bytes_hashed

    instruction_files = [skill_md] + [
        path
        for path in package_files
        if path != skill_md
        and not is_link_like(path)
        and path.suffix.lower() in {".md", ".txt"}
    ]
    file_texts: dict[Path, str] = {skill_md: text}
    text_inspection_complete = inventory_state.complete
    for path in instruction_files[1:]:
        try:
            file_texts[path] = read_bounded_regular_utf8(root, path, text_budget)
        except TextReadError as exc:
            text_inspection_complete = False
            add_text_read_error(findings, path, exc, reported_limits)

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

    script_paths = [
        path for path in all_resource_files["scripts"] if not is_link_like(path)
    ]
    documented_scripts = set(script_paths) & mentioned
    script_texts: dict[Path, str] = {}
    for path in script_paths:
        if path.suffix.lower() not in SCRIPT_SUFFIXES:
            continue
        try:
            script_texts[path] = read_bounded_regular_utf8(root, path, text_budget)
        except TextReadError as exc:
            text_inspection_complete = False
            add_text_read_error(findings, path, exc, reported_limits)

    reachable_scripts = documented_scripts | reachable_python_files(
        root / "scripts", documented_scripts, script_texts
    )
    for path in script_paths:
        relative = path.relative_to(root)
        if (
            integrity_complete
            and text_inspection_complete
            and path not in reachable_scripts
        ):
            add_finding(
                findings,
                "warning",
                "script.unreferenced",
                path,
                "This script is not named by SKILL.md or a reachable reference.",
                "Document when to run it or remove it if it has no caller.",
            )
        if path not in script_texts:
            continue
        script_text = script_texts[path]
        if path in documented_scripts and not script_help_detected(path, script_text):
            add_finding(
                findings,
                "warning",
                "script.help_not_detected",
                path,
                f"No --help interface was detected for {relative}.",
                "If this is an agent-facing CLI, provide concise non-interactive help.",
            )
        if path not in reachable_scripts:
            continue
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
                openai_text = read_bounded_regular_utf8(root, openai_yaml, text_budget)
            except TextReadError as exc:
                text_inspection_complete = False
                add_text_read_error(findings, openai_yaml, exc, reported_limits)
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

    facts["text_bytes_read"] = text_budget.bytes_read
    facts["text_inspection_complete"] = text_inspection_complete
    result = finalize("static", root, facts, findings, max_findings)
    return result, 1 if result["summary"]["errors"] else 0
