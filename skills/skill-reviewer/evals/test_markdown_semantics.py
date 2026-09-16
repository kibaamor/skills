"""CommonMark-subset pointer scanning semantics and scan budgets."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _support import MARKDOWN_SCAN, REVIEW, SCRIPT, skill_text, write


class StaticReviewTests(unittest.TestCase):
    def test_ignores_escaped_markdown_image_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "escaped-image-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "escaped-image-skill",
                    body="Literal syntax: !\\[flow](assets/missing.png).",
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertNotIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_nested_link_keeps_only_the_inner_target(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "[outer [inner](references/real.md)](references/missing.md)"
            ),
            ["references/real.md"],
        )

    def test_image_nested_link_does_not_deactivate_an_outer_link(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "[outer ![image [inner](references/inner.md)]"
                "(assets/image.png)](references/outer.md)"
            ),
            [
                "references/inner.md",
                "assets/image.png",
                "references/outer.md",
            ],
        )

    def test_ignores_markdown_targets_inside_same_line_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "inline-code-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "inline-code-skill",
                    body=(
                        "Example only: `[guide](references/missing.md)`.\n\n"
                        "Example image: `![flow](assets/missing.png)`."
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertNotIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_ignores_markdown_targets_inside_multiline_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "multiline-code-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "multiline-code-skill",
                    body=(
                        "Example only: `first line\n"
                        "![flow](assets/missing.png)\n"
                        "last line`."
                    ),
                ),
            )
            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertNotIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
        )

    def test_unclosed_code_does_not_cross_an_atx_heading(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "`unclosed\n"
                "# Heading\n"
                "Read [guide](references/missing.md).\n"
                "`unclosed"
            ),
            ["references/missing.md"],
        )

    def test_unclosed_code_does_not_cross_a_setext_heading(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "`unclosed\n"
                "Heading [guide](references/missing.md)\n"
                "--\n"
                "`unclosed"
            ),
            ["references/missing.md"],
        )

    def test_multiline_code_stays_inside_a_blockquote(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "> `first\n"
                "> [guide](references/missing.md)\n"
                "> last`"
            ),
            [],
        )

    def test_multiline_code_stays_inside_a_list_blockquote(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "- > `open\n"
                "  > [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_blockquote_list_allows_lazy_continuation(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "> - `open\n"
                "> [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_blockquote_list_allows_indented_lazy_continuation(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "> - `open\n"
                "    - [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_nested_blockquote_allows_lazy_continuation(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "> > `open\n"
                "> [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_list_blockquote_allows_partial_lazy_continuation(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "- > > `open\n"
                "    > [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_nested_list_ends_an_inner_blockquote_code_span(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "- > `open\n"
                "    - [guide](references/missing.md) `close"
            ),
            ["references/missing.md"],
        )

    def test_tab_indentation_uses_markdown_columns(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "-     > `open\n"
                "\t[guide](references/missing.md) `close"
            ),
            ["references/missing.md"],
        )

    def test_unclosed_code_does_not_cross_blockquote_boundaries(self) -> None:
        cases = {
            "blank": "> `open\n>\n> [guide](references/missing.md) `close",
            "depth": "> `open\n>   > [guide](references/missing.md) `close",
            "heading": "> `open\n> # [guide](references/missing.md) `close",
            "list item": "> - `open\n> - [guide](references/missing.md) `close",
            "outer list": "> `open\n2. [guide](references/missing.md) `close",
            "leave list for root quote": (
                "- > `open\n> [guide](references/missing.md) `close"
            ),
            "leave inner quote for outer list": (
                "> > `open\n> 10. [guide](references/missing.md) `close"
            ),
        }
        for boundary, text in cases.items():
            with self.subTest(boundary=boundary):
                self.assertEqual(
                    REVIEW.markdown_link_targets(text),
                    ["references/missing.md"],
                )

    def test_noninterrupting_list_markers_remain_inside_code_spans(self) -> None:
        cases = {
            "empty bullet": "`open\n+\n[guide](references/missing.md) `close",
            "ordered from two": (
                "`open\n2. [guide](references/missing.md) `close"
            ),
            "nested empty bullet": (
                "- `open\n  +\n  [guide](references/missing.md) `close"
            ),
            "nested ordered from two": (
                "- `open\n  2. [guide](references/missing.md) `close"
            ),
            "tab-indented quote marker": (
                "`open\n\t> [guide](references/missing.md) `close"
            ),
        }
        for marker, text in cases.items():
            with self.subTest(marker=marker):
                self.assertEqual(REVIEW.markdown_link_targets(text), [])

    def test_interrupting_list_markers_end_code_spans(self) -> None:
        cases = {
            "bullet": "`open\n- [guide](references/missing.md) `close",
            "ordered one": "`open\n1. [guide](references/missing.md) `close",
            "ordered zero-padded one": (
                "`open\n01. [guide](references/missing.md) `close"
            ),
        }
        for marker, text in cases.items():
            with self.subTest(marker=marker):
                self.assertEqual(
                    REVIEW.markdown_link_targets(text),
                    ["references/missing.md"],
                )

    def test_code_spans_do_not_cross_list_container_blocks(self) -> None:
        cases = {
            "nested item": (
                "10. `open\n    - [guide](references/missing.md) `close"
            ),
            "relative quote": (
                "10. `open\n    > [guide](references/missing.md) `close"
            ),
            "item heading": (
                "- # `open\n    [guide](references/missing.md) `close"
            ),
        }
        for block, text in cases.items():
            with self.subTest(block=block):
                self.assertEqual(
                    REVIEW.markdown_link_targets(text),
                    ["references/missing.md"],
                )

    def test_list_heading_state_does_not_leak_into_a_later_paragraph(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "- # Heading\n"
                "`open\n"
                "2. [guide](references/missing.md) `close"
            ),
            [],
        )

    def test_indented_code_starts_a_new_markdown_block(self) -> None:
        cases = {
            "top level": "    `open\n[guide](references/missing.md) `close",
            "list item": "-     `open\n  [guide](references/missing.md) `close",
        }
        for block, text in cases.items():
            with self.subTest(block=block):
                self.assertEqual(
                    REVIEW.markdown_link_targets(text),
                    ["references/missing.md"],
                )

    def test_code_spans_do_not_cross_commonmark_html_blocks(self) -> None:
        boundaries = {
            "raw": ("  <script>", "</script>"),
            "comment": ("<!--", "-->"),
            "processing": ("<?", "?>"),
            "declaration": ("<!A", ">"),
            "cdata": ("<![CDATA[", "]]>"),
        }
        for block_type, (start, end) in boundaries.items():
            with self.subTest(block_type=block_type):
                self.assertEqual(
                    REVIEW.markdown_link_targets(
                        "`open\n"
                        f"{start}\n"
                        f"{end}\n"
                        "[guide](references/missing.md) `close"
                    ),
                    ["references/missing.md"],
                )

    def test_ignores_markdown_links_inside_commonmark_html_blocks(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "<script>\n[guide](references/missing.md)\n</script>"
            ),
            [],
        )

    def test_html_block_ends_when_its_list_container_ends(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "- <script>\n- [guide](references/missing.md)"
            ),
            ["references/missing.md"],
        )

    def test_raw_html_end_tag_does_not_allow_internal_whitespace(self) -> None:
        self.assertEqual(
            REVIEW.markdown_link_targets(
                "<script>\n"
                "</script >\n"
                "[guide](references/missing.md)"
            ),
            [],
        )

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

    def test_malformed_markdown_link_scan_scales_linearly(self) -> None:
        def elapsed(candidate_count: int) -> float:
            text = "[x](" * candidate_count
            started = time.perf_counter()
            targets = REVIEW.markdown_link_targets(text)
            duration = time.perf_counter() - started
            self.assertEqual(targets, [])
            return duration

        small = elapsed(1_500)
        large = elapsed(3_000)

        self.assertLessEqual(
            large,
            small * 3 + 0.05,
            f"doubling malformed input took {small:.3f}s then {large:.3f}s",
        )

    def test_limits_unclosed_markdown_bracket_depth(self) -> None:
        with mock.patch.object(MARKDOWN_SCAN, "MAX_MARKDOWN_BRACKET_DEPTH", 4):
            with self.assertRaisesRegex(
                REVIEW.MarkdownScanLimitError, "4-level scan budget"
            ):
                REVIEW.markdown_link_targets("[" * 5)

    def test_limits_markdown_code_span_delimiters(self) -> None:
        with mock.patch.object(MARKDOWN_SCAN, "MAX_MARKDOWN_CODE_SPAN_DELIMITERS", 4):
            with self.assertRaisesRegex(
                REVIEW.MarkdownScanLimitError, "4-run scan budget"
            ):
                REVIEW.markdown_link_targets("`a\n" * 5)

    def test_limits_markdown_container_depth(self) -> None:
        with mock.patch.object(MARKDOWN_SCAN, "MAX_MARKDOWN_CONTAINER_DEPTH", 2):
            with self.assertRaisesRegex(
                REVIEW.MarkdownScanLimitError, "2-level scan budget"
            ):
                REVIEW.markdown_link_targets("- a\n  - b\n    - c")

    def test_nonlocal_token_scan_scales_linearly(self) -> None:
        def elapsed(length: int) -> float:
            text = "_" * length
            samples = []
            for _ in range(3):
                started = time.perf_counter()
                masked = REVIEW.without_nonlocal_tokens(text)
                samples.append(time.perf_counter() - started)
                self.assertEqual(masked, text)
            return min(samples)

        small = elapsed(8_000)
        large = elapsed(16_000)

        self.assertLessEqual(
            large,
            small * 3 + 0.05,
            f"doubling a plain token took {small:.3f}s then {large:.3f}s",
        )

    def test_large_malformed_markdown_input_finishes_with_a_bounded_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bounded-markdown-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "bounded-markdown-skill",
                    body="[x](" * 8_000,
                ),
            )
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "static", str(root)],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIn(
            "pointer.scan_limited",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertNotIn("Traceback", completed.stderr)

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


if __name__ == "__main__":
    unittest.main()
