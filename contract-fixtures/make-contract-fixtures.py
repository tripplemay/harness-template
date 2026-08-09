#!/usr/bin/env python3
"""Regenerate the cross-repo contract fixtures (TEST-ONLY golden material).

The fixtures pin the channel-B contract surface shared by this framework and
any external console implementation (tokenizer is the first): canonical-JSON
byte semantics, the pending-gate decision signature payload, and the signed
mode-intent envelope. Everything here is deterministic given the committed
TEST-ONLY key pair: rerunning this script must produce byte-identical output.

Regeneration: python3 contract-fixtures/make-contract-fixtures.py
Key rotation: delete keys/test-console.key + .pub first, then regenerate.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CONSOLE = ROOT / "templates" / "claude" / "console"
KEY = HERE / "keys" / "test-console.key"
PUB = HERE / "keys" / "test-console.pub"

# Golden fixtures must not depend on the wall clock: absolute timestamps are
# frozen, and validity horizons sit a century out so "valid" fixtures never
# rot into "expired" (time-based rejection stays covered by the dynamic
# console tests, not by this static material).
ISSUED_AT = "2026-08-09T00:00:00Z"
FAR_FUTURE = "2126-01-01T00:00:00Z"


def find_openssl() -> str:
    candidates = [
        os.environ.get("HARNESS_OPENSSL"),
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/opt/homebrew/bin/openssl",
        "openssl",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            probe = subprocess.run(
                [candidate, "list", "-public-key-algorithms"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if probe.returncode == 0 and "ED25519" in probe.stdout.upper():
            return candidate
    raise SystemExit("[make-fixtures] no Ed25519-capable OpenSSL found (set HARNESS_OPENSSL)")


def canonical(payload: dict) -> bytes:
    """The single canonical-JSON contract: recursive key sort, compact
    separators, ensure_ascii=False, UTF-8. Must stay byte-identical to
    templates/claude/console/validate-pending-gate.sh and the Node
    canonicalJson used by console implementations."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def ensure_keys(openssl: str) -> None:
    KEY.parent.mkdir(parents=True, exist_ok=True)
    if KEY.exists() and PUB.exists():
        return
    subprocess.run([openssl, "genpkey", "-algorithm", "Ed25519", "-out", str(KEY)], check=True)
    subprocess.run([openssl, "pkey", "-in", str(KEY), "-pubout", "-out", str(PUB)], check=True)
    KEY.chmod(0o600)


def sign(openssl: str, payload: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        pay = pathlib.Path(tmp) / "payload.bin"
        sig = pathlib.Path(tmp) / "signature.bin"
        pay.write_bytes(payload)
        subprocess.run(
            [openssl, "pkeyutl", "-sign", "-inkey", str(KEY), "-rawin", "-in", str(pay), "-out", str(sig)],
            check=True,
            capture_output=True,
        )
        return base64.b64encode(sig.read_bytes()).decode("ascii")


def signed_decision(openssl: str, decision: dict) -> dict:
    decision = dict(decision)
    decision.pop("sig", None)
    decision["sig"] = sign(openssl, canonical(decision))
    return decision


def signed_intent(openssl: str, intent: dict) -> dict:
    intent = dict(intent)
    intent.pop("sig", None)
    intent["sig"] = sign(openssl, canonical(intent))
    return intent


def write_json(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def corrupt_base64(value: str) -> str:
    raw = bytearray(base64.b64decode(value))
    raw[0] ^= 0x01
    return base64.b64encode(bytes(raw)).decode("ascii")


def build_vectors() -> list[dict]:
    inputs = [
        ("simple-object", {"b": 1, "a": "x"}),
        ("nested-recursive-sort", {"z": {"y": 2, "a": {"c": True, "b": None}}, "a": [3, 2, 1]}),
        ("chinese-unescaped", {"note": "批准发布：第 3 轮", "名称": "契约"}),
        ("emoji-and-escapes", {"s": "line\nbreak \"quoted\" 反斜杠\\ 🔒"}),
        ("empty-containers", {"o": {}, "arr": [], "n": None}),
        (
            "decision-shape",
            {
                "gate_id": "CF-DEMO-verifying-done-w1",
                "action": "approve",
                "by": "console@example.invalid",
                "at": ISSUED_AT,
                "note": "中文备注",
                "scope": {"once": True},
            },
        ),
    ]
    return [
        {"name": name, "input": value, "expected": canonical(value).decode("utf-8")}
        for name, value in inputs
    ]


GATE_ID = "CF-BATCH-verifying-done-w1"


def base_gate() -> dict:
    return {
        "id": GATE_ID,
        "kind": "phase_advance",
        "raised_at": ISSUED_AT,
        "raised_by": "verify",
        "batch": "CF-BATCH",
        "from_status": "verifying",
        "to_status": "done",
        "detail": "契约 fixture：全部 acceptance PASS，等待人类批准跨 Class B 闸门",
        "evidence": ["docs/test-reports/CF-BATCH-verdict.json"],
        "decision": None,
    }


def build_pending_gate(openssl: str) -> dict[str, dict]:
    approve = signed_decision(
        openssl,
        {
            "gate_id": GATE_ID,
            "action": "approve",
            "by": "contract-fixture@example.invalid",
            "at": ISSUED_AT,
            "note": "中文备注：批准（contract fixture）",
            "scope": {"once": True},
        },
    )
    reject = signed_decision(
        openssl,
        {
            "gate_id": GATE_ID,
            "action": "reject",
            "by": "contract-fixture@example.invalid",
            "at": ISSUED_AT,
            "note": "拒绝：证据不足 🔒",
        },
    )
    stale = signed_decision(
        openssl,
        {
            "gate_id": "CF-OTHER-verifying-done-w9",
            "action": "approve",
            "by": "contract-fixture@example.invalid",
            "at": ISSUED_AT,
        },
    )
    extra = signed_decision(
        openssl,
        {
            "gate_id": GATE_ID,
            "action": "approve",
            "by": "contract-fixture@example.invalid",
            "at": ISSUED_AT,
            "auto": True,
        },
    )

    def gate_with(decision: dict | None) -> dict:
        gate = base_gate()
        gate["decision"] = decision
        return gate

    tampered_scope = json.loads(json.dumps(approve, ensure_ascii=False))
    tampered_scope["scope"]["once"] = False  # the historical once→permanent attack

    corrupted = dict(approve)
    corrupted["sig"] = corrupt_base64(approve["sig"])

    unsigned = {k: v for k, v in approve.items() if k != "sig"}

    return {
        "valid/approve-once.json": {
            "name": "approve-once",
            "expect": "valid",
            "checks": ["schema", "guard"],
            "pending_gate": gate_with(approve),
        },
        "valid/reject-no-scope.json": {
            "name": "reject-no-scope",
            "expect": "valid",
            "checks": ["schema", "guard"],
            "pending_gate": gate_with(reject),
        },
        "invalid/tampered-scope.json": {
            "name": "tampered-scope",
            "expect": "invalid",
            "checks": ["guard"],
            "reason": "scope mutated after signing; full-field payload makes the signature fail",
            "pending_gate": gate_with(tampered_scope),
        },
        "invalid/sig-corrupted.json": {
            "name": "sig-corrupted",
            "expect": "invalid",
            "checks": ["guard"],
            "reason": "signature bytes corrupted",
            "pending_gate": gate_with(corrupted),
        },
        "invalid/missing-sig.json": {
            "name": "missing-sig",
            "expect": "invalid",
            "checks": ["guard"],
            "reason": "console.pub configured, unsigned decisions are refused",
            "pending_gate": gate_with(unsigned),
        },
        "invalid/gate-id-mismatch.json": {
            "name": "gate-id-mismatch",
            "expect": "invalid",
            "checks": ["schema"],
            "reason": "decision.gate_id must equal pending_gate.id (stale-approval defense)",
            "pending_gate": gate_with(stale),
        },
        "invalid/extra-field.json": {
            "name": "extra-field",
            "expect": "invalid",
            "checks": ["schema"],
            "reason": "decision carries a field outside the schema whitelist",
            "pending_gate": gate_with(extra),
        },
    }


REPO_KEY = "github.com/contract-fixtures/sample"


def base_intent() -> dict:
    return {
        "intent_id": "cf-intent-0001",
        "repo_key": REPO_KEY,
        "expected_head_sha": "0123456789abcdef0123456789abcdef01234567",
        "desired": {
            "execution": {"profile": "fast", "role_bindings": None},
            "autonomy": {"enabled": False},
        },
        "issued_by": "contract-fixture@example.invalid",
        "issued_at": ISSUED_AT,
        "intent_expires_at": FAR_FUTURE,
    }


def build_mode_intent(openssl: str) -> dict[str, dict]:
    fast = signed_intent(openssl, base_intent())

    tampered = json.loads(json.dumps(fast, ensure_ascii=False))
    tampered["expected_head_sha"] = "f" * 40

    unsigned = {k: v for k, v in fast.items() if k != "sig"}

    extra = dict(base_intent())
    extra["operator_note"] = "not in the whitelist"
    extra = signed_intent(openssl, extra)

    autonomy_extra = dict(base_intent())
    autonomy_extra["desired"] = {
        "execution": {"profile": "fast", "role_bindings": None},
        "autonomy": {"enabled": False, "budget": {"max_wakes": 8}},
    }
    autonomy_extra = signed_intent(openssl, autonomy_extra)

    def staged(intent: dict) -> dict:
        return {"intent": intent, "staged_at": ISSUED_AT}

    return {
        "valid/fast-profile.json": {
            "name": "fast-profile",
            "expect": "valid",
            "reason": None,
            "mode_defaults": staged(fast),
        },
        "invalid/tampered-head.json": {
            "name": "tampered-head",
            "expect": "invalid",
            "reason": "expected_head_sha mutated after signing",
            "mode_defaults": staged(tampered),
        },
        "invalid/missing-sig.json": {
            "name": "missing-sig",
            "expect": "invalid",
            "reason": "intent without sig",
            "mode_defaults": staged(unsigned),
        },
        "invalid/extra-field.json": {
            "name": "extra-field",
            "expect": "invalid",
            "reason": "field outside the signed-intent whitelist",
            "mode_defaults": staged(extra),
        },
        "invalid/autonomy-extra.json": {
            "name": "autonomy-extra",
            "expect": "invalid",
            "reason": "autonomy off must be strictly {\"enabled\": false}",
            "mode_defaults": staged(autonomy_extra),
        },
    }


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    openssl = find_openssl()
    ensure_keys(openssl)

    vectors = build_vectors()
    write_json(HERE / "canonical-json" / "vectors.json", {"vectors": vectors})

    files: list[str] = ["canonical-json/vectors.json"]
    for rel, fixture in build_pending_gate(openssl).items():
        write_json(HERE / "pending-gate" / rel, fixture)
        files.append(f"pending-gate/{rel}")
    for rel, fixture in build_mode_intent(openssl).items():
        write_json(HERE / "mode-intent" / rel, fixture)
        files.append(f"mode-intent/{rel}")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = {
        "schema_version": 1,
        "framework_version": version,
        "generated_by": "contract-fixtures/make-contract-fixtures.py",
        "test_only_keys": "keys/test-console.key must never be used outside fixtures",
        "schemas": {
            "pending-gate": sha256(CONSOLE / "pending-gate.schema.json"),
            "mode-intent": sha256(CONSOLE / "mode-intent.schema.json"),
        },
        "files": sorted(files),
    }
    write_json(HERE / "fixtures.json", manifest)
    print(f"[make-fixtures] ok — {len(files)} fixture files @ framework {version}")


if __name__ == "__main__":
    sys.exit(main())
