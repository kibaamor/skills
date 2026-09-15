from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_knowledge.py"
HAS_YAML = importlib.util.find_spec("yaml") is not None


def run_script(*args: str, cwd: Optional[Path] = None) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=10,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"script did not emit JSON: {exc}; stderr={result.stderr!r}") from exc
    return result, report


class ProjectKnowledgeInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "tracked.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "src" / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")
        (self.root / "package.json").write_text('{"scripts":{"test":"true"}}\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "add", "src/tracked.py", "package.json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def inventory(self, *extra_args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        return run_script(
            "inventory",
            "--root",
            str(self.root),
            "--format",
            "json",
            *extra_args,
        )

    def test_git_inventory_defaults_to_tracked_files(self) -> None:
        result, report = self.inventory()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["scope"], "git-tracked")
        paths = {record["path"] for record in report["files"]}
        self.assertIn("src/tracked.py", paths)
        self.assertIn("package.json", paths)
        self.assertNotIn("src/untracked.py", paths)
        self.assertEqual(report["signals"]["manifests"], ["package.json"])

    def test_git_inventory_can_include_untracked_files(self) -> None:
        result, report = self.inventory("--include-untracked")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["scope"], "git-tracked-and-untracked")
        paths = {record["path"] for record in report["files"]}
        self.assertIn("src/tracked.py", paths)
        self.assertIn("src/untracked.py", paths)

    def test_inventory_exclude_applies_to_tracked_and_untracked_files(self) -> None:
        result, report = self.inventory("--include-untracked", "--exclude", "src/**")

        self.assertEqual(result.returncode, 0, result.stderr)
        paths = {record["path"] for record in report["files"]}
        self.assertEqual(paths, {"package.json"})


@unittest.skipUnless(HAS_YAML, "PyYAML is required for strict metadata tests")
class ProjectKnowledgeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.knowledge = self.root / "docs" / "project-knowledge"
        self.knowledge.mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src" / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        (self.root / "tests" / "test_app.py").write_text("# test anchor\n", encoding="utf-8")
        self.write_valid_knowledge()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def context_frontmatter(
        self,
        overrides: Optional[dict[str, str]] = None,
        extra: Optional[Sequence[str]] = None,
    ) -> str:
        fields = {
            "id": "id: project.context",
            "summary": "summary: Project purpose and supported capabilities.",
            "read_when": "read_when:\n  - Investigating project behavior.",
            "source_paths": "source_paths:\n  - src/app.py",
            "source_symbols": "source_symbols:\n  - main",
            "tests": "tests:\n  - tests/test_app.py",
            "owner": "owner: platform-team",
        }
        fields.update(overrides or {})
        lines = [*fields.values(), *(extra or [])]
        return "\n".join(lines)

    def write_valid_knowledge(
        self,
        *,
        readme: Optional[str] = None,
        context_overrides: Optional[dict[str, str]] = None,
        context_extra: Optional[Sequence[str]] = None,
    ) -> None:
        (self.knowledge / "README.md").write_text(
            readme
            or """# Project Knowledge

[Context](CONTEXT.md#project-context)
[Architecture](ARCHITECTURE.md#project-architecture)

## Task Routes

[This section](#task-routes)
[Data flow](ARCHITECTURE.md#data-flow)
""",
            encoding="utf-8",
        )
        (self.knowledge / "CONTEXT.md").write_text(
            f"""---
{self.context_frontmatter(context_overrides, context_extra)}
---

# Project Context

## Capabilities

[Architecture](ARCHITECTURE.md#project-architecture)
""",
            encoding="utf-8",
        )
        (self.knowledge / "ARCHITECTURE.md").write_text(
            """---
id: project.architecture
summary: Runtime boundaries and representative flows.
source_paths:
  - src/app.py
---

# Project Architecture

## Data Flow
""",
            encoding="utf-8",
        )

    def run_validate(self, *extra_args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        return run_script(
            "validate",
            "--root",
            str(self.root),
            "--knowledge-dir",
            "docs/project-knowledge",
            "--require-yaml",
            "--format",
            "json",
            *extra_args,
        )

    def finding_codes(self, report: dict) -> list[str]:
        return [finding["code"] for finding in report.get("findings", [])]

    def snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def test_valid_knowledge_and_heading_anchors_pass_without_writes(self) -> None:
        before = self.snapshot()

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["counts"]["errors"], 0)
        self.assertEqual(self.snapshot(), before)

    def test_same_file_missing_heading_anchor_is_an_error(self) -> None:
        readme = (self.knowledge / "README.md").read_text(encoding="utf-8")
        self.write_valid_knowledge(readme=readme.replace("#task-routes", "#missing-route"))

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN_HEADING_ANCHOR", self.finding_codes(report))

    def test_cross_file_missing_heading_anchor_is_an_error(self) -> None:
        readme = (self.knowledge / "README.md").read_text(encoding="utf-8")
        self.write_valid_knowledge(readme=readme.replace("#data-flow", "#missing-flow"))

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN_HEADING_ANCHOR", self.finding_codes(report))

    def test_heading_anchor_in_markdown_outside_knowledge_directory_is_checked(self) -> None:
        (self.root / "GUIDE.md").write_text("# External Guide\n", encoding="utf-8")
        context = (self.knowledge / "CONTEXT.md").read_text(encoding="utf-8")
        (self.knowledge / "CONTEXT.md").write_text(
            context + "\n[Missing external section](../../GUIDE.md#missing)\n",
            encoding="utf-8",
        )

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN_HEADING_ANCHOR", self.finding_codes(report))

    def test_setext_and_duplicate_heading_anchors_are_supported(self) -> None:
        readme = (self.knowledge / "README.md").read_text(encoding="utf-8")
        readme += """
Repeated
--------

Repeated
--------

[First duplicate](#repeated)
[Second duplicate](#repeated-1)
"""
        self.write_valid_knowledge(readme=readme)

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("BROKEN_HEADING_ANCHOR", self.finding_codes(report))

    def test_readme_is_the_only_entrypoint(self) -> None:
        (self.knowledge / "README.md").rename(self.knowledge / "INDEX.md")

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("ENTRY_MISSING", self.finding_codes(report))

    def test_entry_option_is_rejected_with_structured_operational_error(self) -> None:
        result, report = self.run_validate("--entry", "INDEX.md")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["command"], "validate")
        self.assertIn("fixed at README.md", report["operational_error"])

    def test_help_documents_fixed_entry_without_advertising_entry_option(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("top-level README.md", " ".join(result.stdout.split()))
        self.assertNotIn("--entry", result.stdout)

    def test_unsupported_frontmatter_field_is_an_error(self) -> None:
        self.write_valid_knowledge(context_extra=["fresh: true"])

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("UNSUPPORTED_METADATA_FIELD", self.finding_codes(report))

    def test_linked_decision_page_may_keep_native_format_without_frontmatter(self) -> None:
        decisions = self.knowledge / "decisions"
        decisions.mkdir()
        (decisions / "ADR-001-runtime.md").write_text(
            "# Runtime decision\n\nUse one process for this fixture.\n",
            encoding="utf-8",
        )
        readme = (self.knowledge / "README.md").read_text(encoding="utf-8")
        (self.knowledge / "README.md").write_text(
            readme + "\n[Runtime decision](decisions/ADR-001-runtime.md)\n",
            encoding="utf-8",
        )

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("FRONTMATTER_REQUIRED", self.finding_codes(report))

    def test_summary_must_be_a_nonempty_string_wherever_declared(self) -> None:
        readme = """---
summary: []
---

# Project Knowledge

[Context](CONTEXT.md#project-context)
[Architecture](ARCHITECTURE.md#project-architecture)
"""
        self.write_valid_knowledge(readme=readme)

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID_SUMMARY", self.finding_codes(report))

    def test_optional_list_fields_must_be_nonempty_string_lists(self) -> None:
        invalid_fields = {
            "read_when": "read_when: []",
            "source_symbols": "source_symbols:\n  - '   '",
            "tests": "tests: tests/test_app.py",
        }
        for field, declaration in invalid_fields.items():
            with self.subTest(field=field):
                self.write_valid_knowledge(context_overrides={field: declaration})

                result, report = self.run_validate()

                self.assertEqual(result.returncode, 1)
                self.assertTrue(
                    {
                        "INVALID_METADATA_TYPE",
                        "EMPTY_METADATA_PATH",
                        "EMPTY_METADATA_VALUE",
                    }
                    & set(self.finding_codes(report))
                )

    def test_owner_and_verified_commit_must_be_nonempty_strings(self) -> None:
        self.write_valid_knowledge(
            context_overrides={"owner": "owner: '   '"},
            context_extra=["verified_commit: ''"],
        )

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID_OWNER", self.finding_codes(report))
        self.assertIn("INVALID_VERIFIED_COMMIT", self.finding_codes(report))

    def test_missing_source_and_test_metadata_paths_are_errors(self) -> None:
        self.write_valid_knowledge(
            context_overrides={
                "source_paths": "source_paths:\n  - src/missing.py",
                "tests": "tests:\n  - tests/missing_test.py",
            }
        )

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.finding_codes(report).count("METADATA_PATH_MISSING"), 2)

    def test_unsafe_metadata_paths_are_errors_without_crashing_stale_analysis(self) -> None:
        self.write_valid_knowledge(
            context_overrides={"source_paths": "source_paths:\n  - ../outside.py"}
        )

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("UNSAFE_METADATA_PATH", self.finding_codes(report))

    def commit_all(self, message: str) -> str:
        subprocess.run(["git", "-C", str(self.root), "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Project Knowledge Test",
                "-c",
                "user.email=project-knowledge@example.test",
                "commit",
                "-m",
                message,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        rev = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return rev.stdout.strip()

    def test_verified_commit_reports_stale_candidate_without_failing_by_default(self) -> None:
        baseline = self.commit_all("baseline")
        self.write_valid_knowledge(context_extra=[f"verified_commit: {baseline}"])
        subprocess.run(["git", "-C", str(self.root), "add", "."], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Project Knowledge Test",
                "-c",
                "user.email=project-knowledge@example.test",
                "commit",
                "-m",
                "add verified commit",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        (self.root / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

        result, report = self.run_validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["counts"]["stale"], 1)
        self.assertIn("STALE_CANDIDATE", self.finding_codes(report))

    def test_fail_on_stale_turns_stale_candidate_into_failure(self) -> None:
        baseline = self.commit_all("baseline")
        (self.root / "tests" / "test_app.py").write_text("# changed test anchor\n", encoding="utf-8")

        result, report = self.run_validate("--since", baseline, "--fail-on-stale")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["counts"]["errors"], 0)
        self.assertEqual(report["counts"]["stale"], 1)
        self.assertIn("STALE_CANDIDATE", self.finding_codes(report))


if __name__ == "__main__":
    unittest.main()
