#!/usr/bin/env python3
"""Negative coverage for scripts/validate-contract-fixtures.py.

The validator's positive path runs in CI directly; these tests prove it
actually rejects drift: a mutated canonical vector, a tampered golden
signature, a schema snapshot mismatch, and an unlisted fixture file must each
turn the validator red in an isolated copy of the tree.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

COPIED = [
    "VERSION",
    "harness/framework-releases.json",
    "scripts/validate-contract-fixtures.py",
    "contract-fixtures",
    "templates/claude/console",
    "templates/claude/dispatch",
]


def make_tree(tmp: pathlib.Path) -> pathlib.Path:
    for rel in COPIED:
        source = ROOT / rel
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy(source, target)
    return tmp


def run_validator(tree: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tree / "scripts" / "validate-contract-fixtures.py")],
        capture_output=True,
        text=True,
    )


class ContractFixturesValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="contract-fixtures-test-")
        self.tree = make_tree(pathlib.Path(self.temp.name))
        self.fixtures = self.tree / "contract-fixtures"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pristine_tree_passes(self) -> None:
        result = run_validator(self.tree)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mutated_canonical_vector_fails(self) -> None:
        path = self.fixtures / "canonical-json" / "vectors.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["vectors"][0]["expected"] += "x"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = run_validator(self.tree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("drifted", result.stderr)

    def test_tampered_golden_signature_fails(self) -> None:
        path = self.fixtures / "pending-gate" / "valid" / "approve-once.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["pending_gate"]["decision"]["note"] = "tampered after signing"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = run_validator(self.tree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approve-once", result.stderr)

    def test_schema_snapshot_drift_fails(self) -> None:
        schema = self.tree / "templates" / "claude" / "console" / "pending-gate.schema.json"
        data = json.loads(schema.read_text(encoding="utf-8"))
        data["description"] = str(data.get("description", "")) + " (drift)"
        schema.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = run_validator(self.tree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema snapshot drift", result.stderr)

    def test_unlisted_fixture_file_fails(self) -> None:
        stray = self.fixtures / "pending-gate" / "valid" / "stray.json"
        stray.write_text("{}", encoding="utf-8")
        result = run_validator(self.tree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not listed", result.stderr)

    def test_version_mismatch_fails(self) -> None:
        (self.tree / "VERSION").write_text("0.0.0\n", encoding="utf-8")
        result = run_validator(self.tree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("framework_version", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
