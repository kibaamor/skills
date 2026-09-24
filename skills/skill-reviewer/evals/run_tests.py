#!/usr/bin/env python3
"""Run skill-reviewer tests with fixture skills materialized in isolation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = Path("evals") / "files"
FIXTURE_SKILL_NAME = "SKILL.fixture.md"
ACTIVE_SKILL_NAME = "SKILL.md"


class FixturePreparationError(RuntimeError):
    """Raised when a safe fixture workspace cannot be prepared."""


def _rewrite_eval_paths(skill_root: Path) -> int:
    evals_path = skill_root / "evals" / "evals.json"
    try:
        data = json.loads(evals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixturePreparationError(f"Cannot read {evals_path}: {exc}") from exc

    evals = data.get("evals") if isinstance(data, dict) else None
    if not isinstance(evals, list):
        raise FixturePreparationError(f'{evals_path} must contain an "evals" list')

    rewritten = 0
    for case in evals:
        files = case.get("files") if isinstance(case, dict) else None
        if not isinstance(files, list):
            continue
        for index, value in enumerate(files):
            if not isinstance(value, str) or not (
                value == FIXTURE_SKILL_NAME
                or value.endswith(f"/{FIXTURE_SKILL_NAME}")
            ):
                continue
            files[index] = value[: -len(FIXTURE_SKILL_NAME)] + ACTIVE_SKILL_NAME
            rewritten += 1

    try:
        evals_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise FixturePreparationError(f"Cannot update {evals_path}: {exc}") from exc
    return rewritten


def materialize_fixture_skills(skill_root: Path) -> int:
    """Rename dormant fixture entries and update their staged eval paths."""

    fixture_root = skill_root / FIXTURE_ROOT
    if not fixture_root.is_dir():
        raise FixturePreparationError(f"Fixture directory does not exist: {fixture_root}")

    dormant = sorted(fixture_root.rglob(FIXTURE_SKILL_NAME))
    active = sorted(fixture_root.rglob(ACTIVE_SKILL_NAME))
    if active:
        paths = ", ".join(str(path.relative_to(skill_root)) for path in active)
        raise FixturePreparationError(
            f"Refusing to overwrite active fixture skill entries: {paths}"
        )
    if not dormant:
        raise FixturePreparationError(
            f"No {FIXTURE_SKILL_NAME} files found below {fixture_root}"
        )

    for fixture_path in dormant:
        fixture_path.rename(fixture_path.with_name(ACTIVE_SKILL_NAME))
    _rewrite_eval_paths(skill_root)
    return len(dormant)


def stage_skill_for_tests(source_root: Path, destination: Path) -> int:
    """Copy a skill and materialize its fixture entries in the copy only."""

    source_fixture_root = source_root / FIXTURE_ROOT
    active = sorted(source_fixture_root.rglob(ACTIVE_SKILL_NAME))
    if active:
        paths = ", ".join(str(path.relative_to(source_root)) for path in active)
        raise FixturePreparationError(
            f"Source tree contains active fixture skill entries: {paths}"
        )
    if destination.exists():
        raise FixturePreparationError(f"Staging destination already exists: {destination}")

    try:
        shutil.copytree(
            source_root,
            destination,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"
            ),
        )
    except OSError as exc:
        raise FixturePreparationError(
            f"Cannot stage {source_root} at {destination}: {exc}"
        ) from exc
    return materialize_fixture_skills(destination)


def run_tests(
    pattern: str,
    verbosity: int,
    command: Sequence[str] | None = None,
    *,
    source_root: Path = SKILL_ROOT,
) -> int:
    with tempfile.TemporaryDirectory(prefix="skill-reviewer-tests-") as temporary:
        staged_root = Path(temporary) / source_root.name
        fixture_count = stage_skill_for_tests(source_root, staged_root)
        print(
            f"Materialized {fixture_count} fixture skills in an isolated test copy.",
            file=sys.stderr,
        )
        test_command = list(command or ())
        if not test_command:
            test_command = [
                sys.executable,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-s",
                str(staged_root / "evals"),
                "-p",
                pattern,
            ]
            if verbosity > 1:
                test_command.append("-v")
        environment = os.environ.copy()
        environment["SKILL_REVIEWER_TEST_ROOT"] = str(staged_root)
        try:
            completed = subprocess.run(
                test_command,
                cwd=staged_root,
                env=environment,
                check=False,
            )
        except OSError as exc:
            raise FixturePreparationError(
                f'Cannot run test command "{test_command[0]}": {exc}'
            ) from exc
        return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run tests or an explicit evaluation command in a temporary "
            "skill-reviewer copy where SKILL.fixture.md entries are "
            "materialized as SKILL.md."
        )
    )
    parser.add_argument(
        "-p",
        "--pattern",
        default="test_*.py",
        help="unittest discovery pattern (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="show individual test names",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "optional command to run from the prepared skill root after --; "
            "defaults to unittest discovery"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run_tests(args.pattern, args.verbose, command)
    except FixturePreparationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
