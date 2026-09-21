"""Package-boundary filesystem inspection for untrusted skill data.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

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


MAX_RESOURCE_ENTRIES = 4096
MAX_RESOURCE_DEPTH = 32
MAX_TEXT_FILE_BYTES = 1 << 20
MAX_TOTAL_TEXT_BYTES = 8 << 20


READ_CHUNK_BYTES = 64 << 10


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

                    if stat.S_ISLNK(entry_info.st_mode) or is_reparse_stat(entry_info):
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
    return resolved_path, skill_root, None
