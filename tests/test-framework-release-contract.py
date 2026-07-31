#!/usr/bin/env python3
"""Regression coverage for the framework release contract validator."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate-framework-release-contract.py"


def copy_source(destination: Path) -> None:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".DS_Store", ".obsidian", "__pycache__"),
    )


class FrameworkReleaseContractTest(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def mutated_source(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        copy_source(Path(temporary.name) / "source")
        return temporary

    def test_checked_in_contract_is_valid(self) -> None:
        result = self.run_validator(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_duplicate_manifest_version(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["releases"].append(manifest["releases"][-1])
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("重复版本", result.stderr)

    def test_rejects_empty_manifest(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["releases"] = []
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("非空数组", result.stderr)

    def test_rejects_leading_zero_semver(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["releases"][-1]["version"] = "1.05.3"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("三段式 SemVer", result.stderr)

    def test_rejects_non_increasing_manifest_version(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["releases"][-1]["version"] = "1.5.1"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("严格递增", result.stderr)

    def test_rejects_invalid_release_date(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["releases"][-1]["released_on"] = "2026-02-30"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("合法 UTC 日期", result.stderr)

    def test_rejects_non_integer_schema_version(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            path = root / "harness" / "framework-releases.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["schema_version"] = True
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("schema_version", result.stderr)

    def test_rejects_version_file_drift(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            (root / "VERSION").write_text("1.5.2\n", encoding="utf-8")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("VERSION", result.stderr)

    def test_rejects_changelog_only_release(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            changelog = root / "CHANGELOG.md"
            changelog.write_text(
                "## v1.9.9 — 2026-07-30（fixture）\n\n" + changelog.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("清单缺少 CHANGELOG", result.stderr)


if __name__ == "__main__":
    unittest.main()
