#!/usr/bin/env python3
"""Replay-anchor regression for consume-mode-intent.sh (v1.9.1).

The progress.mode_intent checkpoint is routinely cleared at done cleanup, so
consumption must also leave a durable ledger in harness.json. These tests run
the real consumer end-to-end in a temp git project against the golden signed
fast-profile fixture and prove:

1. successful consumption removes project.mode_defaults and appends the
   consumed intent_id to project.consumed_mode_intents;
2. after the progress anchor is cleared (done cleanup) and the same intent is
   re-staged, the ledger alone rejects the replay;
3. the original progress-anchor guard still rejects replay when the ledger is
   stripped (pre-v1.9.1 files remain protected).
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "contract-fixtures" / "mode-intent" / "valid" / "fast-profile.json"
PUB = ROOT / "contract-fixtures" / "keys" / "test-console.pub"
REMOTE = "https://github.com/contract-fixtures/sample.git"


def git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def make_project(tmp: pathlib.Path) -> pathlib.Path:
    project = tmp / "project"
    project.mkdir()
    git(project, "init", "-q")
    git(project, "remote", "add", "origin", REMOTE)
    for rel in ("templates/claude/console", "templates/claude/dispatch"):
        shutil.copytree(ROOT / rel, project / ".claude" / pathlib.Path(rel).name)
    staged = json.loads(FIXTURE.read_text(encoding="utf-8"))["mode_defaults"]
    (project / "progress.json").write_text(
        json.dumps({"status": "done"}, indent=2) + "\n", encoding="utf-8"
    )
    (project / "harness.json").write_text(
        json.dumps({"project": {"mode_defaults": staged}}, indent=2) + "\n", encoding="utf-8"
    )
    (project / ".agents-registry.json").write_text(
        json.dumps({"schema": "tool-integrations/1", "integrations": []}) + "\n",
        encoding="utf-8",
    )
    return project


def consume(project: pathlib.Path, batch: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(project / ".claude" / "console" / "consume-mode-intent.sh"),
            "--batch",
            batch,
            "--pub",
            str(PUB),
        ],
        cwd=project,
        capture_output=True,
        text=True,
    )


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def restage(project: pathlib.Path) -> None:
    staged = json.loads(FIXTURE.read_text(encoding="utf-8"))["mode_defaults"]
    harness = read_json(project / "harness.json")
    harness["project"]["mode_defaults"] = staged
    (project / "harness.json").write_text(
        json.dumps(harness, indent=2) + "\n", encoding="utf-8"
    )


class ConsumeModeIntentLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="consume-ledger-test-")
        self.project = make_project(pathlib.Path(self.temp.name))
        self.intent_id = json.loads(FIXTURE.read_text(encoding="utf-8"))["mode_defaults"][
            "intent"
        ]["intent_id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def consume_once_ok(self) -> None:
        result = consume(self.project, "TEST-BATCH-1")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_consumption_writes_ledger_and_clears_staged_intent(self) -> None:
        self.consume_once_ok()
        progress = read_json(self.project / "progress.json")
        self.assertEqual(progress["mode_intent"]["intent_id"], self.intent_id)
        harness = read_json(self.project / "harness.json")
        self.assertNotIn("mode_defaults", harness["project"])
        ledger = harness["project"]["consumed_mode_intents"]
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["intent_id"], self.intent_id)
        self.assertEqual(ledger[0]["applied_batch"], "TEST-BATCH-1")

    def test_ledger_rejects_replay_after_progress_anchor_cleared(self) -> None:
        self.consume_once_ok()
        progress = read_json(self.project / "progress.json")
        progress["mode_intent"] = None
        (self.project / "progress.json").write_text(
            json.dumps(progress, indent=2) + "\n", encoding="utf-8"
        )
        restage(self.project)
        replay = consume(self.project, "TEST-BATCH-2")
        self.assertEqual(replay.returncode, 2, msg=replay.stdout)
        self.assertIn("消费台账", replay.stderr)

    def test_progress_anchor_still_rejects_replay_without_ledger(self) -> None:
        self.consume_once_ok()
        harness = read_json(self.project / "harness.json")
        del harness["project"]["consumed_mode_intents"]
        (self.project / "harness.json").write_text(
            json.dumps(harness, indent=2) + "\n", encoding="utf-8"
        )
        restage(self.project)
        replay = consume(self.project, "TEST-BATCH-2")
        self.assertEqual(replay.returncode, 2, msg=replay.stdout)
        self.assertIn("已消费过", replay.stderr)


if __name__ == "__main__":
    unittest.main()
