#!/usr/bin/env python3
"""Unit tests for the source-only, explicitly authorized Kimi L2 probe."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import os
import re
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-vm-kimi-l2-probe.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


PROBE = load_module("vm_kimi_l2_probe_test", SCRIPT)


class FakeProvider:
    PROVIDER_ID = "harness-vm-v1"
    PROVIDER_KIND = "vm-v1"
    SHA256 = re.compile(r"^[0-9a-f]{64}$")
    RUNNER_NAMES = ("session-bridge.py", "session_bridge_kimi.py", "vm-bridge-worker.py")
    MAX_ENVELOPE_BYTES = 1024 * 1024
    MAX_TARGET_BYTES = 1024 * 1024
    MAX_CLI_BUNDLE_BYTES = 32 * 1024 * 1024
    MAX_RUNNER_BYTES = 2 * 1024 * 1024
    MAX_COPYIN_ARCHIVE_BYTES = 1024 * 1024
    MAX_SOURCE_ARCHIVE_ENTRIES = 10_000
    read_calls: list[Path] = []

    @staticmethod
    def _canonical_sha256(domain: str, value: object) -> str:
        encoded = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(domain.encode("ascii") + b"\0" + encoded).hexdigest()

    @staticmethod
    def _secure_directory(path: Path, _label: str) -> None:
        entry = path.lstat()
        if stat.S_ISLNK(entry.st_mode) or not stat.S_ISDIR(entry.st_mode):
            raise ValueError("not a directory")

    @staticmethod
    def _secure_regular_file(path: Path, _label: str, *, require_private: bool = False) -> None:
        entry = path.lstat()
        if stat.S_ISLNK(entry.st_mode) or not stat.S_ISREG(entry.st_mode):
            raise ValueError("not a regular file")
        if require_private and stat.S_IMODE(entry.st_mode) & 0o077:
            raise ValueError("not private")

    @classmethod
    def _read_regular_file_capped(cls, path: Path, _label: str, maximum_bytes: int) -> bytes:
        cls.read_calls.append(path)
        value = path.read_bytes()
        if len(value) > maximum_bytes:
            raise ValueError("too large")
        return value

    @staticmethod
    def _sha256_path(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_bridge(*, digest: str = "b" * 64) -> object:
    return PROBE.SourceBridgeManifest(
        bridge_id="kimi-acp-native-agent",
        strategy="session-bridge-v1",
        protocol_kind="acp-native-agent/v1",
        protocol_command=("kimi", "acp"),
        request_delivery="stdin",
        response_format="json",
        generator_persona="generator-restricted",
        generator_native_agent_type="coder",
        sha256=digest,
    )


class VmKimiL2ProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(
            prefix="vm-kimi-l2-probe-test-", dir=ROOT
        )
        self.root = Path(self.temp.name)
        self.provider_home = self.root / "provider-home"
        self.provider_home.mkdir(mode=0o700)
        self.provider_home_patch = mock.patch.object(
            PROBE, "_provider_account_home", return_value=self.provider_home
        )
        self.provider_home_patch.start()
        FakeProvider.read_calls.clear()

    def tearDown(self) -> None:
        self.provider_home_patch.stop()
        self.temp.cleanup()

    def _source_fixture_root(self) -> Path:
        source_root = self.root / "source-root"
        script = source_root / "scripts" / "run-vm-kimi-l2-probe.py"
        script.parent.mkdir(parents=True, mode=0o700)
        script.write_text("# fixture source root\n", encoding="utf-8")
        script.chmod(0o600)
        return source_root

    def _write_source_bundle(
        self,
        source_root: Path,
        provider_source: str,
        *,
        runners: dict[str, bytes] | None = None,
    ) -> Path:
        """Build the complete source asset set that the pinned loader requires."""
        transports = (
            source_root / "templates" / "claude" / "dispatch" / "transports"
        )
        transports.mkdir(parents=True, mode=0o700)
        provider = transports / "vm-bridge-provider.py"
        provider.write_text(provider_source, encoding="utf-8")
        provider.chmod(0o600)
        runner_bytes = runners or {
            name: f"trusted runner {name}\n".encode("ascii")
            for name in PROBE.SOURCE_RUNNER_NAMES
        }
        self.assertEqual(set(runner_bytes), set(PROBE.SOURCE_RUNNER_NAMES))
        for name in PROBE.SOURCE_RUNNER_NAMES:
            path = transports / name
            path.write_bytes(runner_bytes[name])
            path.chmod(0o600)
        bridge = transports / "bridges" / "kimi-acp-native-agent.json"
        bridge.parent.mkdir(mode=0o700)
        bridge.write_text(
            json.dumps(
                {
                    "_comment": "fixture",
                    "id": "kimi-acp-native-agent",
                    "_verified": True,
                    "session_scope": "same-session",
                    "strategy": "session-bridge-v1",
                    "protocol": dict(PROBE.EXPECTED_BRIDGE_PROTOCOL),
                    "personas": {
                        "planner": "planner-proposal",
                        "generator": "generator-restricted",
                        "evaluator": "evaluator",
                    },
                    "native_agent_types": {
                        "planner": "coder",
                        "generator": "coder",
                        "evaluator": "explore",
                    },
                    "notes": "fixture",
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        bridge.chmod(0o600)
        return provider

    def test_confirmation_must_be_exact_and_failure_stays_sanitized(self) -> None:
        with mock.patch.object(PROBE, "run_probe") as run:
            with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(PROBE.main([]), 2)
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), PROBE._refused_evidence())
        self.assertEqual(
            json.loads(output.getvalue())["confirmation_mode"],
            PROBE.OUT_OF_BAND_MANUAL_CONFIRMATION,
        )

        with mock.patch.object(PROBE, "run_probe") as run:
            with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(PROBE.main([PROBE.CONFIRMATION_FLAG, "extra"]), 2)
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["outcome"], "refused")

        passed = {"version": PROBE.PROBE_VERSION, "outcome": "passed"}
        with mock.patch.object(PROBE, "run_probe", return_value=passed) as run:
            with mock.patch.object(PROBE, "_has_isolated_runtime", return_value=True):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(PROBE.main([PROBE.CONFIRMATION_FLAG]), 0)
        run.assert_called_once_with(confirmed=True)
        self.assertEqual(json.loads(output.getvalue()), passed)

        with mock.patch.object(PROBE, "run_probe", side_effect=RuntimeError("credential=secret")):
            with mock.patch.object(PROBE, "_has_isolated_runtime", return_value=True):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(PROBE.main([PROBE.CONFIRMATION_FLAG]), 2)
        self.assertEqual(json.loads(output.getvalue()), PROBE._failure_evidence())
        self.assertNotIn("secret", output.getvalue())

    def test_isolated_runtime_is_required_before_provider_or_source_loading(self) -> None:
        with mock.patch.object(PROBE, "_has_isolated_runtime", return_value=False):
            with mock.patch.object(PROBE, "load_source_provider") as loader:
                with self.assertRaisesRegex(PROBE.ProbeError, "isolated Python runtime"):
                    PROBE.run_probe(confirmed=True)
        loader.assert_not_called()

        with mock.patch.object(PROBE, "_has_isolated_runtime", return_value=False):
            with mock.patch.object(PROBE, "run_probe") as run:
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(PROBE.main([PROBE.CONFIRMATION_FLAG]), 2)
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), PROBE._isolated_runtime_refused_evidence())

    def test_run_probe_requires_an_explicit_boolean_confirmation_before_loading_source(self) -> None:
        with mock.patch.object(PROBE, "load_source_provider") as loader:
            with self.assertRaises(PROBE.ProbeError):
                PROBE.run_probe(confirmed=False)
            with self.assertRaises(PROBE.ProbeError):
                PROBE.run_probe(confirmed=1)
        loader.assert_not_called()

    def test_fixed_target_is_generator_coder_and_bundle_bound(self) -> None:
        configuration = SimpleNamespace(contract_sha256="a" * 64)
        bridge = fixed_bridge()
        target = PROBE._fixed_target(FakeProvider, configuration, bridge)

        self.assertEqual(target["tool"], "kimi")
        self.assertEqual(target["roles"], ["generator"])
        self.assertEqual(target["agent_type"], "generator-restricted")
        self.assertEqual(target["native_agent_type"], "coder")
        self.assertEqual(target["bridge_protocol"], {
            "kind": "acp-native-agent/v1",
            "command": ["kimi", "acp"],
            "request_delivery": "stdin",
            "response_format": "json",
        })
        self.assertEqual(target["timeout_s"], PROBE.PROBE_TIMEOUT_SECONDS)
        self.assertEqual(target["bridge_provider_contract_sha256"], "a" * 64)
        self.assertEqual(target["bridge_id"], bridge.bridge_id)
        self.assertEqual(target["bridge_strategy"], bridge.strategy)
        self.assertRegex(target["adapter_execution_contract_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(target["execution_provenance_sha256"], r"^[0-9a-f]{64}$")

    def test_source_bridge_manifest_is_verified_and_generator_coder_only(self) -> None:
        bridge = PROBE.load_source_kimi_bridge_manifest()
        self.assertEqual(bridge.bridge_id, "kimi-acp-native-agent")
        self.assertEqual(bridge.strategy, "session-bridge-v1")
        self.assertEqual(bridge.protocol(), PROBE.EXPECTED_BRIDGE_PROTOCOL)
        self.assertEqual(bridge.generator_persona, "generator-restricted")
        self.assertEqual(bridge.generator_native_agent_type, "coder")
        self.assertRegex(bridge.sha256, r"^[0-9a-f]{64}$")

        valid = {
            "_comment": "fixture",
            "id": "kimi-acp-native-agent",
            "_verified": True,
            "session_scope": "same-session",
            "strategy": "session-bridge-v1",
            "protocol": dict(PROBE.EXPECTED_BRIDGE_PROTOCOL),
            "personas": {
                "planner": "planner-proposal",
                "generator": "generator-restricted",
                "evaluator": "evaluator",
            },
            "native_agent_types": {
                "planner": "coder",
                "generator": "plan",
                "evaluator": "explore",
            },
            "notes": "fixture",
        }
        mutations = {
            "unverified": lambda item: item.__setitem__("_verified", False),
            "wrong session": lambda item: item.__setitem__("session_scope", "new-session"),
            "wrong command": lambda item: item["protocol"].__setitem__("command", ["other", "acp"]),
            "wrong persona": lambda item: item["personas"].__setitem__("generator", "planner-proposal"),
            "wrong native type": lambda item: item["native_agent_types"].__setitem__("generator", "plan"),
            "extra field": lambda item: item.__setitem__("unexpected", True),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                invalid = json.loads(json.dumps(valid))
                mutate(invalid)
                with self.assertRaises(PROBE.ProbeError):
                    PROBE._validated_source_bridge_manifest(invalid, "c" * 64)

    def test_private_probe_binding_covers_nonce_snapshots_and_manifest(self) -> None:
        target = PROBE._fixed_target(
            FakeProvider, SimpleNamespace(contract_sha256="a" * 64), fixed_bridge()
        )
        binding = PROBE._create_probe_binding(
            FakeProvider,
            target=target,
            bridge=fixed_bridge(),
            provider_source_sha256="5" * 64,
            envelope_sha256="1" * 64,
            runner_sha256="2" * 64,
            cli_bundle_sha256="3" * 64,
            nonce="4" * 32,
        )
        different_manifest = PROBE._create_probe_binding(
            FakeProvider,
            target=target,
            bridge=fixed_bridge(digest="d" * 64),
            provider_source_sha256="5" * 64,
            envelope_sha256="1" * 64,
            runner_sha256="2" * 64,
            cli_bundle_sha256="3" * 64,
            nonce="4" * 32,
        )
        self.assertEqual(binding.nonce, "4" * 32)
        self.assertEqual(binding.bridge_manifest_sha256, "b" * 64)
        self.assertEqual(binding.provider_source_sha256, "5" * 64)
        self.assertRegex(binding.sha256, r"^[0-9a-f]{64}$")
        self.assertNotEqual(binding.sha256, different_manifest.sha256)
        different_provider = PROBE._create_probe_binding(
            FakeProvider,
            target=target,
            bridge=fixed_bridge(),
            provider_source_sha256="6" * 64,
            envelope_sha256="1" * 64,
            runner_sha256="2" * 64,
            cli_bundle_sha256="3" * 64,
            nonce="4" * 32,
        )
        self.assertNotEqual(binding.sha256, different_provider.sha256)

    def test_fixed_envelope_has_no_project_input_and_requires_manual_confirmation(self) -> None:
        with self.assertRaises(PROBE.ProbeError):
            PROBE._fixed_envelope(confirmed=False)
        with self.assertRaises(PROBE.ProbeError):
            PROBE._fixed_envelope(confirmed=1)
        envelope = PROBE._fixed_envelope(confirmed=True)

        self.assertEqual(envelope["role"], "generator")
        self.assertTrue(envelope["l2_authorized"])
        self.assertEqual(envelope["deadline_s"], PROBE.PROBE_TIMEOUT_SECONDS)
        self.assertEqual(envelope["repo"]["url"], "synthetic://harness/vm-kimi-l2")
        self.assertEqual(envelope["deliverable"]["artifact"], PROBE.ARTIFACT_PATH)
        self.assertIn('"probe":"harness-vm-kimi-l2"', envelope["contract"])
        self.assertIn('"result":"completed"', envelope["contract"])
        self.assertNotIn("project_root", envelope)
        self.assertNotIn("registry", envelope)
        self.assertNotIn("pending_gate", envelope)

    def test_fixed_archive_contains_only_synthetic_source_and_private_snapshots(self) -> None:
        inputs = self.root / "inputs"
        runners = inputs / "runners"
        runners.mkdir(parents=True, mode=0o700)

        def write_private(path: Path, contents: bytes) -> Path:
            path.write_bytes(contents)
            os.chmod(path, 0o600)
            return path

        snapshot = SimpleNamespace(
            envelope=write_private(inputs / "envelope.json", b'{"fixed":true}\n'),
            target=write_private(inputs / "target.json", b'{"target":"kimi"}\n'),
            cli_bundle=write_private(inputs / "kimi.tar.gz", b"fixed-bundle"),
            runners={
                name: write_private(runners / name, f"runner:{name}".encode("ascii"))
                for name in FakeProvider.RUNNER_NAMES
            },
        )
        archive_path = self.root / "copyin.tar.gz"
        PROBE._create_fixed_probe_archive(
            FakeProvider, snapshots=snapshot, destination=archive_path
        )
        self.assertEqual(FakeProvider.read_calls, [])

        with tarfile.open(archive_path, mode="r:gz") as archive:
            expected = {
                "source/README.md",
                ".harness-envelope.json",
                ".harness-target.json",
                ".harness-cli-bundle.tar.gz",
                *(f".harness-runner/{name}" for name in FakeProvider.RUNNER_NAMES),
            }
            self.assertEqual(set(archive.getnames()), expected)
            self.assertNotIn("source/.git", archive.getnames())
            self.assertNotIn("source/AGENTS.md", archive.getnames())
            source = archive.extractfile("source/README.md")
            assert source is not None
            self.assertEqual(source.read(), PROBE.FIXED_SOURCE_FILES["README.md"])

    def test_fixed_archive_rejects_raw_aggregate_and_compressed_size_overages(self) -> None:
        inputs = self.root / "inputs"
        runners = inputs / "runners"
        runners.mkdir(parents=True, mode=0o700)

        def write_private(path: Path, contents: bytes) -> Path:
            path.write_bytes(contents)
            os.chmod(path, 0o600)
            return path

        def random_bytes(label: str) -> bytes:
            return b"".join(
                hashlib.sha256(f"{label}-{index}".encode("ascii")).digest()
                for index in range(256)
            )

        snapshot = SimpleNamespace(
            envelope=write_private(inputs / "envelope.json", random_bytes("envelope")),
            target=write_private(inputs / "target.json", random_bytes("target")),
            cli_bundle=write_private(inputs / "kimi.tar.gz", random_bytes("bundle")),
            runners={
                name: write_private(runners / name, random_bytes(name))
                for name in FakeProvider.RUNNER_NAMES
            },
        )
        entries = PROBE._fixed_archive_entries(FakeProvider, snapshot)
        raw_total = sum(entry.size for entry in entries)
        with mock.patch.object(FakeProvider, "MAX_COPYIN_ARCHIVE_BYTES", raw_total - 1):
            with self.assertRaises(PROBE.ProbeError):
                PROBE._fixed_archive_entries(FakeProvider, snapshot)

        with mock.patch.object(FakeProvider, "MAX_SOURCE_ARCHIVE_ENTRIES", len(entries) - 1):
            with self.assertRaises(PROBE.ProbeError):
                PROBE._fixed_archive_entries(FakeProvider, snapshot)

        archive_path = self.root / "compressed-overage.tar.gz"
        with mock.patch.object(FakeProvider, "MAX_COPYIN_ARCHIVE_BYTES", raw_total):
            with self.assertRaises(PROBE.ProbeError):
                PROBE._create_fixed_probe_archive(
                    FakeProvider, snapshots=snapshot, destination=archive_path
                )
        self.assertFalse(archive_path.exists())

    def test_return_validation_rejects_any_uncommissioned_source_effect(self) -> None:
        copyout = self.root / "copyout"
        copyout.mkdir(mode=0o700)
        source = copyout / "README.md"
        artifact = copyout / "artifact.json"
        receipt = copyout / "receipt.json"
        source.write_bytes(PROBE.FIXED_SOURCE_FILES["README.md"])
        artifact.write_text(json.dumps(PROBE.EXPECTED_ARTIFACT), encoding="utf-8")
        receipt.write_text("{}", encoding="utf-8")
        for path in (source, artifact, receipt):
            os.chmod(path, 0o600)

        extracted = {
            "receipt/bridge-result.json": receipt,
            "source/README.md": source,
            f"source/{PROBE.ARTIFACT_PATH}": artifact,
        }
        observed_artifact, observed_sha = PROBE._verify_fixed_return(FakeProvider, extracted)
        self.assertEqual(observed_artifact, artifact)
        self.assertRegex(observed_sha, r"^[0-9a-f]{64}$")

        extra = copyout / "extra.txt"
        extra.write_text("unexpected", encoding="utf-8")
        os.chmod(extra, 0o600)
        extracted["source/extra.txt"] = extra
        with self.assertRaises(PROBE.ProbeError):
            PROBE._verify_fixed_return(FakeProvider, extracted)

    def test_evidence_drops_raw_receipt_data_and_paths(self) -> None:
        receipt = {
            "bridge_kind": "acp-native-agent/v1",
            "session_scope": "same-session",
            "subagent_type": "coder",
            "terminal_status": "completed",
            "session_id_sha256": "1" * 64,
            "child_call_id_sha256": "2" * 64,
            "raw_model_text": "must-not-escape",
            "credential_path": "/private/not-for-output",
        }
        evidence = PROBE._sanitized_evidence(
            FakeProvider,
            receipt=receipt,
            artifact_sha256="3" * 64,
            probe_binding_sha256="4" * 64,
            bridge_manifest_sha256="5" * 64,
            provider_source_sha256="6" * 64,
            duration_s=1,
        )
        serialized = json.dumps(evidence, sort_keys=True)
        self.assertEqual(evidence["scope"], "evaluator-controlled-fixed-generator-child")
        self.assertEqual(
            evidence["l2_confirmation"], PROBE.OUT_OF_BAND_MANUAL_CONFIRMATION
        )
        self.assertEqual(
            evidence["runtime"], PROBE.ISOLATED_RUNTIME_LAUNCH_REQUIREMENT
        )
        self.assertEqual(evidence["probe_binding_sha256"], "4" * 64)
        self.assertEqual(evidence["bridge_manifest_sha256"], "5" * 64)
        self.assertEqual(evidence["provider_source_sha256"], "6" * 64)
        self.assertNotIn("launch_attestation_sha256", evidence)
        self.assertNotIn("raw_model_text", evidence)
        self.assertNotIn("credential_path", serialized)
        self.assertNotIn("must-not-escape", serialized)
        self.assertNotIn("/private", serialized)
        self.assertNotIn("pending_gate", evidence)

    def test_firewall_reset_runs_when_guest_cleanup_fails(self) -> None:
        calls: list[str] = []

        def cleanup(*_args: object) -> None:
            calls.append("cleanup")
            raise RuntimeError("cleanup failed")

        def reset(*_args: object) -> None:
            calls.append("reset")

        provider = SimpleNamespace(
            _cleanup_guest_job=cleanup,
            _reset_guest_egress_baseline=reset,
        )
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            PROBE._cleanup_probe_guest(
                provider,
                object(),
                guest_root="/var/lib/harness-vm-v1/jobs/" + "a" * 32,
                unit="harness-vm-kimi-l2-" + "a" * 32,
                vendor_drop_unit="harness-vm-kimi-l2-" + "a" * 32 + "-drop",
                guest_job_touched=True,
                firewall_reset_required=True,
            )
        self.assertEqual(calls, ["cleanup", "reset"])

    def test_vendor_drop_preflight_uses_exact_root_profile_without_a_broker(self) -> None:
        calls: list[dict[str, object]] = []

        def run_unit(*_args: object, **kwargs: object) -> object:
            calls.append(kwargs)
            return SimpleNamespace(
                returncode=0, stdout=PROBE.VENDOR_DROP_PREFLIGHT_SENTINEL
            )

        provider = SimpleNamespace(_guest_restricted_unit=run_unit)
        guest_root = "/var/lib/harness-vm-v1/jobs/" + "a" * 32
        unit = "harness-vm-kimi-l2-" + "a" * 32 + "-drop"
        PROBE._verify_vendor_drop_preflight(
            provider, object(), guest_root=guest_root, unit=unit
        )
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["guest_root"], guest_root)
        self.assertEqual(call["unit"], unit)
        self.assertEqual(call["timeout"], PROBE.VENDOR_DROP_PREFLIGHT_TIMEOUT_SECONDS)
        self.assertIsNone(call["network_host"])
        self.assertTrue(call["root_supervisor"])
        self.assertEqual(
            call["environment"],
            {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        self.assertEqual(call["program"], list(PROBE.VENDOR_DROP_PREFLIGHT_PROGRAM))
        self.assertIn("--clear-groups", call["program"])
        self.assertIn("--inh-caps=-all", call["program"])
        self.assertIn("--ambient-caps=-all", call["program"])
        self.assertIn("--no-new-privs", call["program"])

        with self.assertRaisesRegex(PROBE.ProbeError, "privilege-drop"):
            PROBE._verify_vendor_drop_preflight(
                SimpleNamespace(
                    _guest_restricted_unit=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0, stdout=b"wrong\n"
                    )
                ),
                object(),
                guest_root=guest_root,
                unit=unit,
            )

    def test_static_boundaries_prevent_production_entrypoint_or_git_dispatch_use(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("importlib", source)
        self.assertNotIn("spec_from_file_location", source)
        self.assertNotIn("module_from_spec", source)
        self.assertNotIn("exec_module", source)
        self.assertNotIn("SourceFileLoader", source)
        self.assertNotIn("sys.path.append", source)
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("sys.path.extend", source)
        self.assertNotIn("sys.path =", source)
        self.assertNotIn("__pycache__", source)
        self.assertNotIn('getattr(os, "O_NOFOLLOW", 0)', source)
        self.assertIn("_read_source_regular_file", source)
        self.assertIn("O_NOFOLLOW", source)
        self.assertIn("O_DIRECTORY", source)
        self.assertIn("dir_fd=parent_fd", source)
        self.assertIn("os.fstat", source)
        self.assertIn("compile(bundle.provider_source", source)
        self.assertIn("exec(code", source)
        self.assertIn("_read_pinned_source_bundle", source)
        self.assertIn("_validate_pinned_runner_snapshots", source)
        self.assertIn("SOURCE_RUNNER_NAMES", source)
        self.assertIn("dir_fd=stage_fd", source)
        self.assertNotIn('TemporaryDirectory(prefix="harness-vm-kimi-l2-source-"', source)
        self.assertIn("values != [CONFIRMATION_FLAG]", source)
        self.assertIn("_has_isolated_runtime", source)
        self.assertIn('getattr(flags, "isolated", 0) != 1', source)
        self.assertIn('ISOLATED_RUNTIME_LAUNCH_REQUIREMENT = "/usr/bin/python3 -I"', source)
        self.assertIn("out-of-band-manual-confirmation", source)
        self.assertNotIn(".tokenizer/app", source)
        self.assertNotIn("tool-catalog", source)
        self.assertNotIn("dispatch-run", source)
        self.assertNotIn("dispatch-generator-handoff", source)
        self.assertNotIn("dispatch-planner-proposal", source)
        self.assertNotIn("progress.json", source)
        self.assertNotIn(".agents-registry.json", source)
        self.assertNotIn("autodrive", source)
        self.assertNotIn("console", source)
        self.assertNotIn("approve-gate", source)
        self.assertNotIn("pending_gate", source)
        self.assertNotIn("provider.launch(", source)
        self.assertNotIn("provider.launch_attestation(", source)
        self.assertNotIn("catalog_attestation", source)
        self.assertNotIn("provider.doctor(", source)
        self.assertNotIn("subprocess", source)
        self.assertNotRegex(source, r"(?<![A-Za-z0-9_])[\"']git[\"']")
        self.assertIn("receipt/bridge-result.json", source)
        self.assertNotIn("state/bridge-result.json", source)
        self.assertIn("evaluator-controlled-fixed-generator-child", source)

        dispatch_entrypoint = ROOT / "templates/claude/dispatch/dispatch-run.sh"
        self.assertTrue(dispatch_entrypoint.is_file())
        self.assertNotIn(dispatch_entrypoint.name, source)
        self.assertEqual(PROBE._source_root(), ROOT)
        self.assertEqual(
            PROBE._source_provider_path(),
            ROOT / "templates/claude/dispatch/transports/vm-bridge-provider.py",
        )

        tree = ast.parse(source)

        def is_sys_path_target(node: ast.AST) -> bool:
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
                and node.attr == "path"
            ):
                return True
            return isinstance(node, ast.Subscript) and is_sys_path_target(node.value)

        assigned_sys_path = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                )
                assigned_sys_path = assigned_sys_path or any(
                    is_sys_path_target(target) for target in targets
                )
        self.assertFalse(assigned_sys_path)

        sys_path_mutators = {
            "append",
            "clear",
            "extend",
            "insert",
            "pop",
            "remove",
            "reverse",
            "sort",
        }
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in sys_path_mutators
                and is_sys_path_target(node.func.value)
                for node in ast.walk(tree)
            )
        )

        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "provider"
        }
        self.assertNotIn("launch", calls)
        self.assertNotIn("launch_attestation", calls)
        self.assertNotIn("catalog_attestation", calls)
        self.assertNotIn("doctor", calls)
        self.assertIn("_run_guest_worker", calls)

    def test_source_loader_executes_verified_bytes_without_loader_or_pycache(self) -> None:
        source_root = self._source_fixture_root()
        provider_path = self._write_source_bundle(
            source_root,
            "RUNNER_NAMES = " + repr(PROBE.SOURCE_RUNNER_NAMES) + "\n"
            "MARKER = 'stable-source-bytes'\n",
        )
        cache_directory = provider_path.parent / "__pycache__"
        module_name = "_harness_vm_kimi_l2_source_provider"
        previous = sys.modules.get(module_name)
        provider = None

        try:
            with mock.patch.object(PROBE, "_source_root", return_value=source_root):
                provider = PROBE.load_source_provider()
            self.assertEqual(provider.MARKER, "stable-source-bytes")
            self.assertIsNone(provider.__loader__)
            self.assertIsNone(provider.__spec__)
            self.assertIsNone(provider.__cached__)
            self.assertFalse(cache_directory.exists())
            self.assertNotEqual(Path(provider.__file__).parent, provider_path.parent)
            self.assertEqual(stat.S_IMODE(Path(provider.__file__).stat().st_mode), 0o600)
        finally:
            if provider is not None:
                session = PROBE._source_provider_session(provider)
                assert session is not None
                session.close()
            if previous is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous

    def test_source_read_rejects_fstat_toctou_drift(self) -> None:
        source_root = self._source_fixture_root()
        source_path = source_root / "stable-provider.py"
        source_path.write_text("MARKER = 1\n", encoding="utf-8")
        source_path.chmod(0o600)
        real_fstat = os.fstat
        source_inode = source_path.stat().st_ino
        source_calls = 0

        def fstat_with_drift(descriptor: int) -> object:
            nonlocal source_calls
            value = real_fstat(descriptor)
            if stat.S_ISREG(value.st_mode) and value.st_ino == source_inode:
                source_calls += 1
            if source_calls == 3:
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_dev=value.st_dev,
                    st_ino=value.st_ino,
                    st_size=value.st_size + 1,
                    st_nlink=value.st_nlink,
                    st_mtime_ns=value.st_mtime_ns,
                    st_ctime_ns=value.st_ctime_ns,
                )
            return value

        with mock.patch.object(PROBE, "_source_root", return_value=source_root):
            with mock.patch.object(PROBE.os, "fstat", side_effect=fstat_with_drift):
                with self.assertRaisesRegex(PROBE.ProbeError, "changed while it was being read"):
                    PROBE._read_source_regular_file(source_path, "test source", 1024)
        self.assertEqual(source_calls, 3)

    def test_staged_provider_runner_reads_survive_source_ancestor_swap(self) -> None:
        source_root = self._source_fixture_root()
        trusted_runners = {
            name: f"trusted:{name}\n".encode("ascii")
            for name in PROBE.SOURCE_RUNNER_NAMES
        }
        provider_source = (
            "from pathlib import Path\n"
            "RUNNER_NAMES = " + repr(PROBE.SOURCE_RUNNER_NAMES) + "\n"
            "def read_sibling_runners():\n"
            "    root = Path(__file__).absolute().parent\n"
            "    return {name: (root / name).read_bytes() for name in RUNNER_NAMES}\n"
        )
        trusted_path = self._write_source_bundle(
            source_root, provider_source, runners=trusted_runners
        )
        malicious_parent = self.root / "malicious-transports"
        malicious_parent.mkdir(mode=0o700)
        for name in PROBE.SOURCE_RUNNER_NAMES:
            malicious_path = malicious_parent / name
            malicious_path.write_bytes(f"malicious:{name}\n".encode("ascii"))
            malicious_path.chmod(0o600)
        original_parent = trusted_path.parent
        moved_parent = original_parent.with_name("transports-trusted")
        module_name = "_harness_vm_kimi_l2_source_provider"
        previous = sys.modules.get(module_name)
        provider = None

        try:
            with mock.patch.object(PROBE, "_source_root", return_value=source_root):
                provider = PROBE.load_source_provider()
            original_parent.rename(moved_parent)
            original_parent.symlink_to(malicious_parent, target_is_directory=True)
            self.assertEqual(provider.read_sibling_runners(), trusted_runners)
            self.assertNotEqual(Path(provider.__file__).parent, original_parent)
        finally:
            if provider is not None:
                session = PROBE._source_provider_session(provider)
                assert session is not None
                session.close()
            if previous is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous

    def test_source_stage_does_not_consult_tmpdir(self) -> None:
        source_root = self._source_fixture_root()
        self._write_source_bundle(
            source_root,
            "RUNNER_NAMES = " + repr(PROBE.SOURCE_RUNNER_NAMES) + "\n"
            "MARKER = 'tmpdir-independent'\n",
        )
        hostile_tmpdir = self.root / "hostile-tmpdir"
        hostile_tmpdir.mkdir(mode=0o700)
        provider = None
        try:
            with mock.patch.dict(os.environ, {"TMPDIR": str(hostile_tmpdir)}, clear=False):
                with mock.patch.object(
                    PROBE.tempfile,
                    "TemporaryDirectory",
                    side_effect=AssertionError("source staging used TMPDIR"),
                ):
                    with mock.patch.object(PROBE, "_source_root", return_value=source_root):
                        provider = PROBE.load_source_provider()
            self.assertEqual(provider.MARKER, "tmpdir-independent")
            self.assertNotIn(str(hostile_tmpdir), provider.__file__)
        finally:
            if provider is not None:
                session = PROBE._source_provider_session(provider)
                assert session is not None
                session.close()

    def test_runner_snapshot_aggregate_must_match_pinned_runner_digests(self) -> None:
        digests = {
            name: hashlib.sha256(name.encode("ascii")).hexdigest()
            for name in PROBE.SOURCE_RUNNER_NAMES
        }
        expected = FakeProvider._canonical_sha256("harness/vm-bridge-runner/v1", digests)
        session = SimpleNamespace(closed=False, runner_sha256=digests)
        PROBE._validate_pinned_runner_snapshots(
            FakeProvider, SimpleNamespace(runner_sha256=expected), session
        )
        with self.assertRaisesRegex(PROBE.ProbeError, "does not match pinned source"):
            PROBE._validate_pinned_runner_snapshots(
                FakeProvider, SimpleNamespace(runner_sha256="0" * 64), session
            )

    def test_source_and_archive_streaming_fail_closed_without_o_nofollow(self) -> None:
        source_root = self._source_fixture_root()
        source_path = source_root / "stable-provider.py"
        source_path.write_text("MARKER = 1\n", encoding="utf-8")
        source_path.chmod(0o600)
        source_entry = source_path.stat()
        archive_entry = PROBE._ArchiveEntry(
            name="snapshot.json",
            label="fixed snapshot",
            size=source_entry.st_size,
            source=source_path,
            source_device=source_entry.st_dev,
            source_inode=source_entry.st_ino,
        )

        with mock.patch.object(PROBE.os, "O_NOFOLLOW", 0):
            with mock.patch.object(PROBE, "_source_root", return_value=source_root):
                with self.assertRaisesRegex(PROBE.ProbeError, "cannot be opened securely"):
                    PROBE._read_source_regular_file(source_path, "test source", 1024)
            with tarfile.open(fileobj=io.BytesIO(), mode="w") as archive:
                with self.assertRaisesRegex(PROBE.ProbeError, "cannot be opened securely"):
                    PROBE._stream_archive_entry(archive, archive_entry)


if __name__ == "__main__":
    unittest.main()
