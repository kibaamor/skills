"""Shared module loading and fixtures for the skill-reviewer tests."""

from __future__ import annotations

import errno
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "review_skill.py"
SPEC = importlib.util.spec_from_file_location("review_skill", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot import {SCRIPT}")
REVIEW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)
FS_SAFETY = sys.modules["skill_review.fs_safety"]
MARKDOWN_SCAN = sys.modules["skill_review.markdown_scan"]
STATIC_REVIEW_MODULE = sys.modules["skill_review.static_review"]
OUTPUT_MODULE = sys.modules["skill_review.output"]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def symlink_or_skip(
    test_case: unittest.TestCase,
    link: Path,
    target: Path | str,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except NotImplementedError as exc:
        test_case.skipTest(f"Symbolic links are unavailable: {exc}")
    except OSError as exc:
        if exc.errno in {errno.EPERM, errno.EACCES} or getattr(
            exc, "winerror", None
        ) in {5, 1314}:
            test_case.skipTest(f"Symbolic-link permission is unavailable: {exc}")
        raise


def junction_or_fail(test_case: unittest.TestCase, link: Path, target: Path) -> None:
    if os.name != "nt":
        test_case.fail("Directory junction tests must be guarded as Windows-only")
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        test_case.fail(
            "Could not create a Windows directory junction "
            f'from "{link}" to "{target}" (exit {completed.returncode}).\n'
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    attributes = getattr(os.lstat(link), "st_file_attributes", 0)
    if (
        not attributes & REVIEW.WINDOWS_REPARSE_POINT
        or not REVIEW.is_link_like(link)
    ):
        os.rmdir(link)
        test_case.fail(
            "Created junction was not detected as a reparse point: "
            f"attributes={attributes:#x}"
        )


def skill_text(name: str, extra_frontmatter: str = "", body: str = "Do the task.") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: Use this skill when the fixture task applies.\n"
        f"{extra_frontmatter}"
        "---\n\n"
        f"# Fixture\n\n{body}\n"
    )


def grading(results: list[tuple[str, bool, str]]) -> dict[str, object]:
    assertion_results = [
        {"text": text, "passed": passed, "evidence": evidence}
        for text, passed, evidence in results
    ]
    passed_count = sum(int(item[1]) for item in results)
    total = len(results)
    return {
        "assertion_results": assertion_results,
        "summary": {
            "passed": passed_count,
            "failed": total - passed_count,
            "total": total,
            "pass_rate": passed_count / total,
        },
    }


def trigger_queries() -> list[dict[str, object]]:
    return [
        {"query": "Train yes", "should_trigger": True, "split": "train"},
        {"query": "Train no", "should_trigger": False, "split": "train"},
        {
            "query": "Validation yes",
            "should_trigger": True,
            "split": "validation",
        },
        {
            "query": "Validation no",
            "should_trigger": False,
            "split": "validation",
        },
    ]
