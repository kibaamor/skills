"""Package-boundary defenses: links, junctions, budgets, and inventory."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    FS_SAFETY,
    REVIEW,
    SCRIPT,
    STATIC_REVIEW_MODULE,
    junction_or_fail,
    skill_text,
    symlink_or_skip,
    trigger_queries,
    write,
)


class StaticReviewTests(unittest.TestCase):
    def test_immutable_package_is_inventoried_and_digested_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "single-pass-skill"
            write(root / "SKILL.md", skill_text("single-pass-skill"))
            with (
                mock.patch.object(
                    STATIC_REVIEW_MODULE,
                    "iter_files",
                    wraps=STATIC_REVIEW_MODULE.iter_files,
                ) as inventory,
                mock.patch.object(
                    STATIC_REVIEW_MODULE,
                    "digest_package_files",
                    wraps=STATIC_REVIEW_MODULE.digest_package_files,
                ) as digest,
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["package_digest_complete"])
        inventory.assert_called_once()
        digest.assert_called_once()

    def test_package_identity_covers_paths_and_binary_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "content-digest-skill"
            skill_md = root / "SKILL.md"
            binary = root / "custom" / "artifact.bin"
            write(skill_md, skill_text("content-digest-skill"))
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"\xff\x00\x81")

            initial, initial_status = REVIEW.static_review(root, 100)
            binary.write_bytes(b"\xff\x00\x82")
            changed, changed_status = REVIEW.static_review(root, 100)
            renamed = binary.with_name("renamed.bin")
            binary.rename(renamed)
            renamed_result, renamed_status = REVIEW.static_review(root, 100)

            manifest = hashlib.sha256(b"skill-package-manifest\0sha256\0v1\0")
            manifest.update(struct.pack(">Q", 2))
            for path in sorted(
                (skill_md, renamed), key=lambda item: item.relative_to(root).as_posix()
            ):
                relative = path.relative_to(root).as_posix().encode("utf-8")
                contents = path.read_bytes()
                manifest.update(b"F")
                manifest.update(struct.pack(">Q", len(relative)))
                manifest.update(relative)
                manifest.update(struct.pack(">Q", len(contents)))
                manifest.update(hashlib.sha256(contents).digest())
            expected_identity = f"sha256:{manifest.hexdigest()}"

        self.assertEqual((initial_status, changed_status, renamed_status), (0, 0, 0))
        self.assertTrue(initial["facts"]["package_digest_complete"])
        self.assertEqual(initial["facts"]["package_digest_scope"], "entire_package")
        self.assertEqual(initial["facts"]["package_digest_algorithm"], "sha256")
        self.assertEqual(
            initial["facts"]["package_digest_format"],
            "skill-package-manifest-v1",
        )
        self.assertEqual(
            initial["facts"]["limits"]["digest_file_bytes"],
            64 << 20,
        )
        self.assertEqual(
            initial["facts"]["limits"]["total_digest_bytes"],
            256 << 20,
        )
        self.assertEqual(
            initial["facts"]["package_digest_bytes"],
            initial["facts"]["text_bytes_read"] + 3,
        )
        self.assertNotEqual(
            initial["facts"]["package_identity"],
            changed["facts"]["package_identity"],
        )
        self.assertNotEqual(
            changed["facts"]["package_identity"],
            renamed_result["facts"]["package_identity"],
        )
        self.assertEqual(renamed_result["facts"]["package_identity"], expected_identity)

    def test_inventory_reads_instruction_text_outside_standard_directories(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "custom-instructions-skill"
            skill_md = root / "SKILL.md"
            grader = root / "agents" / "grader.md"
            binary = root / "viewer" / "artifact.bin"
            write(skill_md, skill_text("custom-instructions-skill"))
            write(grader, "# Grader\n\nAssess the output evidence.\n")
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"\xff\xfe\x00\x01")
            expected_text_bytes = skill_md.stat().st_size + grader.stat().st_size

            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertTrue(result["facts"]["package_inventory_complete"])
        self.assertTrue(result["facts"]["resource_inventory_complete"])
        self.assertEqual(result["facts"]["resource_inventory_scope"], "entire_package")
        self.assertEqual(result["facts"]["package_entries_scanned"], 5)
        self.assertEqual(result["facts"]["resource_entries_scanned"], 5)
        self.assertEqual(result["facts"]["package_files"], 3)
        self.assertEqual(
            result["facts"]["resource_files"],
            {"references": 0, "scripts": 0, "assets": 0, "evals": 0},
        )
        self.assertTrue(result["facts"]["text_inspection_complete"])
        self.assertEqual(result["facts"]["text_bytes_read"], expected_text_bytes)

    def test_unknown_top_level_link_makes_package_inventory_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "unknown-link-skill"
            skill_md = root / "SKILL.md"
            outside = temporary_root / "outside.md"
            link = root / "custom-guide.md"
            write(skill_md, skill_text("unknown-link-skill"))
            write(outside, "EXTERNAL_SENTINEL [missing](missing.md)\n")
            symlink_or_skip(self, link, outside)
            skill_bytes = skill_md.stat().st_size

            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["package_inventory_complete"])
        self.assertFalse(result["facts"]["resource_inventory_complete"])
        self.assertFalse(result["facts"]["package_digest_complete"])
        self.assertIsNone(result["facts"]["package_identity"])
        self.assertEqual(result["facts"]["text_bytes_read"], skill_bytes)
        self.assertIn(
            "package.resource_symlink",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertNotIn("EXTERNAL_SENTINEL", json.dumps(result))
        self.assertNotIn(
            "pointer.target_missing",
            {finding["code"] for finding in result["findings"]},
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
        self.assertFalse(result["facts"]["package_inventory_complete"])
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
            original_scandir = REVIEW.os.scandir

            def controlled_scandir(path: Path):
                if Path(path) == references:
                    raise PermissionError(
                        errno.EACCES,
                        "Permission denied",
                        str(references),
                    )
                return original_scandir(path)

            with mock.patch.object(
                REVIEW.os, "scandir", side_effect=controlled_scandir
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.resource_unreadable",
            {finding["code"] for finding in result["findings"]},
        )

    @unittest.skipUnless(os.name == "posix", "symbolic links require POSIX")
    def test_resource_links_make_inventory_incomplete(self) -> None:
        for nested in (False, True):
            with self.subTest(nested=nested):
                with tempfile.TemporaryDirectory() as temporary:
                    temporary_root = Path(temporary)
                    root = temporary_root / "linked-resource-skill"
                    external = temporary_root / "external"
                    write(root / "SKILL.md", skill_text("linked-resource-skill"))
                    write(external / "guide.md", "EXTERNAL_SENTINEL\n")
                    if nested:
                        link = root / "references" / "guide.md"
                        link.parent.mkdir()
                        link.symlink_to(external / "guide.md")
                    else:
                        link = root / "references"
                        link.symlink_to(external, target_is_directory=True)

                    result, status = REVIEW.static_review(root, 100)

                self.assertEqual(status, 1)
                self.assertFalse(result["facts"]["resource_inventory_complete"])
                self.assertIn(
                    "package.resource_symlink",
                    {finding["code"] for finding in result["findings"]},
                )
                self.assertNotIn("EXTERNAL_SENTINEL", json.dumps(result))

    def test_pycache_in_skill_ancestor_does_not_hide_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "__pycache__" / "ancestor-skill"
            write(
                root / "SKILL.md",
                skill_text(
                    "ancestor-skill",
                    body="Read [the guide](references/guide.md).",
                ),
            )
            write(root / "references" / "guide.md", "# Guide\n")
            cache = root / "scripts" / "__pycache__" / "tool.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"\xff\xfe\x00\x01")

            result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 0)
        self.assertEqual(result["facts"]["resource_files"]["references"], 1)
        self.assertEqual(result["facts"]["resource_files"]["scripts"], 0)
        self.assertEqual(result["facts"]["package_files"], 3)
        self.assertTrue(result["facts"]["resource_inventory_complete"])

    def test_bounded_reader_rejects_same_size_change_during_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "guide.md"
            write(path, "A" * 100_000)
            original_info = path.stat()
            original_read = REVIEW.os.read
            changed = False

            def changing_read(descriptor: int, size: int) -> bytes:
                nonlocal changed
                chunk = original_read(descriptor, size)
                if chunk and not changed:
                    changed = True
                    with path.open("r+b") as stream:
                        stream.write(b"B" * 100_000)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.utime(
                        path,
                        ns=(
                            original_info.st_atime_ns,
                            original_info.st_mtime_ns + 2_000_000_000,
                        ),
                    )
                return chunk

            with (
                mock.patch.object(REVIEW.os, "read", side_effect=changing_read),
                mock.patch.object(
                    REVIEW.os, "close", wraps=REVIEW.os.close
                ) as close_descriptor,
                self.assertRaises(REVIEW.TextReadError) as caught,
            ):
                REVIEW.read_bounded_regular_utf8(root, path, REVIEW.TextReadBudget())

        self.assertTrue(changed)
        self.assertEqual(caught.exception.code, "package.resource_changed")
        close_descriptor.assert_called_once()

    def test_bounded_reader_accepts_empty_file_after_budget_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "empty.md"
            write(path, "")
            budget = REVIEW.TextReadBudget(bytes_read=7)

            with mock.patch.object(FS_SAFETY, "MAX_TOTAL_TEXT_BYTES", 7):
                text = REVIEW.read_bounded_regular_utf8(root, path, budget)

        self.assertEqual(text, "")
        self.assertEqual(budget.bytes_read, 7)

    def test_windows_stable_signature_ignores_inconsistent_ctime(self) -> None:
        class StatInfo:
            st_size = 100
            st_mtime_ns = 200

            def __init__(self, ctime_ns: int) -> None:
                self.st_ctime_ns = ctime_ns

        with mock.patch.object(REVIEW.os, "name", "nt"):
            lstat_signature = REVIEW.stable_file_signature(StatInfo(300))
            fstat_signature = REVIEW.stable_file_signature(StatInfo(200))

        self.assertEqual(lstat_signature, fstat_signature)

    def test_package_digest_per_file_budget_rejects_without_opening_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "digest-file-budget-skill"
            oversized = root / "artifact.bin"
            skill_md = root / "SKILL.md"
            write(skill_md, skill_text("digest-file-budget-skill"))
            file_limit = skill_md.stat().st_size
            oversized.parent.mkdir(parents=True, exist_ok=True)
            oversized.write_bytes(b"x" * (file_limit + 1))
            real_open = FS_SAFETY.os.open

            def guarded_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                if Path(path) == oversized:
                    self.fail("oversized binary resource was opened")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with (
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_DIGEST_FILE_BYTES",
                    file_limit,
                ),
                mock.patch.object(FS_SAFETY, "MAX_TOTAL_DIGEST_BYTES", 1 << 20),
                mock.patch.object(FS_SAFETY.os, "open", guarded_open),
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertFalse(result["facts"]["package_digest_complete"])
        self.assertIsNone(result["facts"]["package_identity"])
        self.assertIn(
            "package.digest_file_limit",
            {finding["code"] for finding in result["findings"]},
        )

    def test_package_digest_total_budget_is_independent_from_text_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "digest-total-budget-skill"
            skill_md = root / "SKILL.md"
            binary = root / "artifact.bin"
            write(skill_md, skill_text("digest-total-budget-skill"))
            binary.write_bytes(b"12")
            skill_bytes = skill_md.stat().st_size

            with (
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_DIGEST_FILE_BYTES",
                    skill_bytes + 10,
                ),
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_TOTAL_DIGEST_BYTES",
                    skill_bytes + 1,
                ),
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertEqual(result["facts"]["package_digest_bytes"], skill_bytes)
        self.assertEqual(result["facts"]["text_bytes_read"], skill_bytes)
        self.assertFalse(result["facts"]["package_digest_complete"])
        self.assertIsNone(result["facts"]["package_identity"])
        self.assertIn(
            "package.digest_total_limit",
            {finding["code"] for finding in result["findings"]},
        )

    @unittest.skipUnless(
        os.name == "posix" and hasattr(os, "mkfifo"),
        "FIFO resources require POSIX",
    )
    def test_fifo_resource_is_rejected_without_being_opened(self) -> None:
        for relative in (
            "SKILL.md",
            "references/hang.md",
            "scripts/hang.py",
            "agents/openai.yaml",
            "custom/hang.bin",
        ):
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "fifo-resource-skill"
                    if relative != "SKILL.md":
                        write(
                            root / "SKILL.md",
                            skill_text("fifo-resource-skill"),
                        )
                    else:
                        root.mkdir()
                    fifo = root / relative
                    fifo.parent.mkdir(parents=True, exist_ok=True)
                    os.mkfifo(fifo)
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            str(SCRIPT),
                            "static",
                            str(root),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )

                self.assertEqual(completed.returncode, 1, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertIn(
                    "package.resource_special_file",
                    {finding["code"] for finding in result["findings"]},
                )
                self.assertNotIn("Traceback", completed.stderr)

    def test_package_entry_budget_includes_unknown_top_level_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "entry-budget-skill"
            write(root / "SKILL.md", skill_text("entry-budget-skill"))
            for index in range(3):
                write(root / "custom" / f"entry-{index}.bin", "x")
            with mock.patch.object(FS_SAFETY, "MAX_RESOURCE_ENTRIES", 3):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.resource_entry_limit",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertEqual(result["facts"]["package_entries_scanned"], 3)
        self.assertEqual(result["facts"]["resource_entries_scanned"], 3)
        self.assertFalse(result["facts"]["package_inventory_complete"])
        self.assertFalse(result["facts"]["resource_inventory_complete"])
        self.assertFalse(result["facts"]["text_inspection_complete"])

    def test_resource_depth_budget_stops_deep_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "depth-budget-skill"
            write(root / "SKILL.md", skill_text("depth-budget-skill"))
            write(
                root / "assets" / "one" / "two" / "three" / "asset.bin",
                "x",
            )
            with mock.patch.object(FS_SAFETY, "MAX_RESOURCE_DEPTH", 1):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.resource_depth_limit",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["facts"]["resource_inventory_complete"])

    def test_oversized_text_resource_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "text-size-budget-skill"
            oversized = root / "references" / "oversized.md"
            skill_contents = skill_text(
                "text-size-budget-skill",
                body="Read [the guide](references/oversized.md).",
            )
            write(root / "SKILL.md", skill_contents)
            per_file_limit = (root / "SKILL.md").stat().st_size
            write(oversized, "x" * (per_file_limit + 1))
            real_open = FS_SAFETY.os.open
            oversized_opens = 0

            def counted_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal oversized_opens
                if Path(path) == oversized:
                    oversized_opens += 1
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with (
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_TEXT_FILE_BYTES",
                    per_file_limit,
                ),
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_TOTAL_TEXT_BYTES",
                    per_file_limit * 3,
                ),
                mock.patch.object(
                    FS_SAFETY.os,
                    "open",
                    counted_open,
                ),
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertEqual(oversized_opens, 1)
        self.assertEqual(
            [
                finding["path"]
                for finding in result["findings"]
                if finding["code"] == "package.resource_too_large"
            ],
            [str(oversized)],
        )
        self.assertEqual(result["facts"]["text_bytes_read"], per_file_limit)

    def test_total_text_budget_stops_reading_later_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "total-text-budget-skill"
            first = root / "references" / "first.md"
            second = root / "references" / "second.md"
            skill_contents = skill_text(
                "total-text-budget-skill",
                body=(
                    "Read [first](references/first.md) and "
                    "[second](references/second.md)."
                ),
            )
            write(root / "SKILL.md", skill_contents)
            write(first, "123456")
            write(second, "abcdef")
            skill_bytes = (root / "SKILL.md").stat().st_size
            with (
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_TEXT_FILE_BYTES",
                    skill_bytes + 10,
                ),
                mock.patch.object(
                    FS_SAFETY,
                    "MAX_TOTAL_TEXT_BYTES",
                    skill_bytes + 10,
                ),
            ):
                result, status = REVIEW.static_review(root, 100)

        self.assertEqual(status, 1)
        self.assertIn(
            "package.resource_text_budget",
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
        self.assertFalse(result["facts"]["package_inventory_complete"])
        self.assertTrue(
            {"package.metadata_symlink", "package.metadata_outside"}.issubset(codes)
        )
        self.assertNotIn("metadata.default_prompt_missing_skill", codes)

    @unittest.skipUnless(os.name == "nt", "directory junctions require Windows")
    def test_reference_directory_junctions_are_not_read(self) -> None:
        for index, relative_directory in enumerate(("references", "references/nested")):
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
                        with mock.patch.object(Path, "read_text", guarded_read_text):
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


if __name__ == "__main__":
    unittest.main()
