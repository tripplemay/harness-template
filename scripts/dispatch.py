#!/usr/bin/env python3
"""
Harness v1.0 Phase 1 dispatcher — single-machine, no Redis.

Usage:
    dispatch.py render <role> <id> [--round N]
        Render template to stdout (no subprocess spawn).

    dispatch.py run generator <feature_id>
    dispatch.py run evaluator <batch_id> [--round N]
        Render template + spawn subprocess. Prints result file path to stdout.

    dispatch.py parse <result_file>
        Extract last-line JSON from subprocess output, pretty-print.

Env vars:
    HARNESS_PROJECT_ROOT  Project path (default: cwd)
    HARNESS_TMP_DIR       Result files location (default: /tmp/harness)
    HARNESS_AGENT_ID      Override agent id (default: <role>-<hostname>-1)

Phase 1 limitations:
    - Single machine only (no Redis queue, no remote workers)
    - Serial dispatch (one subprocess at a time)
    - No heartbeat / lock / retry (handled by Orchestrator's error loop)
    - No budget tracking

These are implemented in Phase 2-5 per docs/v1.0-orchestration-plan.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HARNESS_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = HARNESS_ROOT / "templates" / "agent-invocations"
TMP_DIR = Path(os.environ.get("HARNESS_TMP_DIR", "/tmp/harness"))

TEMPLATE_BODY_RE = re.compile(
    r"## 模板正文.*?```[^\n]*\n(.*?)\n```",
    re.DOTALL,
)
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def die(msg: str, code: int = 2) -> None:
    print(f"dispatch.py: {msg}", file=sys.stderr)
    sys.exit(code)


def project_root() -> Path:
    return Path(os.environ.get("HARNESS_PROJECT_ROOT", Path.cwd()))


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"required file missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"invalid JSON in {path}: {e}")


def extract_template(md_path: Path) -> str:
    if not md_path.exists():
        die(f"template not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    m = TEMPLATE_BODY_RE.search(text)
    if not m:
        die(f"cannot locate '## 模板正文' fenced block in {md_path}")
    return m.group(1)


def render_template(template: str, variables: dict) -> str:
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        key = m.group(1).strip()
        if key not in variables:
            missing.append(key)
            return f"{{{{{key}}}}}"
        return str(variables[key])

    result = VAR_RE.sub(sub, template)
    if missing:
        die(f"template variables not provided: {', '.join(sorted(set(missing)))}")
    return result


def default_agent_id(role: str) -> str:
    explicit = os.environ.get("HARNESS_AGENT_ID")
    if explicit:
        return explicit
    host = socket.gethostname().split(".")[0] or "unknown"
    return f"{role[:3]}-{host}-1"


def build_variables(role: str, target_id: str, round_num: int = 1) -> dict:
    proj = project_root()
    progress = load_json(proj / "progress.json")
    features = load_json(proj / "features.json")
    feature_list = features.get("features", [])

    batch_id = progress.get("batch_id", "unknown")
    orchestrator = progress.get("orchestration", {}).get("orchestrator_agent", "orchestrator")
    spec_path = (progress.get("docs") or {}).get("spec") or f"docs/specs/{batch_id}-spec.md"

    variables = {
        "project_path": str(proj),
        "batch_id": batch_id,
        "orchestrator_agent": orchestrator,
        "agent_id": default_agent_id(role),
        "spec_path": spec_path,
    }

    if role == "generator":
        feature = next((f for f in feature_list if f.get("id") == target_id), None)
        if feature is None:
            die(f"feature {target_id} not found in features.json")
        variables["feature_id"] = target_id
        variables["touches"] = json.dumps(feature.get("touches", []), ensure_ascii=False)
    elif role == "evaluator":
        variables["batch_id"] = target_id  # allow override
        variables["features_to_verify"] = json.dumps(
            [f["id"] for f in feature_list], ensure_ascii=False
        )
        variables["round"] = str(round_num)
        prev = round_num - 1
        variables["previous_report_path"] = (
            f"docs/test-reports/{target_id}-round-{prev}.md" if prev >= 1 else "null"
        )
    else:
        die(f"unknown role: {role}")

    return variables


def cmd_render(args: argparse.Namespace) -> int:
    template = extract_template(TEMPLATES_DIR / f"{args.role}-prompt.md")
    variables = build_variables(args.role, args.id, args.round)
    sys.stdout.write(render_template(template, variables))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    template = extract_template(TEMPLATES_DIR / f"{args.role}-prompt.md")
    variables = build_variables(args.role, args.id, args.round)
    rendered = render_template(template, variables)

    # Tool isolation —守护"Generator ≠ Evaluator"铁律
    if args.role == "generator":
        cmd = ["claude", "-p", rendered, "--output-format", "json"]
    elif args.role == "evaluator":
        cmd = ["codex", "exec", "--cd", variables["project_path"], rendered]
    else:
        die(f"unknown role: {args.role}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TMP_DIR / f"{args.role}-{args.id}-round{args.round}.log"

    print(f"[dispatch] role={args.role} id={args.id} → {out_path}", file=sys.stderr)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=sys.stderr, check=False)
    except FileNotFoundError as e:
        die(f"tool not on PATH: {e.filename} (required for role={args.role})")

    print(f"[dispatch] exit={result.returncode}", file=sys.stderr)
    # Stdout = result file path (Orchestrator can pipe to parse)
    print(out_path)
    return result.returncode


def cmd_parse(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        die(f"result file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        die(f"result file is empty: {path}")

    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0

    die(f"no valid JSON object found in last lines of {path}", code=1)
    return 1  # unreachable


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dispatch.py",
        description="Harness v1.0 Phase 1 dispatcher (single-machine)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("render", help="Render template, print to stdout")
    pr.add_argument("role", choices=["generator", "evaluator"])
    pr.add_argument("id", help="feature_id (generator) or batch_id (evaluator)")
    pr.add_argument("--round", type=int, default=1)
    pr.set_defaults(func=cmd_render)

    rn = sub.add_parser("run", help="Render template + spawn subprocess")
    rn.add_argument("role", choices=["generator", "evaluator"])
    rn.add_argument("id")
    rn.add_argument("--round", type=int, default=1)
    rn.set_defaults(func=cmd_run)

    ps = sub.add_parser("parse", help="Extract last-line JSON from result file")
    ps.add_argument("path", help="Path to result log file")
    ps.set_defaults(func=cmd_parse)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
