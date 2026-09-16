"""Atomic, boundary-checked publication of aggregate results.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import os
import secrets
import stat
import tempfile
from pathlib import Path

from .fs_safety import first_link_like_component, is_reparse_stat


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
