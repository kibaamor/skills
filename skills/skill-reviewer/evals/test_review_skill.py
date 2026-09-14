#!/usr/bin/env python3
"""Regression tests for the bundled deterministic reviewer."""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "review_skill.py"
SPEC = importlib.util.spec_from_file_location("review_skill", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot import {SCRIPT}")
REVIEW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)


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


class StaticReviewTests(unittest.TestCase):
    def test_accepts_nested_frontmatter_and_ignores_fenced_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "nested-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "nested-skill",
                    "metadata:\n  short-description: Nested value\n",
                    (
                        "Example only: `scripts/not-real.py`.\n\n"
                        "```markdown\n"
                        "[Example](references/not-real.md)\n"
                        "```"
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["errors"], 0)

    def test_rejects_unbalanced_frontmatter_flow_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "broken-skill"
            write(
                root / "SKILL.md",
                skill_text("broken-skill", "metadata: [\n"),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "frontmatter.malformed",
            {finding["code"] for finding in result["findings"]},
        )

    def test_reports_a_live_missing_markdown_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "linked-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "linked-skill",
                    body="Read [the required guide](references/missing.md).",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_windows_anchored_markdown_pointers_on_every_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "windows-pointer-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "windows-pointer-skill",
                    body=(
                        "Read [the drive-relative guide](C:relative.md).\n"
                        r"Read [the rooted guide](\rooted.md)."
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        codes = [finding["code"] for finding in result["findings"]]
        self.assertEqual(codes.count("pointer.target_outside"), 2)
        self.assertNotIn("pointer.target_missing", codes)

    def test_rejects_backslash_markdown_pointer_as_nonportable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "portable-pointer-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "portable-pointer-skill",
                    body=r"Read [the guide](references\guide.md).",
                ),
            )
            write(root / "references" / "guide.md", "# Guide\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("pointer.target_nonportable", codes)
        self.assertNotIn("pointer.target_missing", codes)

    def test_handles_commonmark_pointer_escaping_and_nesting(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "[bad](references/a"
                + "\\"
                + "\n[next](references/guide.md))"
            ),
            ["references/guide.md"],
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "escaped-pointer-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "escaped-pointer-skill",
                    body=(
                        "Read [the guide](<references/guide\\(v2\\).md>).\n"
                        "Read [the nested guide]"
                        "(references/guide(v2).md#intro).\n"
                        r"Read [the fragment](references/guide.md\#intro)."
                    ),
                ),
            )
            write(root / "references" / "guide(v2).md", "# Guide\n")
            write(root / "references" / "guide.md", "# Fragment guide\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("pointer.target_nonportable", codes)
        self.assertNotIn("pointer.target_missing", codes)

    def test_parses_escaped_angle_closer_before_portability_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "escaped-angle-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "escaped-angle-skill",
                    body=r"Read [the guide](<references/a\>b.md#intro>).",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        findings = [
            finding
            for finding in result["findings"]
            if finding["code"] == "pointer.target_nonportable"
        ]
        self.assertEqual(len(findings), 1)
        self.assertIn("Windows-invalid character", findings[0]["message"])
        self.assertNotIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_fenced_resource_paths_do_not_hide_orphaned_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fenced-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "fenced-skill",
                    body=(
                        "This is only an example:\n\n"
                        "```markdown\n"
                        "Read references/example.md and run scripts/example.py.\n"
                        "```"
                    ),
                ),
            )
            write(root / "references" / "example.md", "# Example\n")
            write(root / "scripts" / "example.py", "# --help\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertTrue(
            {"reference.orphaned", "script.unreferenced"}.issubset(
                {finding["code"] for finding in result["findings"]}
            )
        )

    def test_shell_fenced_commands_count_as_script_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "command-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "command-skill",
                    body=(
                        "```bash\n"
                        "python -X utf8 scripts/bash_tool.py --help\n"
                        "```\n\n"
                        "```powershell\n"
                        "PS> powershell.exe -ExecutionPolicy Bypass -File "
                        ".\\scripts\\powershell_tool.ps1\n"
                        "```\n\n"
                        "```shell-session\n"
                        "$ python scripts/session_tool.py --help\n"
                        "```"
                    ),
                ),
            )
            write(root / "scripts" / "bash_tool.py", "# --help\n")
            write(root / "scripts" / "powershell_tool.ps1", "# .SYNOPSIS\n")
            write(root / "scripts" / "session_tool.py", "# --help\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["resource_files"]["scripts"], 3)
        unreferenced = {
            Path(finding["path"]).name
            for finding in result["findings"]
            if finding["code"] == "script.unreferenced"
        }
        self.assertTrue(
            {
                "bash_tool.py",
                "powershell_tool.ps1",
                "session_tool.py",
            }.isdisjoint(unreferenced)
        )

    def test_windows_shell_forms_count_as_script_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository with spaces" / "windows-command-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "windows-command-skill",
                    body=(
                        "```powershell\n"
                        '& "$PSScriptRoot\\scripts\\from root.ps1" -Mode safe\n'
                        '& "${PSScriptRoot}\\scripts\\from braced root.ps1" -Mode safe\n'
                        "powershell.exe -NoProfile -File "
                        '".\\scripts\\quoted path.ps1" --help\n'
                        "```\n\n"
                        "```cmd\n"
                        'call "%~dp0scripts\\from batch.cmd" /?\n'
                        "```\n\n"
                        "```shell-session\n"
                        '\\\\server\\share> call ".\\scripts\\unc console.cmd" /?\n'
                        "```"
                    ),
                ),
            )
            for script_name, help_text in (
                ("from root.ps1", "# .SYNOPSIS\n"),
                ("from braced root.ps1", "# .SYNOPSIS\n"),
                ("quoted path.ps1", "# .SYNOPSIS\n"),
                ("from batch.cmd", "@rem /?\n"),
                ("unc console.cmd", "@rem /?\n"),
            ):
                write(root / "scripts" / script_name, help_text)
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        unreferenced = {
            Path(finding["path"]).name
            for finding in result["findings"]
            if finding["code"] == "script.unreferenced"
        }
        self.assertTrue(
            {
                "from root.ps1",
                "from braced root.ps1",
                "quoted path.ps1",
                "from batch.cmd",
                "unc console.cmd",
            }.isdisjoint(unreferenced),
            unreferenced,
        )

    def test_scans_native_windows_scripts_for_interactive_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "windows-script-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "windows-script-skill",
                    body="Run scripts/prompt.cmd only with explicit input.",
                ),
            )
            write(root / "scripts" / "prompt.cmd", "@echo off\nset /p answer=Continue?\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertIn(
            "script.interactive_pattern",
            {finding["code"] for finding in result["findings"]},
        )

    def test_noncommand_fenced_text_does_not_count_as_script_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "example-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "example-skill",
                    body=(
                        "```markdown\n"
                        "python scripts/markdown_example.py --help\n"
                        "```\n\n"
                        "```bash\n"
                        "echo scripts/echo_example.py\n"
                        "# python scripts/comment_example.py --help\n"
                        "```\n\n"
                        "```powershell\n"
                        'Write-Output "scripts/powershell_output.ps1"\n'
                        '"scripts/bare quoted.ps1"\n'
                        '"$PSScriptRoot\\scripts\\bare rooted.ps1"\n'
                        '& \'$PSScriptRoot\\scripts\\literal_variable.ps1\'\n'
                        "# & \"$PSScriptRoot\\scripts\\commented.ps1\"\n"
                        "```\n\n"
                        "```cmd\n"
                        "REM call scripts\\remarked.cmd /?\n"
                        "```\n\n"
                        "```shell-session\n"
                        "$ echo scripts/session_echo.py\n"
                        'PS C:\\repo> "scripts\\session literal.ps1"\n'
                        "scripts/session_output.py\n"
                        "```"
                    ),
                ),
            )
            for script_name in (
                "markdown_example.py",
                "echo_example.py",
                "comment_example.py",
                "powershell_output.ps1",
                "bare quoted.ps1",
                "bare rooted.ps1",
                "literal_variable.ps1",
                "commented.ps1",
                "remarked.cmd",
                "session_echo.py",
                "session literal.ps1",
                "session_output.py",
            ):
                write(root / "scripts" / script_name, "# --help\n")
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        unreferenced = {
            Path(finding["path"]).name
            for finding in result["findings"]
            if finding["code"] == "script.unreferenced"
        }
        self.assertEqual(
            unreferenced,
            {
                "markdown_example.py",
                "echo_example.py",
                "comment_example.py",
                "powershell_output.ps1",
                "bare quoted.ps1",
                "bare rooted.ps1",
                "literal_variable.ps1",
                "commented.ps1",
                "remarked.cmd",
                "session_echo.py",
                "session literal.ps1",
                "session_output.py",
            },
        )

    def test_linked_agents_directory_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "metadata-skill"
            outside_agents = temporary_root / "outside-agents"
            write(root / "SKILL.md", skill_text("metadata-skill"))
            write(
                outside_agents / "openai.yaml",
                'interface:\n  default_prompt: "Do not mention the skill token"\n',
            )
            symlink_or_skip(
                self,
                root / "agents",
                outside_agents,
                target_is_directory=True,
            )
            result, _ = REVIEW.static_review(root, 100)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("package.metadata_symlink", codes)
        self.assertNotIn("metadata.default_prompt_missing_skill", codes)

    def test_windows_reparse_attribute_is_link_like(self) -> None:
        info = mock.Mock(
            st_mode=stat.S_IFDIR,
            st_file_attributes=REVIEW.WINDOWS_REPARSE_POINT,
        )
        with mock.patch.object(REVIEW.os, "lstat", return_value=info):
            self.assertTrue(REVIEW.is_link_like(Path("junction")))

    def test_reports_resource_inventory_access_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unreadable-skill"
            write(root / "SKILL.md", skill_text("unreadable-skill"))
            references = root / "references"
            references.mkdir()
            original_walk = REVIEW.os.walk

            def controlled_walk(path: Path, *args: object, **kwargs: object):
                if Path(path) == references:
                    onerror = kwargs["onerror"]
                    assert callable(onerror)
                    error = PermissionError(
                        errno.EACCES,
                        "Permission denied",
                        str(references),
                    )
                    onerror(error)
                    return iter(())
                return original_walk(path, *args, **kwargs)

            with mock.patch.object(REVIEW.os, "walk", side_effect=controlled_walk):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.resource_unreadable",
            {finding["code"] for finding in result["findings"]},
        )

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_agents_directory_junction_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "junction-skill"
            outside_agents = temporary_root / "outside-agents"
            link = root / "agents"
            write(root / "SKILL.md", skill_text("junction-skill"))
            write(
                outside_agents / "openai.yaml",
                'interface:\n  default_prompt: "Do not mention the skill token"\n',
            )
            junction_or_fail(self, link, outside_agents)
            try:
                result, status = REVIEW.static_review(root, 100)
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue((outside_agents / "openai.yaml").is_file())

        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(status, 1)
        self.assertTrue(
            {"package.metadata_symlink", "package.metadata_outside"}.issubset(codes)
        )
        self.assertNotIn("metadata.default_prompt_missing_skill", codes)

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_reference_directory_junctions_are_not_read(self) -> None:
        for index, relative_directory in enumerate(
            ("references", "references/nested")
        ):
            with self.subTest(relative_directory=relative_directory):
                with tempfile.TemporaryDirectory() as temporary:
                    temporary_root = Path(temporary)
                    root = temporary_root / f"resource-skill-{index}"
                    outside = temporary_root / f"outside-references-{index}"
                    pointer = f"{relative_directory}/guide.md"
                    write(
                        root / "SKILL.md",
                        skill_text(
                            f"resource-skill-{index}",
                            body=f"Read [the guide]({pointer}).",
                        ),
                    )
                    write(
                        outside / "guide.md",
                        "EXTERNAL_REFERENCE_SENTINEL\n"
                        "Read [missing](references/external-sentinel.md).\n",
                    )
                    link = root / relative_directory
                    link.parent.mkdir(parents=True, exist_ok=True)
                    junction_or_fail(self, link, outside)
                    guarded_paths = {
                        Path(os.path.abspath(link / "guide.md")),
                        Path(os.path.abspath(outside / "guide.md")),
                    }
                    real_read_text = Path.read_text

                    def guarded_read_text(
                        path: Path, *args: object, **kwargs: object
                    ) -> str:
                        self.assertNotIn(Path(os.path.abspath(path)), guarded_paths)
                        return real_read_text(path, *args, **kwargs)

                    try:
                        with mock.patch.object(
                            Path, "read_text", guarded_read_text
                        ):
                            result, status = REVIEW.static_review(root, 100)
                    finally:
                        if os.path.lexists(link):
                            os.rmdir(link)
                    self.assertTrue((outside / "guide.md").is_file())

                self.assertEqual(status, 1)
                codes = {finding["code"] for finding in result["findings"]}
                self.assertTrue(
                    {"package.resource_symlink", "pointer.target_outside"}.issubset(
                        codes
                    )
                )
                self.assertEqual(result["facts"]["resource_files"]["references"], 1)
                self.assertNotIn("EXTERNAL_REFERENCE_SENTINEL", json.dumps(result))
                self.assertNotIn("external-sentinel.md", json.dumps(result))

    def test_rejects_pointer_resolving_through_symlink_outside_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "linked-skill"
            outside = temporary_root / "outside.md"
            write(outside, "Do not inspect me.\n")
            write(
                root / "SKILL.md",
                skill_text(
                    "linked-skill",
                    body="Read [the guide](references/outside.md).",
                ),
            )
            link = root / "references" / "outside.md"
            link.parent.mkdir(parents=True)
            symlink_or_skip(self, link, outside)
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertTrue(
            {"package.resource_symlink", "pointer.target_outside"}.issubset(
                {finding["code"] for finding in result["findings"]}
            )
        )

    def test_rejects_symlinked_root_skill_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "linked-skill"
            outside = temporary_root / "outside.md"
            write(outside, skill_text("linked-skill"))
            root.mkdir()
            symlink_or_skip(self, root / "SKILL.md", outside)
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.skill_md_symlink",
            {finding["code"] for finding in result["findings"]},
        )


class EvalsValidationTests(unittest.TestCase):
    def test_rejects_skill_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            write(root / "evals" / "files" / "input.txt", "fixture\n")
            evals = {
                "skill_name": "wrong-skill",
                "evals": [
                    {
                        "id": "one",
                        "prompt": "Use the realistic fixture input.",
                        "expected_output": "A verified result.",
                        "files": ["evals/files/input.txt"],
                    },
                    {
                        "id": "two",
                        "prompt": "Exercise a realistic boundary.",
                        "expected_output": "A safe boundary response.",
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.skill_name_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_accepts_matching_well_formed_evals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            evals = {
                "skill_name": "right-skill",
                "evals": [
                    {
                        "id": "one",
                        "prompt": "Complete this realistic task.",
                        "expected_output": "An observable result.",
                    },
                    {
                        "id": "two",
                        "prompt": "Handle this realistic edge case.",
                        "expected_output": "An observable safe response.",
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["target_skill_name"], "right-skill")

    def test_rejects_fixture_paths_outside_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "right-skill"
            outside = temporary_root / "outside.txt"
            write(root / "SKILL.md", skill_text("right-skill"))
            write(outside, "outside\n")
            fixture_link = root / "evals" / "files" / "linked.txt"
            fixture_link.parent.mkdir(parents=True)
            symlink_or_skip(self, fixture_link, outside)
            evals = {
                "skill_name": "right-skill",
                "evals": [
                    {
                        "id": "absolute",
                        "prompt": "Exercise an absolute fixture path.",
                        "expected_output": "A rejected unsafe fixture.",
                        "files": [str(outside)],
                    },
                    {
                        "id": "parent",
                        "prompt": "Exercise a parent traversal fixture path.",
                        "expected_output": "A rejected unsafe fixture.",
                        "files": ["../outside.txt"],
                    },
                    {
                        "id": "symlink",
                        "prompt": "Exercise a fixture symlink that escapes the skill.",
                        "expected_output": "A rejected unsafe fixture.",
                        "files": ["evals/files/linked.txt"],
                    },
                    {
                        "id": "nonportable",
                        "prompt": "Exercise a platform-specific fixture path.",
                        "expected_output": "A rejected nonportable fixture.",
                        "files": ["evals\\files\\input.txt"],
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertTrue(
            {
                "evals.file_absolute",
                "evals.file_parent_traversal",
                "evals.file_outside_skill",
                "evals.file_nonportable",
            }.issubset({finding["code"] for finding in result["findings"]})
        )

    def test_rejects_fixture_paths_that_are_not_windows_portable(self) -> None:
        invalid_paths = [
            "C:drive-relative.txt",
            "/posix-absolute.txt",
            "C:/drive-absolute.txt",
            r"\drive-rooted.txt",
            r"\\server\share\unc.txt",
            "evals/files/CON.txt",
            "evals/files/invalid?.txt",
            "evals/files/trailing-dot.",
            "evals/files/trailing-space ",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "portable-skill"
            write(root / "SKILL.md", skill_text("portable-skill"))
            evals = {
                "skill_name": "portable-skill",
                "evals": [
                    {
                        "id": f"invalid-{index}",
                        "prompt": f"Reject nonportable fixture path {index}.",
                        "expected_output": "A structured path validation finding.",
                        "files": [file_value],
                    }
                    for index, file_value in enumerate(invalid_paths)
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        for index, file_value in enumerate(invalid_paths):
            with self.subTest(file_value=file_value):
                path_findings = [
                    finding
                    for finding in result["findings"]
                    if f"evals[{index}]" in finding["message"]
                    and finding["code"].startswith("evals.file_")
                ]
                self.assertTrue(path_findings)
                self.assertNotIn(
                    "evals.file_missing",
                    {finding["code"] for finding in path_findings},
                )

    def test_requires_evals_to_resolve_to_a_target_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "missing-skill",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run one case.",
                                "expected_output": "One result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run another case.",
                                "expected_output": "Another result.",
                            },
                        ],
                    }
                ),
            )
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.target_skill_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_symlinked_eval_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            write(root / "SKILL.md", skill_text("target-skill"))
            write(outside / "SKILL.md", skill_text("outside-skill"))
            write(
                outside / "evals" / "evals.json",
                json.dumps(
                    {
                        "skill_name": "outside-skill",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run one case.",
                                "expected_output": "One result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run another case.",
                                "expected_output": "Another result.",
                            },
                        ],
                    }
                ),
            )
            linked_evals = root / "evals" / "evals.json"
            linked_evals.parent.mkdir()
            symlink_or_skip(
                self, linked_evals, outside / "evals" / "evals.json"
            )
            result, status = REVIEW.validate_evals(linked_evals, 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["subject"], str(linked_evals))
        self.assertIn(
            "evals.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_eval_definition_below_symlinked_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            write(root / "SKILL.md", skill_text("target-skill"))
            write(outside / "SKILL.md", skill_text("outside-skill"))
            write(
                outside / "evals" / "evals.json",
                json.dumps(
                    {
                        "skill_name": "outside-skill",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run one case.",
                                "expected_output": "One result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run another case.",
                                "expected_output": "Another result.",
                            },
                        ],
                    }
                ),
            )
            symlink_or_skip(
                self,
                root / "evals",
                outside / "evals",
                target_is_directory=True,
            )
            result, status = REVIEW.validate_evals(root / "evals" / "evals.json", 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_eval_definition_below_junctioned_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            write(root / "SKILL.md", skill_text("target-skill"))
            write(
                outside / "evals" / "evals.json",
                json.dumps(
                    {
                        "skill_name": "EXTERNAL_EVAL_SENTINEL",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "External prompt one.",
                                "expected_output": "External result one.",
                            },
                            {
                                "id": "two",
                                "prompt": "External prompt two.",
                                "expected_output": "External result two.",
                            },
                        ],
                    }
                ),
            )
            link = root / "evals"
            junction_or_fail(self, link, outside / "evals")
            try:
                result, status = REVIEW.validate_evals(link / "evals.json", 100)
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue((outside / "evals" / "evals.json").is_file())

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(
            result["facts"],
            {
                "skill_name": None,
                "target_skill_name": None,
                "eval_count": 0,
                "assertion_count": 0,
            },
        )
        self.assertNotIn("EXTERNAL_EVAL_SENTINEL", json.dumps(result))

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_fixture_below_outside_junction_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "fixture-skill"
            outside = temporary_root / "outside-fixtures"
            write(root / "SKILL.md", skill_text("fixture-skill"))
            write(outside / "input.txt", "EXTERNAL_FIXTURE_SENTINEL\n")
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "fixture-skill",
                        "evals": [
                            {
                                "id": "outside-fixture",
                                "prompt": "Use the fixture.",
                                "expected_output": "A bounded result.",
                                "files": ["evals/files/input.txt"],
                            },
                            {
                                "id": "ordinary-case",
                                "prompt": "Run another case.",
                                "expected_output": "Another bounded result.",
                            },
                        ],
                    }
                ),
            )
            link = root / "evals" / "files"
            junction_or_fail(self, link, outside)
            try:
                result, status = REVIEW.validate_evals(evals_path, 100)
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue((outside / "input.txt").is_file())

        self.assertEqual(status, 1)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("evals.file_outside_skill", codes)
        self.assertNotIn("evals.file_missing", codes)
        self.assertEqual(result["facts"]["eval_count"], 2)
        self.assertNotIn("EXTERNAL_FIXTURE_SENTINEL", json.dumps(result))

    def test_rejects_duplicate_assertions_within_an_eval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            evals = {
                "skill_name": "right-skill",
                "evals": [
                    {
                        "id": "one",
                        "prompt": "Complete this realistic task.",
                        "expected_output": "An observable result.",
                        "assertions": ["Has output", " Has output "],
                    },
                    {
                        "id": "two",
                        "prompt": "Handle this realistic edge case.",
                        "expected_output": "An observable safe response.",
                    },
                ],
            }
            evals_path = root / "evals" / "evals.json"
            write(evals_path, json.dumps(evals))
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.assertion_duplicate",
            {finding["code"] for finding in result["findings"]},
        )


class TriggerValidationTests(unittest.TestCase):
    def test_accepts_bundled_stratified_trigger_queries(self) -> None:
        path = SKILL_ROOT / "evals" / "trigger_queries.json"
        result, status = REVIEW.validate_triggers(path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["query_count"], 20)
        self.assertEqual(
            result["facts"]["coverage"],
            {
                "train": {"positive": 6, "negative": 6},
                "validation": {"positive": 4, "negative": 4},
            },
        )

    def test_reports_split_fractions_and_warns_on_imbalanced_splits(self) -> None:
        data: list[dict[str, object]] = []
        for split, per_class_count in (("train", 4), ("validation", 1)):
            for should_trigger in (True, False):
                label = "yes" if should_trigger else "no"
                for index in range(per_class_count):
                    data.append(
                        {
                            "query": f"{split} {label} {index}",
                            "should_trigger": should_trigger,
                            "split": split,
                        }
                    )

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            write(path, json.dumps(data))
            result, status = REVIEW.validate_triggers(path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["warnings"], 1)
        self.assertEqual(
            result["facts"]["split_fractions"],
            {"train": 0.8, "validation": 0.2},
        )
        self.assertIn(
            "triggers.split_imbalance",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_non_array_trigger_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            write(path, json.dumps({"query": "Not an array"}))
            result, status = REVIEW.validate_triggers(path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "triggers.root_type",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_invalid_duplicate_and_unstratified_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            data = [
                {"query": "Same query", "should_trigger": True, "split": "train"},
                {
                    "query": " Same query ",
                    "should_trigger": False,
                    "split": "validation",
                },
                {
                    "query": " ",
                    "should_trigger": "yes",
                    "split": ["test"],
                    "rationale": " ",
                    "typo": True,
                },
            ]
            write(path, json.dumps(data))
            result, status = REVIEW.validate_triggers(path, 100)

        self.assertEqual(status, 1)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertTrue(
            {
                "triggers.query",
                "triggers.query_duplicate",
                "triggers.should_trigger",
                "triggers.split",
                "triggers.coverage",
                "triggers.rationale",
                "triggers.unknown_fields",
            }.issubset(codes)
        )

    def test_unknown_trigger_field_is_a_nonfatal_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            data = [
                {"query": "Train yes", "should_trigger": True, "split": "train"},
                {"query": "Train no", "should_trigger": False, "split": "train"},
                {
                    "query": "Validation yes",
                    "should_trigger": True,
                    "split": "validation",
                    "rationale": "This is an intended request.",
                    "note": "unknown",
                },
                {
                    "query": "Validation no",
                    "should_trigger": False,
                    "split": "validation",
                },
            ]
            write(path, json.dumps(data))
            result, status = REVIEW.validate_triggers(path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["warnings"], 1)
        self.assertIn(
            "triggers.unknown_fields",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_symlinked_trigger_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            external_queries = outside / "evals" / "trigger_queries.json"
            write(external_queries, json.dumps(trigger_queries()))
            linked_queries = root / "evals" / "trigger_queries.json"
            linked_queries.parent.mkdir(parents=True)
            symlink_or_skip(self, linked_queries, external_queries)
            result, status = REVIEW.validate_triggers(linked_queries, 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["subject"], str(linked_queries))
        self.assertIn(
            "triggers.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_trigger_definition_below_symlinked_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            write(
                outside / "evals" / "trigger_queries.json",
                json.dumps(trigger_queries()),
            )
            root.mkdir()
            symlink_or_skip(
                self,
                root / "evals",
                outside / "evals",
                target_is_directory=True,
            )
            result, status = REVIEW.validate_triggers(
                root / "evals" / "trigger_queries.json", 100
            )

        self.assertEqual(status, 1)
        self.assertIn(
            "triggers.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_trigger_definition_below_junctioned_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "target-skill"
            outside = temporary_root / "outside-skill"
            write(root / "SKILL.md", skill_text("target-skill"))
            external_queries = trigger_queries()
            external_queries[0]["query"] = "EXTERNAL_TRIGGER_SENTINEL"
            write(
                outside / "evals" / "trigger_queries.json",
                json.dumps(external_queries),
            )
            link = root / "evals"
            junction_or_fail(self, link, outside / "evals")
            try:
                result, status = REVIEW.validate_triggers(
                    link / "trigger_queries.json", 100
                )
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue(
                (outside / "evals" / "trigger_queries.json").is_file()
            )

        self.assertEqual(status, 1)
        self.assertIn(
            "triggers.definition_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(result["facts"]["query_count"], 0)
        self.assertEqual(result["facts"]["unique_query_count"], 0)
        self.assertEqual(
            result["facts"]["coverage"],
            {
                "train": {"positive": 0, "negative": 0},
                "validation": {"positive": 0, "negative": 0},
            },
        )
        self.assertNotIn("EXTERNAL_TRIGGER_SENTINEL", json.dumps(result))


class RootAliasTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_accepts_package_root_junction_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "aliased-skill"
            alias = temporary_root / "selected-package-alias"
            write(root / "SKILL.md", skill_text("aliased-skill"))
            write(
                root / "evals" / "evals.json",
                json.dumps(
                    {
                        "skill_name": "aliased-skill",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run the first case.",
                                "expected_output": "The first result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run the second case.",
                                "expected_output": "The second result.",
                            },
                        ],
                    }
                ),
            )
            write(
                root / "evals" / "trigger_queries.json",
                json.dumps(trigger_queries()),
            )
            expected_subject = str(root.resolve())
            junction_or_fail(self, alias, root)
            try:
                static_result, static_status = REVIEW.static_review(alias, 100)
                evals_result, evals_status = REVIEW.validate_evals(
                    alias / "evals" / "evals.json", 100
                )
                triggers_result, triggers_status = REVIEW.validate_triggers(
                    alias / "evals" / "trigger_queries.json", 100
                )
            finally:
                if os.path.lexists(alias):
                    os.rmdir(alias)
            self.assertTrue((root / "SKILL.md").is_file())

        self.assertEqual((static_status, evals_status, triggers_status), (0, 0, 0))
        self.assertEqual(static_result["subject"], expected_subject)
        self.assertEqual(static_result["facts"]["skill_name"], "aliased-skill")
        self.assertEqual(evals_result["facts"]["eval_count"], 2)
        self.assertEqual(triggers_result["facts"]["query_count"], 4)


class AggregateTests(unittest.TestCase):
    def write_run(
        self,
        root: Path,
        eval_name: str,
        configuration: str,
        grading_data: dict[str, object],
        tokens: int,
        duration_ms: int,
    ) -> None:
        run = root / eval_name / configuration
        write(run / "grading.json", json.dumps(grading_data))
        write(
            run / "timing.json",
            json.dumps({"total_tokens": tokens, "duration_ms": duration_ms}),
        )

    def test_aggregates_consistent_evidenced_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([(" Has result ", True, "Found output.json")]),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["complete"])
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_accepts_iteration_root_junction_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            alias = temporary_root / "selected-iteration-alias"
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Has result", True, "Found output.json")]),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            expected_subject = str(root.resolve())
            junction_or_fail(self, alias, root)
            try:
                result, status = REVIEW.aggregate(
                    alias, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(alias):
                    os.rmdir(alias)
            self.assertTrue((root / "eval-one" / "with_skill").is_dir())

        self.assertEqual(status, 0)
        self.assertEqual(result["subject"], expected_subject)
        self.assertTrue(result["facts"]["complete"])
        self.assertEqual(result["facts"]["delta"]["pass_rate"], 1.0)

    def test_rejects_evidence_free_or_inconsistent_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = {
                "assertion_results": [
                    {"text": "Has result", "passed": True, "evidence": ""}
                ],
                "summary": {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0},
            }
            self.write_run(root, "eval-one", "with_skill", invalid, 1200, 3000)
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_mismatched_paired_assertion_texts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Candidate assertion", True, "Found output.json")]),
                1200,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Baseline assertion", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.assertion_set_mismatch",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_duplicate_assertions_within_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = grading(
                [
                    ("Has result", True, "Found output.json"),
                    (" Has result ", True, "Found the same output.json"),
                ]
            )
            self.write_run(root, "eval-one", "with_skill", duplicate, 1200, 3000)
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["complete"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )

    def test_huge_numeric_value_is_a_bounded_aggregate_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_run(
                root,
                "eval-one",
                "with_skill",
                grading([("Has result", True, "Found output.json")]),
                10**1000,
                3000,
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "aggregate",
                    str(root),
                    "--candidate",
                    "with_skill",
                    "--baseline",
                    "old_skill",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("aggregate.run_incomplete", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)

    def test_aggregates_multiple_large_finite_values_without_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for eval_name in ("eval-one", "eval-two"):
                self.write_run(
                    root,
                    eval_name,
                    "with_skill",
                    grading([("Has result", True, "Found output.json")]),
                    10**308,
                    3000,
                )
                self.write_run(
                    root,
                    eval_name,
                    "old_skill",
                    grading([("Has result", False, "output.json is absent")]),
                    900,
                    2000,
                )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 0)
        self.assertEqual(
            result["facts"]["run_summary"]["with_skill"]["tokens"]["mean"],
            float(10**308),
        )

    def test_rejects_linked_configuration_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-config"
            write(
                external / "grading.json",
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            write(
                external / "timing.json",
                json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
            )
            linked_config = root / "eval-one" / "with_skill"
            linked_config.parent.mkdir(parents=True)
            symlink_or_skip(
                self, linked_config, external, target_is_directory=True
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.path_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertNotIn("with_skill", result["facts"]["run_summary"])

    def test_rejects_linked_run_data_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external_grading = temporary_root / "external-grading.json"
            write(
                external_grading,
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            candidate = root / "eval-one" / "with_skill"
            candidate.mkdir(parents=True)
            symlink_or_skip(self, candidate / "grading.json", external_grading)
            write(
                candidate / "timing.json",
                json.dumps({"total_tokens": 1200, "duration_ms": 3000}),
            )
            self.write_run(
                root,
                "eval-one",
                "old_skill",
                grading([("Has result", False, "output.json is absent")]),
                900,
                2000,
            )
            result, status = REVIEW.aggregate(root, "with_skill", "old_skill", 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.run_incomplete",
            {finding["code"] for finding in result["findings"]},
        )
        candidate_runs = [
            run
            for run in result["facts"]["runs"]
            if run["configuration"] == "with_skill"
        ]
        self.assertEqual(
            candidate_runs,
            [
                {
                    "eval": "eval-one",
                    "configuration": "with_skill",
                    "complete": False,
                }
            ],
        )

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_junctioned_configuration_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-config"
            write(
                external / "grading.json",
                json.dumps(grading([("Has result", True, "Found output.json")])),
            )
            write(
                external / "timing.json",
                json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
            )
            linked_config = root / "eval-one" / "with_skill"
            linked_config.parent.mkdir(parents=True)
            junction_or_fail(self, linked_config, external)
            try:
                self.write_run(
                    root,
                    "eval-one",
                    "old_skill",
                    grading([("Has result", False, "output.json is absent")]),
                    900,
                    2000,
                )
                result, status = REVIEW.aggregate(
                    root, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(linked_config):
                    os.rmdir(linked_config)
            self.assertTrue((external / "grading.json").is_file())
            self.assertTrue((external / "timing.json").is_file())

        self.assertEqual(status, 1)
        self.assertTrue(
            {"aggregate.path_symlink", "aggregate.configuration_missing"}.issubset(
                {finding["code"] for finding in result["findings"]}
            )
        )
        self.assertNotIn("with_skill", result["facts"]["run_summary"])
        self.assertIsNone(result["facts"]["delta"])
        self.assertNotIn("424242", json.dumps(result))

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_rejects_junctioned_eval_directory_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "iteration"
            external = temporary_root / "external-eval"
            root.mkdir()
            for configuration, passed in (("with_skill", True), ("old_skill", False)):
                write(
                    external / configuration / "grading.json",
                    json.dumps(
                        grading(
                            [
                                (
                                    "Has result",
                                    passed,
                                    "External result sentinel",
                                )
                            ]
                        )
                    ),
                )
                write(
                    external / configuration / "timing.json",
                    json.dumps({"total_tokens": 424242, "duration_ms": 3000}),
                )
            link = root / "eval-one"
            junction_or_fail(self, link, external)
            try:
                result, status = REVIEW.aggregate(
                    root, "with_skill", "old_skill", 100
                )
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)
            self.assertTrue((external / "with_skill" / "grading.json").is_file())
            self.assertTrue((external / "old_skill" / "timing.json").is_file())

        self.assertEqual(status, 1)
        self.assertIn(
            "aggregate.path_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(result["facts"]["runs"], [])
        self.assertEqual(result["facts"]["run_summary"], {})
        self.assertIsNone(result["facts"]["delta"])
        self.assertFalse(result["facts"]["complete"])
        self.assertNotIn("424242", json.dumps(result))


class InterfaceTests(unittest.TestCase):
    def test_junction_creation_failure_is_not_skipped(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["cmd.exe", "mklink"],
            returncode=9,
            stdout="JUNCTION_STDOUT_SENTINEL",
            stderr="JUNCTION_STDERR_SENTINEL",
        )
        link = Path("junction-link")
        target = Path("junction-target")
        with (
            mock.patch.object(os, "name", "nt"),
            mock.patch.object(subprocess, "run", return_value=completed),
            self.assertRaises(self.failureException) as caught,
        ):
            junction_or_fail(self, link, target)

        message = str(caught.exception)
        self.assertIn("exit 9", message)
        self.assertIn(str(link), message)
        self.assertIn(str(target), message)
        self.assertIn("JUNCTION_STDOUT_SENTINEL", message)
        self.assertIn("JUNCTION_STDERR_SENTINEL", message)

    def test_every_subcommand_help_documents_exit_codes(self) -> None:
        for subcommand in (
            "static",
            "validate-evals",
            "validate-triggers",
            "aggregate",
        ):
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), subcommand, "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Exit codes:", completed.stdout)
            self.assertIn(
                "2 fatal CLI, filesystem, JSON parse, or output failure",
                completed.stdout,
            )

    def test_output_help_does_not_claim_truncated_results_are_complete(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "aggregate", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Also write the rendered result", completed.stdout)
        self.assertNotIn("complete rendered result", completed.stdout)

    def test_symlink_loop_is_a_bounded_invalid_path_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trigger_queries.json"
            symlink_or_skip(self, path, path.name)
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "validate-triggers", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Error:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
