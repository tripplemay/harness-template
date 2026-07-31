#!/usr/bin/env python3
"""Validate the v1 framework release contract without modifying the source tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANGELOG_V1_HEADER_RE = re.compile(
    r"^## v(?P<version>1(?!\d)(?:\.[^\s—]*)?)(?P<rest>.*)$", re.MULTILINE
)
CHANGELOG_DATE_RE = re.compile(
    r"^\s+—\s+(?P<released_on>\d{4}-\d{2}-\d{2})(?:\s|$|[（(])"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate framework-releases.json, VERSION, and v1 CHANGELOG headings."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Framework source root (defaults to this script's repository root).",
    )
    return parser.parse_args()


def semver_key(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def valid_date(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"缺少发布清单：{path}")
    except json.JSONDecodeError as exc:
        errors.append(f"发布清单不是合法 JSON：{path} ({exc})")
    return None


def validate_manifest(root: Path, errors: list[str]) -> list[tuple[str, str]]:
    manifest_path = root / "harness" / "framework-releases.json"
    manifest = load_json(manifest_path, errors)
    if not isinstance(manifest, dict):
        if manifest is not None:
            errors.append("发布清单顶层必须是对象")
        return []

    if set(manifest) != {"schema_version", "releases"}:
        errors.append("发布清单顶层只能包含 schema_version 和 releases")
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1:
        errors.append("发布清单 schema_version 必须为整数 1")

    releases = manifest.get("releases")
    if not isinstance(releases, list) or not releases:
        errors.append("发布清单 releases 必须是非空数组")
        return []

    records: list[tuple[str, str]] = []
    seen_versions: set[str] = set()
    previous: tuple[int, int, int] | None = None
    for index, release in enumerate(releases):
        prefix = f"releases[{index}]"
        if not isinstance(release, dict) or set(release) != {"version", "released_on"}:
            errors.append(f"{prefix} 必须只包含 version 和 released_on")
            continue

        version = release.get("version")
        released_on = release.get("released_on")
        valid_version = isinstance(version, str) and SEMVER_RE.fullmatch(version) is not None
        if not valid_version:
            errors.append(f"{prefix}.version 必须是无前导零的三段式 SemVer")
        elif not version.startswith("1."):
            errors.append(f"{prefix}.version 必须属于 v1 正式发布历史：{version}")
        if not valid_date(released_on):
            errors.append(f"{prefix}.released_on 必须是合法 UTC 日期 YYYY-MM-DD")

        if not valid_version or not valid_date(released_on):
            continue

        assert isinstance(version, str)
        assert isinstance(released_on, str)
        key = semver_key(version)
        if version in seen_versions:
            errors.append(f"发布清单存在重复版本：{version}")
        if previous is not None and key <= previous:
            errors.append(f"发布清单版本必须严格递增：{version}")
        seen_versions.add(version)
        previous = key
        records.append((version, released_on))
    return records


def validate_version(root: Path, records: list[tuple[str, str]], errors: list[str]) -> None:
    version_path = root / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        errors.append(f"缺少 VERSION：{version_path}")
        return

    if not records:
        return
    if version != records[-1][0]:
        errors.append(
            f"VERSION={version!r} 必须等于发布清单末项 {records[-1][0]!r}"
        )


def validate_changelog(root: Path, records: list[tuple[str, str]], errors: list[str]) -> None:
    changelog_path = root / "CHANGELOG.md"
    try:
        changelog = changelog_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"缺少 CHANGELOG：{changelog_path}")
        return

    headings: list[tuple[str, str]] = []
    seen_versions: set[str] = set()
    for match in CHANGELOG_V1_HEADER_RE.finditer(changelog):
        version = match.group("version")
        date_match = CHANGELOG_DATE_RE.match(match.group("rest"))
        if SEMVER_RE.fullmatch(version) is None:
            errors.append(f"CHANGELOG v1 标题不是三段式 SemVer：v{version}")
            continue
        if date_match is None or not valid_date(date_match.group("released_on")):
            errors.append(f"CHANGELOG v1 标题缺少合法发布日期：v{version}")
            continue
        released_on = date_match.group("released_on")
        if version in seen_versions:
            errors.append(f"CHANGELOG 存在重复 v1 标题：v{version}")
        seen_versions.add(version)
        headings.append((version, released_on))

    manifest_pairs = set(records)
    changelog_pairs = set(headings)
    for version, released_on in sorted(manifest_pairs - changelog_pairs, key=lambda item: semver_key(item[0])):
        errors.append(f"CHANGELOG 缺少清单发布：v{version} — {released_on}")
    for version, released_on in sorted(changelog_pairs - manifest_pairs, key=lambda item: semver_key(item[0])):
        errors.append(f"发布清单缺少 CHANGELOG 发布：v{version} — {released_on}")


def main() -> int:
    root = parse_args().root.resolve()
    errors: list[str] = []
    records = validate_manifest(root, errors)
    validate_version(root, records, errors)
    validate_changelog(root, records, errors)
    if errors:
        print("[release-contract] x 发布契约校验失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    print("[release-contract] ok manifest、VERSION 与 CHANGELOG v1 发布记录一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
