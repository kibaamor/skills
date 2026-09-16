"""Pointer, script-mention, and static-rule findings of the reviewer."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import FS_SAFETY, REVIEW, STATIC_REVIEW_MODULE, skill_text, write


class StaticReviewTests(unittest.TestCase):
    def test_accepts_action_description_without_use_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "action-description"
            write(
                root / "SKILL.md",
                (
                    "---\n"
                    "name: action-description\n"
                    "description: Audits release manifests before publication.\n"
                    "---\n\n"
                    "# Action description\n\nInspect the manifest.\n"
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertNotIn(
            "description.imperative_not_detected",
            {finding["code"] for finding in result["findings"]},
        )

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

    def test_reports_a_missing_markdown_image_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "image-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "image-skill",
                    body="Use this workflow: ![](assets/missing.png)",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_reports_a_missing_markdown_image_with_nested_alt_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "nested-image-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "nested-image-skill",
                    body="Use ![outer [inner]](assets/missing.png).",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_unclosed_code_does_not_hide_a_pointer_in_a_later_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unclosed-code-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "unclosed-code-skill",
                    body=(
                        "`unclosed\n\n"
                        "Read [the required guide](references/missing.md).\n\n"
                        "`unclosed"
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_follows_package_root_companion_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "companion-skill"
            companion = root / "SKILL-MECHANICS.md"
            skill_contents = skill_text(
                "companion-skill",
                body="Read [the skill mechanics](SKILL-MECHANICS.md).",
            )
            companion_contents = "# Skill mechanics\n\nRead [the required guide](references/missing.md).\n"
            write(root / "SKILL.md", skill_contents)
            write(companion, companion_contents)
            expected_bytes = (
                root / "SKILL.md"
            ).stat().st_size + companion.stat().st_size
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        missing = next(
            finding
            for finding in result["findings"]
            if finding["code"] == "pointer.target_missing"
        )
        self.assertEqual(Path(missing["path"]), companion)
        self.assertEqual(result["facts"]["text_bytes_read"], expected_bytes)

    def test_limits_package_root_companion_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "companion-limit-skill"
            first = root / "FIRST.md"
            second = root / "SECOND.md"
            write(
                root / "SKILL.md",
                skill_text(
                    "companion-limit-skill",
                    body="Read [first](FIRST.md) and [second](SECOND.md).",
                ),
            )
            write(first, "# First\n")
            write(second, "# Second\n")
            expected_bytes = (root / "SKILL.md").stat().st_size + first.stat().st_size
            with mock.patch.object(STATIC_REVIEW_MODULE, "MAX_RESOURCE_ENTRIES", 1):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["text_inspection_complete"])
        self.assertIn(
            "package.resource_entry_limit",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(result["facts"]["text_bytes_read"], expected_bytes)

    def test_linked_package_root_companion_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "linked-companion-skill"
            companion = root / "COMPANION.md"
            guide = root / "references" / "guide.md"
            write(
                root / "SKILL.md",
                skill_text(
                    "linked-companion-skill",
                    body="Read [the companion](COMPANION.md).",
                ),
            )
            write(companion, "# Simulated link\n")
            write(guide, "[unread content](references/missing.md)\n")
            original_detector = REVIEW.first_link_like_component
            original_resolver = REVIEW.resolve_within

            def detect_companion_link(package_root: Path, path: Path) -> Path | None:
                if Path(os.path.abspath(path)) == companion:
                    return companion
                return original_detector(package_root, path)

            def resolve_companion_link(
                package_root: Path, path: Path, *, strict: bool
            ) -> Path:
                if Path(os.path.abspath(path)) == companion:
                    return guide
                return original_resolver(package_root, path, strict=strict)

            with (
                mock.patch.object(
                    STATIC_REVIEW_MODULE,
                    "first_link_like_component",
                    side_effect=detect_companion_link,
                ),
                mock.patch.object(
                    STATIC_REVIEW_MODULE,
                    "resolve_within",
                    side_effect=resolve_companion_link,
                ),
                mock.patch.object(
                    FS_SAFETY,
                    "first_link_like_component",
                    side_effect=detect_companion_link,
                ),
            ):
                result, status = REVIEW.static_review(root, 100)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["text_inspection_complete"])
        self.assertIn("package.resource_changed", codes)
        self.assertNotIn("pointer.target_missing", codes)

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

    def test_bare_script_paths_handle_punctuation_without_matching_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bare-path-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "bare-path-skill",
                    body=(
                        "Run ./scripts/local.py. See "
                        "https://example.invalid/scripts/remote.py, "
                        "https://example.invalid/?file=scripts/query.py, and "
                        "https://example.invalid/#scripts/fragment.py, plus "
                        "https://example.invalid/x(scripts/paren.py). Contact "
                        'https://example.invalid/?file="scripts/quoted.py". '
                        "foo@scripts/email.py for background. "
                        "运行scripts/cjk.py。"
                    ),
                ),
            )
            for name in (
                "local.py",
                "remote.py",
                "query.py",
                "fragment.py",
                "paren.py",
                "quoted.py",
                "email.py",
                "cjk.py",
            ):
                write(root / "scripts" / name, "# --help\n")
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
                "remote.py",
                "query.py",
                "fragment.py",
                "paren.py",
                "quoted.py",
                "email.py",
            },
        )

    def test_reports_bare_script_parent_traversal_without_truncating_it(self) -> None:
        paths = (
            "scripts/../../outside.py",
            "scripts/../../",
            "scripts/..//../outside.py",
        )
        for path in paths:
            self.assertEqual(REVIEW.extract_paths(f"Run python {path}"), {path: False})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "traversal-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "traversal-skill",
                    body="\n".join(f"Run python {path}" for path in paths),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertEqual(
            sum(
                finding["code"] == "pointer.target_outside"
                for finding in result["findings"]
            ),
            len(paths),
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


if __name__ == "__main__":
    unittest.main()
