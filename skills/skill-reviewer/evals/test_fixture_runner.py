"""Isolated materialization of dormant skill fixtures."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from run_tests import (
    ACTIVE_SKILL_NAME,
    FIXTURE_SKILL_NAME,
    FixturePreparationError,
    materialize_fixture_skills,
    run_tests,
    stage_skill_for_tests,
)


class FixtureRunnerTests(unittest.TestCase):
    def make_skill(self, root: Path) -> Path:
        skill_root = root / "skill-reviewer"
        fixture = skill_root / "evals" / "files" / "example-skill"
        fixture.mkdir(parents=True)
        (fixture / FIXTURE_SKILL_NAME).write_text("fixture contents\n", encoding="utf-8")
        (skill_root / "evals" / "evals.json").write_text(
            json.dumps(
                {
                    "skill_name": "skill-reviewer",
                    "evals": [
                        {
                            "id": "example",
                            "prompt": "Review the example.",
                            "expected_output": "A review.",
                            "files": [
                                f"evals/files/example-skill/{FIXTURE_SKILL_NAME}"
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return skill_root

    def test_materializes_fixture_and_rewrites_staged_eval_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_root = self.make_skill(Path(temporary))

            count = materialize_fixture_skills(skill_root)

            fixture = skill_root / "evals" / "files" / "example-skill"
            self.assertEqual(count, 1)
            self.assertFalse((fixture / FIXTURE_SKILL_NAME).exists())
            self.assertEqual(
                (fixture / ACTIVE_SKILL_NAME).read_text(encoding="utf-8"),
                "fixture contents\n",
            )
            evals = json.loads(
                (skill_root / "evals" / "evals.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                evals["evals"][0]["files"],
                [f"evals/files/example-skill/{ACTIVE_SKILL_NAME}"],
            )

    def test_stages_without_changing_source_fixture_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_skill(root / "source")
            destination = root / "staged" / "skill-reviewer"

            count = stage_skill_for_tests(source, destination)

            source_fixture = source / "evals" / "files" / "example-skill"
            staged_fixture = destination / "evals" / "files" / "example-skill"
            self.assertEqual(count, 1)
            self.assertTrue((source_fixture / FIXTURE_SKILL_NAME).is_file())
            self.assertFalse((source_fixture / ACTIVE_SKILL_NAME).exists())
            self.assertFalse((staged_fixture / FIXTURE_SKILL_NAME).exists())
            self.assertTrue((staged_fixture / ACTIVE_SKILL_NAME).is_file())

    def test_refuses_to_overwrite_an_active_fixture_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_root = self.make_skill(Path(temporary))
            fixture = skill_root / "evals" / "files" / "example-skill"
            (fixture / ACTIVE_SKILL_NAME).write_text("active contents\n", encoding="utf-8")

            with self.assertRaises(FixturePreparationError):
                materialize_fixture_skills(skill_root)

            self.assertEqual(
                (fixture / FIXTURE_SKILL_NAME).read_text(encoding="utf-8"),
                "fixture contents\n",
            )
            self.assertEqual(
                (fixture / ACTIVE_SKILL_NAME).read_text(encoding="utf-8"),
                "active contents\n",
            )

    def test_custom_command_uses_materialized_root_then_cleans_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_skill(root / "source")
            result_path = root / "command-result.json"
            command = [
                sys.executable,
                "-B",
                "-c",
                (
                    "import json, os, sys\n"
                    "from pathlib import Path\n"
                    "root = Path(os.environ['SKILL_REVIEWER_TEST_ROOT'])\n"
                    "fixture = root / 'evals/files/example-skill'\n"
                    "evals = json.loads((root / 'evals/evals.json').read_text())\n"
                    "result = {\n"
                    "    'root': str(root),\n"
                    "    'cwd_matches': Path.cwd() == root,\n"
                    "    'active': (fixture / 'SKILL.md').is_file(),\n"
                    "    'dormant': (fixture / 'SKILL.fixture.md').exists(),\n"
                    "    'files': evals['evals'][0]['files'],\n"
                    "}\n"
                    "Path(sys.argv[1]).write_text(json.dumps(result))\n"
                ),
                str(result_path),
            ]

            with redirect_stderr(StringIO()):
                status = run_tests("unused", 1, command, source_root=source)

            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(status, 0)
            self.assertTrue(result["cwd_matches"])
            self.assertTrue(result["active"])
            self.assertFalse(result["dormant"])
            self.assertEqual(
                result["files"],
                [f"evals/files/example-skill/{ACTIVE_SKILL_NAME}"],
            )
            self.assertFalse(Path(result["root"]).exists())

    def test_custom_command_exit_code_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = self.make_skill(Path(temporary) / "source")
            command = [sys.executable, "-B", "-c", "raise SystemExit(7)"]

            with redirect_stderr(StringIO()):
                status = run_tests("unused", 1, command, source_root=source)

            self.assertEqual(status, 7)


if __name__ == "__main__":
    unittest.main()
