"""Validation of evals.json and trigger_queries.json definitions."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    FS_SAFETY,
    REVIEW,
    SKILL_ROOT,
    junction_or_fail,
    skill_text,
    symlink_or_skip,
    trigger_queries,
    write,
)


class EvalsValidationTests(unittest.TestCase):
    def test_accepts_bundled_behavior_evals(self) -> None:
        path = SKILL_ROOT / "evals" / "evals.json"
        result, status = REVIEW.validate_evals(path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["target_skill_name"], "skill-reviewer")
        self.assertGreaterEqual(result["facts"]["eval_count"], 2)

    def test_rejects_oversized_eval_definition_without_unbounded_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "oversized-evals-skill"
            write(root / "SKILL.md", skill_text("oversized-evals-skill"))
            evals_path = root / "evals" / "evals.json"
            contents = json.dumps(
                {
                    "skill_name": "oversized-evals-skill",
                    "evals": [
                        {
                            "id": "one",
                            "prompt": "Run one realistic case.",
                            "expected_output": "One observable result.",
                        },
                        {
                            "id": "two",
                            "prompt": "Run another realistic case.",
                            "expected_output": "Another observable result.",
                        },
                    ],
                }
            )
            write(evals_path, contents)
            with mock.patch.object(
                FS_SAFETY, "MAX_TEXT_FILE_BYTES", len(contents) - 1
            ):
                result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["facts"]["eval_count"], 0)
        self.assertIn(
            "package.resource_too_large",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_oversized_target_skill_during_evals_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "oversized-target-skill"
            target_text = skill_text("oversized-target-skill") + ("x" * 400)
            write(root / "SKILL.md", target_text)
            evals_path = root / "evals" / "evals.json"
            contents = json.dumps(
                {
                    "skill_name": "oversized-target-skill",
                    "evals": [
                        {
                            "id": "one",
                            "prompt": "Run one realistic case.",
                            "expected_output": "One observable result.",
                        },
                        {
                            "id": "two",
                            "prompt": "Run another realistic case.",
                            "expected_output": "Another observable result.",
                        },
                    ],
                }
            )
            write(evals_path, contents)
            with mock.patch.object(
                FS_SAFETY, "MAX_TEXT_FILE_BYTES", len(contents) + 10
            ):
                result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.target_frontmatter",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertIn("resource exceeds", json.dumps(result).lower())

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

    def test_rejects_target_frontmatter_without_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unnamed-skill"
            write(
                root / "SKILL.md",
                "---\ndescription: Audits manifests.\n---\n\n# Unnamed\n",
            )
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "invented-name",
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Run one realistic case.",
                                "expected_output": "An observable result.",
                            },
                            {
                                "id": "two",
                                "prompt": "Run a boundary case.",
                                "expected_output": "An observable boundary result.",
                            },
                        ],
                    }
                ),
            )
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "evals.target_name_missing",
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

    def test_canonicalizes_skill_name_before_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "  right-skill  ",
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
                ),
            )
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["skill_name"], "right-skill")

    def test_rejects_blank_trimmed_duplicate_and_boolean_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            cases = []
            for case_id in ("   ", "duplicate", " duplicate ", 7, True):
                cases.append(
                    {
                        "id": case_id,
                        "prompt": "Complete this realistic task.",
                        "expected_output": "An observable result.",
                    }
                )
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps({"skill_name": "right-skill", "evals": cases}),
            )
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 1)
        codes = [finding["code"] for finding in result["findings"]]
        self.assertEqual(codes.count("evals.id_missing"), 2)
        self.assertEqual(codes.count("evals.id_duplicate"), 1)

    def test_unknown_root_and_case_fields_are_nonfatal_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "right-skill"
            write(root / "SKILL.md", skill_text("right-skill"))
            evals_path = root / "evals" / "evals.json"
            write(
                evals_path,
                json.dumps(
                    {
                        "skill_name": "right-skill",
                        "metadata": {},
                        "evals": [
                            {
                                "id": "one",
                                "prompt": "Complete this realistic task.",
                                "expected_output": "An observable result.",
                                "expectations": ["Unsupported dialect field"],
                            },
                            {
                                "id": "two",
                                "prompt": "Handle this realistic edge case.",
                                "expected_output": "An observable safe response.",
                            },
                        ],
                    }
                ),
            )
            result, status = REVIEW.validate_evals(evals_path, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["warnings"], 2)
        unknown_findings = [
            finding
            for finding in result["findings"]
            if finding["code"] == "evals.unknown_fields"
        ]
        self.assertEqual(len(unknown_findings), 2)
        self.assertIn("metadata", unknown_findings[0]["message"])
        self.assertIn("expectations", unknown_findings[1]["message"])

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
        facts = result["facts"]
        self.assertEqual(facts["query_count"], facts["unique_query_count"])
        for split in ("train", "validation"):
            self.assertGreaterEqual(facts["coverage"][split]["positive"], 4)
            self.assertGreaterEqual(facts["coverage"][split]["negative"], 4)
        self.assertGreaterEqual(facts["split_fractions"]["validation"], 0.3)
        self.assertLessEqual(facts["split_fractions"]["validation"], 0.5)

    def test_rejects_oversized_trigger_definition_without_unbounded_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "oversized-trigger-skill"
            queries_path = root / "evals" / "trigger_queries.json"
            data = trigger_queries()
            data[0]["query"] = "Train yes " + ("x" * 200)
            contents = json.dumps(data)
            write(queries_path, contents)
            with mock.patch.object(
                FS_SAFETY, "MAX_TEXT_FILE_BYTES", len(contents) - 1
            ):
                result, status = REVIEW.validate_triggers(queries_path, 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["facts"]["query_count"], 0)
        self.assertIn(
            "package.resource_too_large",
            {finding["code"] for finding in result["findings"]},
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


if __name__ == "__main__":
    unittest.main()
