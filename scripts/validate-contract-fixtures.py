#!/usr/bin/env python3
"""Validate contract-fixtures/ against the real console machinery.

The fixtures are the machine-checkable cross-repo contract surface (channel B):
canonical-JSON byte semantics, pending-gate decision signatures, and the signed
mode-intent envelope. This validator refuses drift in either direction:

  1. fixtures.json manifest: framework_version equals VERSION and the release
     manifest tail; the schema snapshot hashes equal the live schemas; the file
     enumeration matches the tree exactly (no unlisted, no missing).
  2. canonical-json vectors recompute byte-for-byte.
  3. every pending-gate fixture is replayed through the real
     validate-pending-gate.sh (schema + signature-mode guard with the TEST-ONLY
     public key): valid fixtures must pass all declared checks, invalid ones
     must fail every declared check.
  4. every mode-intent fixture is replayed through the real
     validate-mode-intent.sh inside a scratch git repo bound to the fixture
     repo_key: valid must pass, invalid must fail.
  5. the TEST-ONLY key pair is self-consistent (pub derives from key).

Exit 0 only when every check holds. Run from the repository root or anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "contract-fixtures"
CONSOLE = ROOT / "templates" / "claude" / "console"
KEY = FIXTURES / "keys" / "test-console.key"
PUB = FIXTURES / "keys" / "test-console.pub"

ERRORS: list[str] = []


def err(message: str) -> None:
    ERRORS.append(message)


def find_openssl() -> str | None:
    for candidate in [
        os.environ.get("HARNESS_OPENSSL"),
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/opt/homebrew/bin/openssl",
        "openssl",
    ]:
        if not candidate:
            continue
        try:
            probe = subprocess.run(
                [candidate, "list", "-public-key-algorithms"], capture_output=True, text=True
            )
        except FileNotFoundError:
            continue
        if probe.returncode == 0 and "ED25519" in probe.stdout.upper():
            return candidate
    return None


def canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_manifest() -> dict:
    manifest = load(FIXTURES / "fixtures.json")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if manifest.get("framework_version") != version:
        err(f"manifest framework_version {manifest.get('framework_version')!r} != VERSION {version!r}")
    releases = load(ROOT / "harness" / "framework-releases.json")["releases"]
    if releases[-1]["version"] != version:
        err(f"release manifest tail {releases[-1]['version']!r} != VERSION {version!r}")
    for name, schema_file in (
        ("pending-gate", CONSOLE / "pending-gate.schema.json"),
        ("mode-intent", CONSOLE / "mode-intent.schema.json"),
    ):
        expected = manifest.get("schemas", {}).get(name)
        actual = sha256(schema_file)
        if expected != actual:
            err(f"schema snapshot drift for {name}: manifest {expected!r} != live {actual!r}")
    listed = set(manifest.get("files", []))
    on_disk = {
        str(path.relative_to(FIXTURES))
        for path in FIXTURES.rglob("*.json")
        if path.name != "fixtures.json"
    }
    exempt = set()  # every fixture json must be listed
    missing = listed - on_disk
    unlisted = (on_disk - listed) - exempt
    if missing:
        err(f"manifest lists files that do not exist: {sorted(missing)}")
    if unlisted:
        err(f"fixture files not listed in manifest: {sorted(unlisted)}")
    return manifest


def check_vectors() -> None:
    vectors = load(FIXTURES / "canonical-json" / "vectors.json")["vectors"]
    if not vectors:
        err("canonical-json vectors are empty")
    seen_non_ascii = False
    for vector in vectors:
        name = vector.get("name", "<unnamed>")
        expected = vector.get("expected")
        actual = canonical(vector.get("input", {})).decode("utf-8")
        if actual != expected:
            err(f"canonical vector {name!r} drifted: expected {expected!r}, recomputed {actual!r}")
        if any(ord(ch) > 127 for ch in (expected or "")):
            seen_non_ascii = True
    if not seen_non_ascii:
        err("vectors must include at least one non-ASCII case (ensure_ascii=False is contractual)")


def check_keys(openssl: str) -> None:
    derived = subprocess.run(
        [openssl, "pkey", "-in", str(KEY), "-pubout"], capture_output=True, text=True
    )
    if derived.returncode != 0:
        err(f"cannot derive public key from test key: {derived.stderr.strip()}")
        return
    if derived.stdout.strip() != PUB.read_text(encoding="utf-8").strip():
        err("keys/test-console.pub does not match keys/test-console.key")


def run_pending_gate(openssl: str) -> None:
    with tempfile.TemporaryDirectory(prefix="cf-gate-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        validator = tmp / "validate-pending-gate.sh"
        shutil.copy(CONSOLE / "validate-pending-gate.sh", validator)
        validator.chmod(0o755)
        shutil.copy(PUB, tmp / "console.pub")
        env = {**os.environ, "HARNESS_OPENSSL": openssl}
        for path in sorted((FIXTURES / "pending-gate").rglob("*.json")):
            fixture = load(path)
            rel = str(path.relative_to(FIXTURES))
            if not isinstance(fixture.get("pending_gate"), dict) or fixture.get("expect") not in {"valid", "invalid"}:
                err(f"{rel}: malformed fixture (needs expect + pending_gate)")
                continue
            progress = tmp / "progress.json"
            progress.write_text(
                json.dumps(
                    {"status": "verifying", "pending_gate": fixture["pending_gate"]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            for check in fixture.get("checks", []):
                result = subprocess.run(
                    ["bash", str(validator), check, str(progress)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                passed = result.returncode == 0
                if fixture["expect"] == "valid" and not passed:
                    err(f"{rel}: declared valid but {check} failed: {result.stdout}{result.stderr}")
                if fixture["expect"] == "invalid" and passed:
                    err(f"{rel}: declared invalid but {check} passed")


def run_mode_intent(openssl: str) -> None:
    repo_key = "github.com/contract-fixtures/sample"
    registry = {
        "version": "dispatch/1",
        "agents": [
            {
                "id": "main-claude",
                "roles": ["planner", "generator"],
                "transport": "subagent",
                "agent_type": "generator-restricted",
                "model_family": "claude",
                "constraints": {"l2": False, "write_src": True, "push": True},
            },
            {
                "id": "reviewer-claude",
                "roles": ["evaluator"],
                "transport": "subagent",
                "agent_type": "evaluator",
                "model_family": "claude",
                "constraints": {"l2": False, "write_src": False, "push": False},
            },
        ],
    }
    with tempfile.TemporaryDirectory(prefix="cf-intent-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        repo = tmp / "project"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", f"git@github.com:{repo_key.split('/', 1)[1]}.git"],
            check=True,
        )
        registry_path = repo / ".agents-registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        validator = CONSOLE / "validate-mode-intent.sh"
        for path in sorted((FIXTURES / "mode-intent").rglob("*.json")):
            fixture = load(path)
            rel = str(path.relative_to(FIXTURES))
            if not isinstance(fixture.get("mode_defaults"), dict) or fixture.get("expect") not in {"valid", "invalid"}:
                err(f"{rel}: malformed fixture (needs expect + mode_defaults)")
                continue
            harness = repo / "harness.json"
            harness.write_text(
                json.dumps(
                    {
                        "framework": {},
                        "project": {"name": "contract-fixture", "mode_defaults": fixture["mode_defaults"]},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                ["bash", str(validator), str(harness), str(registry_path), str(PUB)],
                capture_output=True,
                text=True,
                env={**os.environ, "HARNESS_OPENSSL": openssl},
                cwd=repo,
            )
            passed = result.returncode == 0
            if fixture["expect"] == "valid" and not passed:
                err(f"{rel}: declared valid but validator failed: {result.stdout}{result.stderr}")
            if fixture["expect"] == "invalid" and passed:
                err(f"{rel}: declared invalid but validator passed")


def main() -> int:
    openssl = find_openssl()
    if openssl is None:
        print("[contract-fixtures] x no Ed25519-capable OpenSSL (set HARNESS_OPENSSL)", file=sys.stderr)
        return 2
    check_manifest()
    check_vectors()
    check_keys(openssl)
    run_pending_gate(openssl)
    run_mode_intent(openssl)
    if ERRORS:
        print("[contract-fixtures] x validation failed:", file=sys.stderr)
        for message in ERRORS:
            print(f"  - {message}", file=sys.stderr)
        return 2
    print("[contract-fixtures] ok — manifest, vectors, keys, pending-gate, mode-intent all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
