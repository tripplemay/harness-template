#!/usr/bin/env python3
"""Regression coverage for the framework release contract validator."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate-framework-release-contract.py"
MANIFEST_RELATIVE_PATH = Path("framework/harness/framework-releases.json")
CURRENT_VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

# These paths are the v2 control-plane minimum.  Keep this list deliberately
# small and capability-focused: new CLI adapters are discovered from the
# managed registry/catalog rather than being added to a frontend allow-list.
V2_REQUIRED_MANAGED = (
    (Path("templates/claude/agents/planner-proposal.md"), Path(".claude/agents/planner-proposal.md")),
    (Path("templates/claude/autonomous/gate-arbiter.workflow.js"), Path(".claude/autonomous/gate-arbiter.workflow.js")),
    (Path("templates/claude/console/mode-intent.schema.json"), Path(".claude/console/mode-intent.schema.json")),
    (Path("templates/claude/console/consume-mode-intent.sh"), Path(".claude/console/consume-mode-intent.sh")),
    (Path("templates/claude/console/resolve-mode-bindings.sh"), Path(".claude/console/resolve-mode-bindings.sh")),
    (Path("templates/claude/console/validate-mode-intent.sh"), Path(".claude/console/validate-mode-intent.sh")),
    (Path("templates/claude/dispatch/agents-registry.schema.json"), Path(".claude/dispatch/agents-registry.schema.json")),
    (Path("templates/claude/dispatch/subagent-bridge.schema.json"), Path(".claude/dispatch/subagent-bridge.schema.json")),
    (Path("templates/claude/dispatch/dispatch-envelope.schema.json"), Path(".claude/dispatch/dispatch-envelope.schema.json")),
    (Path("templates/claude/dispatch/dispatch-run.sh"), Path(".claude/dispatch/dispatch-run.sh")),
    (Path("templates/claude/dispatch/dispatch_common.py"), Path(".claude/dispatch/dispatch_common.py")),
    (Path("templates/claude/dispatch/tool-catalog.py"), Path(".claude/dispatch/tool-catalog.py")),
    (Path("templates/claude/dispatch/validate-active-return-route.py"), Path(".claude/dispatch/validate-active-return-route.py")),
    (Path("templates/claude/dispatch/validate-external-bridge-receipt.py"), Path(".claude/dispatch/validate-external-bridge-receipt.py")),
    (Path("templates/claude/dispatch/resolve-active-mode-role.sh"), Path(".claude/dispatch/resolve-active-mode-role.sh")),
    (Path("templates/claude/dispatch/validate-resolved-mode-bindings.sh"), Path(".claude/dispatch/validate-resolved-mode-bindings.sh")),
    (Path("templates/claude/dispatch/sandbox-profile.sh"), Path(".claude/dispatch/sandbox-profile.sh")),
    (Path("templates/claude/dispatch/planner-proposal.schema.json"), Path(".claude/dispatch/planner-proposal.schema.json")),
    (Path("templates/claude/dispatch/prepare-planner-proposal.sh"), Path(".claude/dispatch/prepare-planner-proposal.sh")),
    (Path("templates/claude/dispatch/dispatch-planner-proposal.sh"), Path(".claude/dispatch/dispatch-planner-proposal.sh")),
    (Path("templates/claude/dispatch/accept-planner-proposal.sh"), Path(".claude/dispatch/accept-planner-proposal.sh")),
    (Path("templates/claude/dispatch/validate-planner-proposal.sh"), Path(".claude/dispatch/validate-planner-proposal.sh")),
    (Path("templates/claude/dispatch/generator-handoff.schema.json"), Path(".claude/dispatch/generator-handoff.schema.json")),
    (Path("templates/claude/dispatch/dispatch-generator-handoff.sh"), Path(".claude/dispatch/dispatch-generator-handoff.sh")),
    (Path("templates/claude/dispatch/accept-generator-handoff.sh"), Path(".claude/dispatch/accept-generator-handoff.sh")),
    (Path("templates/claude/dispatch/validate-generator-handoff.sh"), Path(".claude/dispatch/validate-generator-handoff.sh")),
    (Path("templates/claude/dispatch/transports/a2a-client.py"), Path(".claude/dispatch/transports/a2a-client.py")),
    (Path("templates/claude/dispatch/transports/a2a-runner.py"), Path(".claude/dispatch/transports/a2a-runner.py")),
    (Path("templates/claude/dispatch/transports/session-bridge.py"), Path(".claude/dispatch/transports/session-bridge.py")),
    (Path("templates/claude/dispatch/transports/session-bridge.md"), Path(".claude/dispatch/transports/session-bridge.md")),
    (Path("templates/claude/dispatch/transports/external-bridge-provider.md"), Path(".claude/dispatch/transports/external-bridge-provider.md")),
    (Path("templates/claude/dispatch/transports/external-bridge-provider.schema.json"), Path(".claude/dispatch/transports/external-bridge-provider.schema.json")),
    (Path("templates/claude/dispatch/transports/external-bridge-provider-attestation.schema.json"), Path(".claude/dispatch/transports/external-bridge-provider-attestation.schema.json")),
    (Path("templates/claude/dispatch/transports/vm-bridge-provider.py"), Path(".claude/dispatch/transports/vm-bridge-provider.py")),
    (Path("templates/claude/dispatch/transports/vm-bridge-worker.py"), Path(".claude/dispatch/transports/vm-bridge-worker.py")),
    (Path("templates/claude/dispatch/transports/session_bridge_codex.py"), Path(".claude/dispatch/transports/session_bridge_codex.py")),
    (Path("templates/claude/dispatch/transports/session_bridge_kimi.py"), Path(".claude/dispatch/transports/session_bridge_kimi.py")),
    (Path("templates/claude/dispatch/transports/bridges/kimi-acp-native-agent.json"), Path(".claude/dispatch/transports/bridges/kimi-acp-native-agent.json")),
    (Path("templates/claude/dispatch/transports/adapters/codex.json"), Path(".claude/dispatch/transports/adapters/codex.json")),
    (Path("templates/claude/dispatch/transports/adapters/claude-code.json"), Path(".claude/dispatch/transports/adapters/claude-code.json")),
    (Path("templates/claude/dispatch/transports/adapters/kimi.json"), Path(".claude/dispatch/transports/adapters/kimi.json")),
    (Path("templates/claude/skills/autodrive/SKILL.md"), Path(".claude/skills/autodrive/SKILL.md")),
    (Path("templates/claude/skills/build/SKILL.md"), Path(".claude/skills/build/SKILL.md")),
    (Path("templates/claude/skills/plan/SKILL.md"), Path(".claude/skills/plan/SKILL.md")),
    (Path("templates/claude/skills/verify/SKILL.md"), Path(".claude/skills/verify/SKILL.md")),
    (Path("harness/dispatch-mode.md"), Path("framework/harness/dispatch-mode.md")),
    (Path("harness/harness-rules.md"), Path("harness-rules.md")),
)


def copy_source(destination: Path) -> None:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".DS_Store", ".obsidian", "__pycache__"),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def downgrade_source_to_v152(root: Path) -> None:
    manifest_path = root / "harness" / "framework-releases.json"
    manifest_path.unlink()
    (root / "VERSION").write_text("1.5.2\n", encoding="utf-8")

    changelog_path = root / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    marker = "## v1.5.2 — 2026-07-29"
    _before, separator, historical = changelog.partition(marker)
    if not separator:
        raise AssertionError("fixture source is missing the v1.5.2 changelog entry")
    changelog_path.write_text(historical, encoding="utf-8")

    # Mimic a v1.5.2 project: the pre-v2 lock must not already contain the
    # v2 runtime files, so sync proves that recursive template management
    # carries them. Keep root harness documents available for the legacy
    # adopt fixture below.
    for source_relative, _destination_relative in V2_REQUIRED_MANAGED:
        if source_relative.parts[:2] == ("templates", "claude"):
            candidate = root / source_relative
            if candidate.exists():
                candidate.unlink()


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

    def test_rejects_bare_v1_changelog_title(self) -> None:
        with self.mutated_source() as temporary:
            root = Path(temporary) / "source"
            changelog = root / "CHANGELOG.md"
            changelog.write_text(
                "## v1 — 2026-07-30（fixture）\n\n" + changelog.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("三段式 SemVer", result.stderr)


class FrameworkReleaseDistributionTest(unittest.TestCase):
    def run_harness(
        self, executable: Path, command: str, source: Path, project: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                "bash",
                str(executable),
                command,
                "--from",
                str(source),
                "--project",
                str(project),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_manifest_is_managed(
        self, source: Path, project: Path, expected_version: str
    ) -> None:
        source_manifest = source / "harness" / "framework-releases.json"
        project_manifest = project / MANIFEST_RELATIVE_PATH
        self.assertEqual(project_manifest.read_bytes(), source_manifest.read_bytes())

        lock = json.loads((project / "harness.lock").read_text(encoding="utf-8"))
        meta = lock["managed"][MANIFEST_RELATIVE_PATH.as_posix()]
        self.assertEqual(meta["src"], "harness/framework-releases.json")
        self.assertEqual(meta["sha256"], sha256(project_manifest))
        self.assertEqual(meta["upstream"], sha256(source_manifest))

        config = json.loads((project / "harness.json").read_text(encoding="utf-8"))
        self.assertEqual(config["framework"]["version"], expected_version)

    def assert_v2_control_plane_is_managed(self, source: Path, project: Path) -> None:
        lock = json.loads((project / "harness.lock").read_text(encoding="utf-8"))
        for source_relative, destination_relative in V2_REQUIRED_MANAGED:
            source_path = source / source_relative
            destination_path = project / destination_relative
            self.assertTrue(destination_path.is_file(), destination_relative)
            self.assertEqual(destination_path.read_bytes(), source_path.read_bytes())

            metadata = lock["managed"][destination_relative.as_posix()]
            self.assertEqual(metadata["src"], source_relative.as_posix())
            self.assertEqual(metadata["sha256"], sha256(destination_path))
            self.assertEqual(metadata["upstream"], sha256(source_path))
            if source_path.suffix in {".sh", ".py"}:
                self.assertNotEqual(destination_path.stat().st_mode & 0o111, 0)

    def test_init_sync_and_adopt_then_sync_manage_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="release-distribution-") as raw_temporary:
            temporary = Path(raw_temporary)
            old_source = temporary / "source-v152"
            new_source = temporary / "source-v153"
            copy_source(old_source)
            copy_source(new_source)
            downgrade_source_to_v152(old_source)

            fresh_project = temporary / "fresh-project"
            self.run_harness(
                new_source / "templates" / "claude" / "harness.sh",
                "init",
                new_source,
                fresh_project,
            )
            self.assert_manifest_is_managed(new_source, fresh_project, CURRENT_VERSION)
            self.assert_v2_control_plane_is_managed(new_source, fresh_project)

            project = temporary / "legacy-sync-project"
            self.run_harness(
                old_source / "templates" / "claude" / "harness.sh",
                "init",
                old_source,
                project,
            )
            self.assertFalse((project / MANIFEST_RELATIVE_PATH).exists())
            legacy_lock = json.loads((project / "harness.lock").read_text(encoding="utf-8"))
            self.assertNotIn(MANIFEST_RELATIVE_PATH.as_posix(), legacy_lock["managed"])

            self.run_harness(
                project / ".claude" / "harness.sh", "sync", new_source, project
            )
            self.assert_manifest_is_managed(new_source, project, CURRENT_VERSION)
            self.assert_v2_control_plane_is_managed(new_source, project)

            adopted_project = temporary / "adopt-project"
            adopted_project.mkdir()
            shutil.copy2(
                old_source / "harness" / "harness-rules.md",
                adopted_project / "harness-rules.md",
            )
            self.run_harness(
                old_source / "templates" / "claude" / "harness.sh",
                "adopt",
                old_source,
                adopted_project,
                "--as",
                "1.5.2",
            )

            adopted_lock = json.loads(
                (adopted_project / "harness.lock").read_text(encoding="utf-8")
            )
            self.assertFalse((adopted_project / MANIFEST_RELATIVE_PATH).exists())
            self.assertNotIn(MANIFEST_RELATIVE_PATH.as_posix(), adopted_lock["managed"])

            self.run_harness(
                new_source / "templates" / "claude" / "harness.sh",
                "sync",
                new_source,
                adopted_project,
            )
            self.assert_manifest_is_managed(new_source, adopted_project, CURRENT_VERSION)
            self.assert_v2_control_plane_is_managed(new_source, adopted_project)

    def test_nested_and_flat_bootstrap_manage_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="release-bootstrap-") as raw_temporary:
            temporary = Path(raw_temporary)
            source = temporary / "source"
            copy_source(source)

            nested_project = temporary / "nested-project"
            nested_project.mkdir()
            copy_source(nested_project / "framework")
            nested = subprocess.run(
                ["bash", str(nested_project / "framework" / "bootstrap.sh")],
                cwd=nested_project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(nested.returncode, 0, nested.stdout + nested.stderr)
            self.assert_manifest_is_managed(source, nested_project, CURRENT_VERSION)
            self.assert_v2_control_plane_is_managed(source, nested_project)

            flat_project = temporary / "flat-project"
            copy_source(flat_project)
            flat = subprocess.run(
                ["bash", "bootstrap.sh"],
                cwd=flat_project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(flat.returncode, 0, flat.stdout + flat.stderr)
            self.assert_manifest_is_managed(source, flat_project, CURRENT_VERSION)
            self.assert_v2_control_plane_is_managed(source, flat_project)


if __name__ == "__main__":
    unittest.main()
