#!/usr/bin/env python3
"""Run the source-only vm-v1 Kimi Generator probe.

This narrow evaluator-controlled L2 utility is not an orchestration
entrypoint. It admits live L2 work only after an
``out-of-band-manual-confirmation``: the exact CLI flag records that prior
evaluator decision locally. It never reads project state or consumes a
project approval decision. The provider and Kimi bridge manifest come only
from this framework source tree, and its only workload is one fixed synthetic
Generator child task. Launch it only with an absolute trusted Python in
isolated mode: ``/usr/bin/python3 -I scripts/run-vm-kimi-l2-probe.py
--confirm-live-kimi-l2``.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pwd
import re
import secrets
import stat
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


PROBE_VERSION = "harness/vm-kimi-l2-probe/1"
PROBE_BINDING_VERSION = "harness/vm-kimi-l2-probe-binding/1"
CONFIRMATION_FLAG = "--confirm-live-kimi-l2"
OUT_OF_BAND_MANUAL_CONFIRMATION = "out-of-band-manual-confirmation"
ISOLATED_RUNTIME_LAUNCH_REQUIREMENT = "/usr/bin/python3 -I"
PROBE_TIMEOUT_SECONDS = 180
VENDOR_DROP_PREFLIGHT_TIMEOUT_SECONDS = 30
MAX_PROBE_ARTIFACT_BYTES = 4 * 1024
MAX_SOURCE_BRIDGE_MANIFEST_BYTES = 64 * 1024
MAX_SOURCE_PROVIDER_BYTES = 4 * 1024 * 1024
MAX_SOURCE_RUNNER_BYTES = 2 * 1024 * 1024
SOURCE_TRANSPORTS_RELATIVE = Path("templates/claude/dispatch/transports")
SOURCE_PROVIDER_RELATIVE = SOURCE_TRANSPORTS_RELATIVE / "vm-bridge-provider.py"
SOURCE_BRIDGE_RELATIVE = (
    SOURCE_TRANSPORTS_RELATIVE / "bridges/kimi-acp-native-agent.json"
)
SOURCE_RUNNER_NAMES = (
    "session-bridge.py",
    "session_bridge_kimi.py",
    "vm-bridge-worker.py",
)
SOURCE_STAGE_METADATA = ".harness-vm-kimi-l2-source.json"
SOURCE_STAGE_SESSION_ATTR = "_harness_vm_kimi_l2_source_session"
ARTIFACT_PATH = "docs/test-reports/generator-handoff-vm-kimi-l2.json"
EXPECTED_ARTIFACT = {"probe": "harness-vm-kimi-l2", "result": "completed"}
FIXED_SOURCE_FILES = {
    "README.md": b"# Isolated Harness vm-v1 Kimi L2 probe\n",
}
EXPECTED_BRIDGE_PROTOCOL = {
    "kind": "acp-native-agent/v1",
    "command": ["kimi", "acp"],
    "request_delivery": "stdin",
    "response_format": "json",
}
VENDOR_DROP_PREFLIGHT_SENTINEL = b"harnessvm-drop-preflight-ok\n"
VENDOR_DROP_PREFLIGHT_PROGRAM = (
    "/usr/bin/setpriv",
    "--reuid=harnessvm",
    "--regid=harnessvm",
    "--clear-groups",
    "--inh-caps=-all",
    "--ambient-caps=-all",
    "--no-new-privs",
    "--",
    "/usr/bin/python3",
    "-I",
    "-c",
    "import os,pwd\n"
    "from pathlib import Path\n"
    "entry=pwd.getpwnam('harnessvm')\n"
    "if os.getresuid() != (entry.pw_uid,entry.pw_uid,entry.pw_uid): raise SystemExit(2)\n"
    "if os.getresgid() != (entry.pw_gid,entry.pw_gid,entry.pw_gid): raise SystemExit(2)\n"
    "if os.getgroups(): raise SystemExit(2)\n"
    "status={}\n"
    "for line in Path('/proc/self/status').read_text(encoding='ascii').splitlines():\n"
    "    key,separator,value=line.partition(':')\n"
    "    if separator: status[key]=value.strip()\n"
    "if any(status.get(key) != '0000000000000000' for key in ('CapInh','CapPrm','CapEff','CapAmb')): raise SystemExit(2)\n"
    "if status.get('NoNewPrivs') != '1': raise SystemExit(2)\n"
    "print('harnessvm-drop-preflight-ok')\n",
)
SOURCE_BRIDGE_FIELDS = {
    "_comment",
    "id",
    "_verified",
    "session_scope",
    "strategy",
    "protocol",
    "personas",
    "native_agent_types",
    "notes",
}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
NONCE_HEX = re.compile(r"^[0-9a-f]{32}$")


class ProbeError(ValueError):
    """The controlled probe cannot establish its required evidence."""


def _has_isolated_runtime() -> bool:
    """Require the interpreter posture that excludes common import injection."""
    flags = sys.flags
    if (
        getattr(flags, "isolated", 0) != 1
        or getattr(flags, "ignore_environment", 0) != 1
        or getattr(flags, "no_user_site", 0) != 1
    ):
        return False
    safe_path = getattr(flags, "safe_path", None)
    if safe_path is not None and safe_path != 1:
        return False
    executable = getattr(sys, "executable", None)
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        return False
    if any(entry in {"", "."} for entry in sys.path):
        return False
    return "sitecustomize" not in sys.modules and "usercustomize" not in sys.modules


@dataclass(frozen=True)
class SourceBridgeManifest:
    bridge_id: str
    strategy: str
    protocol_kind: str
    protocol_command: tuple[str, ...]
    request_delivery: str
    response_format: str
    generator_persona: str
    generator_native_agent_type: str
    sha256: str

    def protocol(self) -> dict[str, Any]:
        return {
            "kind": self.protocol_kind,
            "command": list(self.protocol_command),
            "request_delivery": self.request_delivery,
            "response_format": self.response_format,
        }


@dataclass(frozen=True)
class _ArchiveEntry:
    name: str
    label: str
    size: int
    contents: bytes | None = None
    source: Path | None = None
    source_device: int | None = None
    source_inode: int | None = None


@dataclass(frozen=True)
class _ProbeBinding:
    nonce: str
    sha256: str
    bridge_manifest_sha256: str
    provider_source_sha256: str


@dataclass(frozen=True)
class _PinnedSourceBundle:
    provider_source: bytes
    provider_sha256: str
    runner_sources: Mapping[str, bytes]
    runner_sha256: Mapping[str, str]
    bridge: SourceBridgeManifest


@dataclass
class _SourceProviderSession:
    module: ModuleType
    stage_directory: Path
    stage_fd: int
    stage_parent_fd: int
    stage_name: str
    bridge: SourceBridgeManifest
    provider_sha256: str
    runner_sha256: Mapping[str, str]
    module_name: str
    previous_module: ModuleType | None
    closed: bool = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if sys.modules.get(self.module_name) is self.module:
            if self.previous_module is None:
                sys.modules.pop(self.module_name, None)
            else:
                sys.modules[self.module_name] = self.previous_module
        _cleanup_private_source_stage(
            self.stage_fd, self.stage_parent_fd, self.stage_name
        )


class _CappedWriter:
    """Bound the compressed archive while tarfile streams into a private fd."""

    def __init__(self, stream: Any, maximum_bytes: int) -> None:
        self._stream = stream
        self._maximum_bytes = maximum_bytes
        self.written = 0

    def write(self, block: bytes) -> int:
        if self.written + len(block) > self._maximum_bytes:
            raise ProbeError("fixed probe archive exceeds its compressed size limit")
        written = self._stream.write(block)
        if written is not None and written != len(block):
            raise OSError("fixed probe archive write made no progress")
        self.written += len(block)
        return len(block)

    def flush(self) -> None:
        self._stream.flush()


def _required_no_follow_flag(label: str) -> int:
    value = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(value, int) or value == 0:
        raise ProbeError(f"{label} cannot be opened securely")
    return value


def _required_directory_flag(label: str) -> int:
    value = getattr(os, "O_DIRECTORY", None)
    if not isinstance(value, int) or value == 0:
        raise ProbeError(f"{label} cannot be opened securely")
    return value


def _source_open_flags(label: str, *, directory: bool) -> int:
    flags = os.O_RDONLY | _required_no_follow_flag(label)
    if directory:
        flags |= _required_directory_flag(label)
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    if isinstance(close_on_exec, int) and close_on_exec != 0:
        flags |= close_on_exec
    return flags


def _open_source_directory_at(
    component: str, label: str, *, parent_fd: int | None
) -> int:
    """Open one trusted directory without resolving it again by pathname."""
    try:
        if parent_fd is None:
            descriptor = os.open(component, _source_open_flags(label, directory=True))
        else:
            descriptor = os.open(
                component, _source_open_flags(label, directory=True), dir_fd=parent_fd
            )
    except (OSError, TypeError, NotImplementedError) as exc:
        raise ProbeError(f"{label} is unavailable") from exc
    try:
        entry = os.fstat(descriptor)
    except OSError as exc:
        os.close(descriptor)
        raise ProbeError(f"{label} is unavailable") from exc
    if not stat.S_ISDIR(entry.st_mode):
        os.close(descriptor)
        raise ProbeError(f"{label} is not a directory")
    return descriptor


def _absolute_source_path(path: Path | str, label: str) -> Path:
    """Normalize lexically; secure traversal happens only through dirfds."""
    absolute = Path(os.path.abspath(path))
    if not absolute.is_absolute() or absolute.anchor != os.sep:
        raise ProbeError(f"{label} path is invalid")
    return absolute


def _open_absolute_source_directory(path: Path, label: str) -> int:
    """Walk an absolute directory one no-follow descriptor at a time."""
    absolute = _absolute_source_path(path, label)
    descriptor = _open_source_directory_at(absolute.anchor, label, parent_fd=None)
    try:
        for component in absolute.parts[1:]:
            child = _open_source_directory_at(component, label, parent_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _source_root() -> Path:
    """Return the lexical checkout root; its fd is established separately."""
    script = _absolute_source_path(Path(__file__), "probe source")
    if script.name != "run-vm-kimi-l2-probe.py" or script.parent.name != "scripts":
        raise ProbeError("probe source layout is invalid")
    return script.parent.parent


def _source_relative_parts(path: Path | str, root: Path, label: str) -> tuple[str, ...]:
    root_path = _absolute_source_path(root, "probe source root")
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            relative = _absolute_source_path(candidate, label).relative_to(root_path)
        except ValueError as exc:
            raise ProbeError(f"{label} is outside the source root") from exc
    else:
        relative = candidate
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ProbeError(f"{label} path is invalid")
    return tuple(relative.parts)


def _open_source_regular_file_at(
    root_fd: int, parts: tuple[str, ...], label: str
) -> int:
    """Open a source file below an already anchored source-root descriptor."""
    if not parts:
        raise ProbeError(f"{label} path is invalid")
    parent_fd = root_fd
    owned_parent_fd: int | None = None
    try:
        for component in parts[:-1]:
            child = _open_source_directory_at(component, label, parent_fd=parent_fd)
            if owned_parent_fd is not None:
                os.close(owned_parent_fd)
            owned_parent_fd = child
            parent_fd = child
        try:
            descriptor = os.open(
                parts[-1], _source_open_flags(label, directory=False), dir_fd=parent_fd
            )
        except (OSError, TypeError, NotImplementedError) as exc:
            raise ProbeError(f"{label} is unavailable") from exc
        try:
            entry = os.fstat(descriptor)
        except OSError as exc:
            os.close(descriptor)
            raise ProbeError(f"{label} is unavailable") from exc
        if not stat.S_ISREG(entry.st_mode):
            os.close(descriptor)
            raise ProbeError(f"{label} is not a regular file")
        return descriptor
    finally:
        if owned_parent_fd is not None:
            os.close(owned_parent_fd)


def _open_source_root(root: Path | None = None) -> int:
    """Anchor the checkout and verify the probe file through that same fd."""
    source_root = (
        _source_root()
        if root is None
        else _absolute_source_path(root, "probe source root")
    )
    descriptor = _open_absolute_source_directory(source_root, "probe source root")
    try:
        script_fd = _open_source_regular_file_at(
            descriptor, ("scripts", "run-vm-kimi-l2-probe.py"), "probe source"
        )
    except Exception:
        os.close(descriptor)
        raise
    os.close(script_fd)
    return descriptor


def _source_file(relative: str, label: str) -> Path:
    root = _source_root()
    return root.joinpath(*_source_relative_parts(relative, root, label))


def _source_file_metadata(entry: Any) -> tuple[Any, ...]:
    return (
        entry.st_dev,
        entry.st_ino,
        entry.st_size,
        entry.st_nlink,
        getattr(entry, "st_mtime_ns", None),
        getattr(entry, "st_ctime_ns", None),
    )


def _read_source_regular_file_at(
    root_fd: int,
    parts: tuple[str, ...],
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, str]:
    """Read bounded bytes from a file below an already anchored source root."""
    if not isinstance(maximum_bytes, int) or maximum_bytes < 1:
        raise ProbeError(f"{label} size limit is invalid")
    descriptor: int | None = None
    try:
        descriptor = _open_source_regular_file_at(root_fd, parts, label)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > maximum_bytes:
            raise ProbeError(f"{label} is invalid")
        blocks: list[bytes] = []
        total = 0
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, min(64 * 1024, maximum_bytes - total + 1))
            if not block:
                break
            total += len(block)
            if total > maximum_bytes:
                raise ProbeError(f"{label} exceeds its size limit")
            digest.update(block)
            blocks.append(block)
        final = os.fstat(descriptor)
        if _source_file_metadata(final) != _source_file_metadata(opened):
            raise ProbeError(f"{label} changed while it was being read")
        return b"".join(blocks), digest.hexdigest()
    except OSError as exc:
        raise ProbeError(f"{label} is unavailable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_source_regular_file(
    path: Path | str, label: str, maximum_bytes: int
) -> tuple[bytes, str]:
    """Read bounded source bytes through a source-root-anchored no-follow fd."""
    root = _source_root()
    parts = _source_relative_parts(path, root, label)
    root_fd = _open_source_root(root)
    try:
        return _read_source_regular_file_at(root_fd, parts, label, maximum_bytes)
    finally:
        os.close(root_fd)


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _validated_source_bridge_manifest(
    value: Any, manifest_sha256: str
) -> SourceBridgeManifest:
    """Accept only the published source Kimi same-session bridge semantics."""
    if not isinstance(value, dict) or set(value) != SOURCE_BRIDGE_FIELDS:
        raise ProbeError("source bridge manifest shape is invalid")
    if not isinstance(manifest_sha256, str) or SHA256_HEX.fullmatch(manifest_sha256) is None:
        raise ProbeError("source bridge manifest digest is invalid")
    if (
        value.get("id") != "kimi-acp-native-agent"
        or value.get("_verified") is not True
        or value.get("session_scope") != "same-session"
        or value.get("strategy") != "session-bridge-v1"
    ):
        raise ProbeError("source bridge manifest is not the verified Kimi same-session bridge")
    protocol = value.get("protocol")
    if protocol != EXPECTED_BRIDGE_PROTOCOL:
        raise ProbeError("source bridge manifest protocol is not fixed Kimi ACP")
    personas = value.get("personas")
    native_agent_types = value.get("native_agent_types")
    if (
        not isinstance(personas, dict)
        or set(personas) != {"planner", "generator", "evaluator"}
        or personas.get("generator") != "generator-restricted"
        or not isinstance(native_agent_types, dict)
        or set(native_agent_types) != {"planner", "generator", "evaluator"}
        or native_agent_types.get("generator") != "coder"
    ):
        raise ProbeError("source bridge manifest Generator route is invalid")
    return SourceBridgeManifest(
        bridge_id="kimi-acp-native-agent",
        strategy="session-bridge-v1",
        protocol_kind="acp-native-agent/v1",
        protocol_command=("kimi", "acp"),
        request_delivery="stdin",
        response_format="json",
        generator_persona="generator-restricted",
        generator_native_agent_type="coder",
        sha256=manifest_sha256,
    )


def _source_bridge_manifest_from_bytes(raw: bytes, digest: str) -> SourceBridgeManifest:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProbeError("source Kimi bridge manifest is unreadable") from exc
    return _validated_source_bridge_manifest(value, digest)


def load_source_kimi_bridge_manifest() -> SourceBridgeManifest:
    """Securely load the framework-source manifest used by this narrow probe."""
    path = _source_file(SOURCE_BRIDGE_RELATIVE, "source Kimi bridge manifest")
    raw, digest = _read_source_regular_file(
        path, "source Kimi bridge manifest", MAX_SOURCE_BRIDGE_MANIFEST_BYTES
    )
    return _source_bridge_manifest_from_bytes(raw, digest)


def _source_provider_path() -> Path:
    return _source_file(SOURCE_PROVIDER_RELATIVE, "source provider")


def _read_pinned_source_bundle() -> _PinnedSourceBundle:
    """Read every executable source asset while one source-root fd remains held."""
    root = _source_root()
    provider_parts = _source_relative_parts(SOURCE_PROVIDER_RELATIVE, root, "source provider")
    bridge_parts = _source_relative_parts(
        SOURCE_BRIDGE_RELATIVE, root, "source Kimi bridge manifest"
    )
    runner_parts = {
        name: _source_relative_parts(
            SOURCE_TRANSPORTS_RELATIVE / name, root, f"source runner {name}"
        )
        for name in SOURCE_RUNNER_NAMES
    }
    root_fd = _open_source_root(root)
    try:
        provider_source, provider_sha256 = _read_source_regular_file_at(
            root_fd, provider_parts, "source provider", MAX_SOURCE_PROVIDER_BYTES
        )
        runner_sources: dict[str, bytes] = {}
        runner_sha256: dict[str, str] = {}
        for name in SOURCE_RUNNER_NAMES:
            source, digest = _read_source_regular_file_at(
                root_fd,
                runner_parts[name],
                f"source runner {name}",
                MAX_SOURCE_RUNNER_BYTES,
            )
            runner_sources[name] = source
            runner_sha256[name] = digest
        bridge_source, bridge_sha256 = _read_source_regular_file_at(
            root_fd,
            bridge_parts,
            "source Kimi bridge manifest",
            MAX_SOURCE_BRIDGE_MANIFEST_BYTES,
        )
    finally:
        os.close(root_fd)
    return _PinnedSourceBundle(
        provider_source=provider_source,
        provider_sha256=provider_sha256,
        runner_sources=runner_sources,
        runner_sha256=runner_sha256,
        bridge=_source_bridge_manifest_from_bytes(bridge_source, bridge_sha256),
    )


def _require_private_stage_directory(
    descriptor: int, label: str, *, exact_mode: bool
) -> None:
    try:
        entry = os.fstat(descriptor)
    except OSError as exc:
        raise ProbeError(f"{label} is unavailable") from exc
    mode = stat.S_IMODE(entry.st_mode)
    if (
        not stat.S_ISDIR(entry.st_mode)
        or entry.st_uid != os.geteuid()
        or (mode != 0o700 if exact_mode else mode & 0o022)
    ):
        raise ProbeError(f"{label} is not private")


def _provider_account_home() -> Path:
    try:
        home = pwd.getpwuid(os.geteuid()).pw_dir
    except (KeyError, OSError) as exc:
        raise ProbeError("provider account home is unavailable") from exc
    return _absolute_source_path(Path(home), "provider account home")


def _open_or_create_private_stage_directory_at(
    parent_fd: int, name: str, label: str, *, exact_mode: bool
) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except (OSError, TypeError, NotImplementedError) as exc:
        raise ProbeError(f"{label} is unavailable") from exc
    descriptor = _open_source_directory_at(name, label, parent_fd=parent_fd)
    try:
        _require_private_stage_directory(descriptor, label, exact_mode=exact_mode)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_private_source_stage_parent() -> tuple[int, Path]:
    """Open the fixed provider-owned source-stage parent without TMPDIR."""
    home = _provider_account_home()
    descriptor = _open_absolute_source_directory(home, "provider account home")
    try:
        _require_private_stage_directory(
            descriptor, "provider account home", exact_mode=False
        )
        path = home
        for index, name in enumerate(
            (".tokenizer", "harness", "vm-v1", "runs", "source-stages")
        ):
            child = _open_or_create_private_stage_directory_at(
                descriptor,
                name,
                "pinned source stage parent",
                # The provider has the same boundary: its top-level namespace
                # may be readable, but it must never be writable by another UID.
                exact_mode=index >= 1,
            )
            os.close(descriptor)
            descriptor = child
            path = path / name
        return descriptor, path
    except Exception:
        os.close(descriptor)
        raise


def _create_private_source_stage() -> tuple[int, int, str, Path]:
    parent_fd, parent = _open_private_source_stage_parent()
    name = f"source-{secrets.token_hex(16)}"
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        stage_fd = _open_source_directory_at(name, "pinned source stage", parent_fd=parent_fd)
        try:
            _require_private_stage_directory(stage_fd, "pinned source stage", exact_mode=True)
        except Exception:
            os.close(stage_fd)
            raise
        return parent_fd, stage_fd, name, parent / name
    except (OSError, TypeError, NotImplementedError) as exc:
        os.close(parent_fd)
        raise ProbeError("pinned source stage cannot be created") from exc
    except Exception:
        os.close(parent_fd)
        raise


def _cleanup_private_source_stage(stage_fd: int, parent_fd: int, name: str) -> None:
    for entry_name in (
        SOURCE_PROVIDER_RELATIVE.name,
        *SOURCE_RUNNER_NAMES,
        SOURCE_STAGE_METADATA,
    ):
        try:
            os.unlink(entry_name, dir_fd=stage_fd)
        except OSError:
            pass
    try:
        os.close(stage_fd)
    except OSError:
        pass
    try:
        os.rmdir(name, dir_fd=parent_fd)
    except OSError:
        pass
    try:
        os.close(parent_fd)
    except OSError:
        pass


def _write_private_source_stage_file(
    stage_fd: int, name: str, contents: bytes, expected_sha256: str
) -> None:
    if (
        not isinstance(name, str)
        or not name
        or "/" in name
        or "\\" in name
        or name in {".", ".."}
        or not isinstance(contents, bytes)
        or SHA256_HEX.fullmatch(expected_sha256) is None
    ):
        raise ProbeError("pinned source stage entry is invalid")
    descriptor: int | None = None
    succeeded = False
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | _required_no_follow_flag("pinned source stage"),
            0o600,
            dir_fd=stage_fd,
        )
        os.fchmod(descriptor, 0o600)
        digest = hashlib.sha256()
        view = memoryview(contents)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("pinned source stage write made no progress")
            digest.update(view[:written])
            view = view[written:]
        os.fsync(descriptor)
        entry = os.fstat(descriptor)
        if (
            not stat.S_ISREG(entry.st_mode)
            or stat.S_IMODE(entry.st_mode) != 0o600
            or entry.st_nlink != 1
            or entry.st_size != len(contents)
            or digest.hexdigest() != expected_sha256
        ):
            raise ProbeError("pinned source stage entry drifted")
        succeeded = True
    except OSError as exc:
        raise ProbeError("pinned source stage cannot be written") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if not succeeded:
            try:
                os.unlink(name, dir_fd=stage_fd)
            except OSError:
                pass


def _stage_pinned_source_bundle(
    bundle: _PinnedSourceBundle,
) -> tuple[int, int, str, Path]:
    """Write fixed source bytes once into an owned 0700 runtime stage."""
    if set(bundle.runner_sources) != set(SOURCE_RUNNER_NAMES) or set(bundle.runner_sha256) != set(
        SOURCE_RUNNER_NAMES
    ):
        raise ProbeError("pinned source runner set is invalid")
    parent_fd, stage_fd, stage_name, stage = _create_private_source_stage()
    try:
        _write_private_source_stage_file(
            stage_fd,
            SOURCE_PROVIDER_RELATIVE.name,
            bundle.provider_source,
            bundle.provider_sha256,
        )
        for name in SOURCE_RUNNER_NAMES:
            _write_private_source_stage_file(
                stage_fd, name, bundle.runner_sources[name], bundle.runner_sha256[name]
            )
        metadata = {
            "version": "harness/vm-kimi-l2-source-stage/1",
            "provider_sha256": bundle.provider_sha256,
            "runner_sha256": dict(bundle.runner_sha256),
            "bridge_manifest_sha256": bundle.bridge.sha256,
        }
        metadata_bytes = json.dumps(
            metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        _write_private_source_stage_file(
            stage_fd,
            SOURCE_STAGE_METADATA,
            metadata_bytes,
            hashlib.sha256(metadata_bytes).hexdigest(),
        )
        return parent_fd, stage_fd, stage_name, stage
    except Exception:
        _cleanup_private_source_stage(stage_fd, parent_fd, stage_name)
        raise


def _load_source_provider_session() -> _SourceProviderSession:
    """Stage pinned provider/runner bytes before executing any provider code."""
    bundle = _read_pinned_source_bundle()
    stage_parent_fd, stage_fd, stage_name, stage = _stage_pinned_source_bundle(bundle)
    staged_provider = stage / SOURCE_PROVIDER_RELATIVE.name
    try:
        code = compile(bundle.provider_source, str(staged_provider), "exec", dont_inherit=True)
    except (SyntaxError, TypeError, ValueError) as exc:
        _cleanup_private_source_stage(stage_fd, stage_parent_fd, stage_name)
        raise ProbeError("source provider cannot be compiled") from exc
    name = "_harness_vm_kimi_l2_source_provider"
    module = ModuleType(name, "source-only vm-v1 Kimi L2 probe provider")
    module.__file__ = str(staged_provider)
    module.__package__ = ""
    module.__loader__ = None
    module.__spec__ = None
    module.__cached__ = None
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(code, module.__dict__, module.__dict__)
        if getattr(module, "RUNNER_NAMES", None) != SOURCE_RUNNER_NAMES:
            raise ProbeError("source provider runner set drifted")
    except Exception as exc:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        _cleanup_private_source_stage(stage_fd, stage_parent_fd, stage_name)
        if isinstance(exc, ProbeError):
            raise
        raise ProbeError("source provider cannot be loaded") from exc
    session = _SourceProviderSession(
        module=module,
        stage_directory=stage,
        stage_fd=stage_fd,
        stage_parent_fd=stage_parent_fd,
        stage_name=stage_name,
        bridge=bundle.bridge,
        provider_sha256=bundle.provider_sha256,
        runner_sha256=dict(bundle.runner_sha256),
        module_name=name,
        previous_module=previous,
    )
    module.__dict__[SOURCE_STAGE_SESSION_ATTR] = session
    return session


def _source_provider_session(provider: ModuleType) -> _SourceProviderSession | None:
    session = getattr(provider, SOURCE_STAGE_SESSION_ATTR, None)
    return session if isinstance(session, _SourceProviderSession) else None


def load_source_provider() -> ModuleType:
    """Load only pinned source bytes into a fresh staged module namespace."""
    return _load_source_provider_session().module


def _fixed_envelope(*, confirmed: bool) -> dict[str, Any]:
    """Return the only task data that can reach the external model."""
    if confirmed is not True:
        raise ProbeError("fixed probe requires out-of-band manual confirmation")
    return {
        "task_id": "vm-kimi-l2-generator",
        "contract_version": "harness/1.1",
        "batch": "VM-KIMI-L2",
        "role": "generator",
        "repo": {
            "url": "synthetic://harness/vm-kimi-l2",
            "ref": "0" * 40,
        },
        "spec": None,
        "features": [],
        "l2_authorized": True,
        "contract": (
            "Create only docs/test-reports/generator-handoff-vm-kimi-l2.json with exactly "
            "the JSON object {\"probe\":\"harness-vm-kimi-l2\",\"result\":\"completed\"}. "
            "Do not alter, delete, or add any other source file."
        ),
        "deliverable": {
            "artifact": ARTIFACT_PATH,
            "schema": "harness/vm-kimi-l2-probe-artifact/v1",
            "commit_to": None,
        },
        "deadline_s": PROBE_TIMEOUT_SECONDS,
    }


def _fixed_target(
    provider: ModuleType, configuration: Any, bridge: SourceBridgeManifest
) -> dict[str, Any]:
    """Build the fixed Generator target from a verified source bridge manifest."""
    bridge_protocol = bridge.protocol()
    target: dict[str, Any] = {
        "target_id": "vm-kimi-l2-generator",
        "integration_id": "vm-kimi-l2",
        "tool": "kimi",
        "invocation": "subagent",
        "model_family": "kimi",
        "priority": 0,
        "roles": ["generator"],
        "adapter": "kimi",
        "sandbox": {"home_dir": "/provider-owned-vm", "env_allow": [], "env_set": {}},
        "timeout_s": PROBE_TIMEOUT_SECONDS,
        "agent_type": bridge.generator_persona,
        "native_agent_type": bridge.generator_native_agent_type,
        "bridge_id": bridge.bridge_id,
        "bridge_strategy": bridge.strategy,
        "session_scope": "same-session",
        "bridge_protocol": bridge_protocol,
        "bridge_provider_id": provider.PROVIDER_ID,
        "bridge_provider_kind": provider.PROVIDER_KIND,
        "bridge_provider_contract_sha256": configuration.contract_sha256,
        "adapter_execution_contract_sha256": provider._canonical_sha256(
            "harness/vm-kimi-l2-probe-adapter/v1", bridge_protocol
        ),
        "capabilities": ["build"],
    }
    target["execution_provenance_sha256"] = provider._canonical_sha256(
        "harness/vm-kimi-l2-probe-target/v1", target
    )
    return target


def _require_provider_sha256(provider: ModuleType, value: Any, label: str) -> str:
    if not isinstance(value, str) or provider.SHA256.fullmatch(value) is None:
        raise ProbeError(f"{label} is invalid")
    return value


def _create_probe_binding(
    provider: ModuleType,
    *,
    target: Mapping[str, Any],
    bridge: SourceBridgeManifest,
    provider_source_sha256: str,
    envelope_sha256: str,
    runner_sha256: str,
    cli_bundle_sha256: str,
    nonce: str | None = None,
) -> _ProbeBinding:
    """Bind this evaluator-only invocation without issuing a provider attestation."""
    probe_nonce = nonce if nonce is not None else secrets.token_hex(16)
    if not isinstance(probe_nonce, str) or NONCE_HEX.fullmatch(probe_nonce) is None:
        raise ProbeError("fixed probe nonce is invalid")
    target_provenance = _require_provider_sha256(
        provider, target.get("execution_provenance_sha256"), "fixed probe target provenance"
    )
    provider_digest = _require_provider_sha256(
        provider, provider_source_sha256, "fixed probe provider source digest"
    )
    envelope_digest = _require_provider_sha256(
        provider, envelope_sha256, "fixed probe envelope digest"
    )
    runner_digest = _require_provider_sha256(provider, runner_sha256, "fixed probe runner digest")
    bundle_digest = _require_provider_sha256(
        provider, cli_bundle_sha256, "fixed probe CLI bundle digest"
    )
    manifest_digest = _require_provider_sha256(
        provider, bridge.sha256, "fixed probe bridge manifest digest"
    )
    payload = {
        "version": PROBE_BINDING_VERSION,
        "scope": "evaluator-controlled-fixed-generator-child",
        "nonce_sha256": hashlib.sha256(probe_nonce.encode("ascii")).hexdigest(),
        "target_execution_provenance_sha256": target_provenance,
        "provider_source_sha256": provider_digest,
        "envelope_sha256": envelope_digest,
        "runner_sha256": runner_digest,
        "cli_bundle_sha256": bundle_digest,
        "bridge_manifest_sha256": manifest_digest,
        "bridge": {
            "id": bridge.bridge_id,
            "strategy": bridge.strategy,
            "protocol": bridge.protocol(),
            "generator_persona": bridge.generator_persona,
            "generator_native_agent_type": bridge.generator_native_agent_type,
        },
    }
    return _ProbeBinding(
        nonce=probe_nonce,
        sha256=provider._canonical_sha256("harness/vm-kimi-l2-probe-binding/v1", payload),
        bridge_manifest_sha256=manifest_digest,
        provider_source_sha256=provider_digest,
    )


def _write_private_json(provider: ModuleType, destination: Path, value: dict[str, Any]) -> None:
    """Use the provider's exclusive private JSON writer for synthetic inputs."""
    provider._write_json_exclusive(destination, value)
    provider._secure_regular_file(destination, "fixed probe JSON", require_private=True)


def _safe_archive_name(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise ProbeError("fixed probe archive entry name is invalid")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ProbeError("fixed probe archive entry name is invalid")
    return value


def _private_archive_entry(
    provider: ModuleType,
    *,
    name: str,
    source: Path,
    label: str,
    maximum_bytes: int,
) -> _ArchiveEntry:
    """Bind a streamed tar entry to one private snapshot inode and size."""
    _safe_archive_name(name)
    provider._secure_regular_file(source, label, require_private=True)
    try:
        entry = source.lstat()
    except OSError as exc:
        raise ProbeError(f"{label} is unavailable") from exc
    if (
        stat.S_ISLNK(entry.st_mode)
        or not stat.S_ISREG(entry.st_mode)
        or entry.st_nlink != 1
        or entry.st_size < 0
        or entry.st_size > maximum_bytes
    ):
        raise ProbeError(f"{label} is invalid")
    return _ArchiveEntry(
        name=name,
        label=label,
        size=entry.st_size,
        source=source,
        source_device=entry.st_dev,
        source_inode=entry.st_ino,
    )


def _fixed_archive_entries(provider: ModuleType, snapshots: Any) -> tuple[_ArchiveEntry, ...]:
    """Preflight exact entries and their aggregate uncompressed byte ceiling."""
    if set(snapshots.runners) != set(provider.RUNNER_NAMES):
        raise ProbeError("fixed probe runner snapshot set is invalid")
    entries: list[_ArchiveEntry] = []
    for source_path, contents in FIXED_SOURCE_FILES.items():
        name = _safe_archive_name(f"source/{source_path}")
        entries.append(
            _ArchiveEntry(
                name=name,
                label=f"fixed probe source {source_path}",
                size=len(contents),
                contents=contents,
            )
        )
    entries.extend(
        (
            _private_archive_entry(
                provider,
                name=".harness-envelope.json",
                source=snapshots.envelope,
                label="fixed probe envelope snapshot",
                maximum_bytes=provider.MAX_ENVELOPE_BYTES,
            ),
            _private_archive_entry(
                provider,
                name=".harness-target.json",
                source=snapshots.target,
                label="fixed probe target snapshot",
                maximum_bytes=provider.MAX_TARGET_BYTES,
            ),
            _private_archive_entry(
                provider,
                name=".harness-cli-bundle.tar.gz",
                source=snapshots.cli_bundle,
                label="fixed probe CLI bundle snapshot",
                maximum_bytes=provider.MAX_CLI_BUNDLE_BYTES,
            ),
        )
    )
    for runner_name in provider.RUNNER_NAMES:
        entries.append(
            _private_archive_entry(
                provider,
                name=f".harness-runner/{runner_name}",
                source=snapshots.runners[runner_name],
                label=f"fixed probe runner snapshot {runner_name}",
                maximum_bytes=provider.MAX_RUNNER_BYTES,
            )
        )
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise ProbeError("fixed probe archive contains duplicate entries")
    if len(entries) > provider.MAX_SOURCE_ARCHIVE_ENTRIES:
        raise ProbeError("fixed probe archive exceeds its entry limit")
    raw_total = sum(entry.size for entry in entries)
    if raw_total > provider.MAX_COPYIN_ARCHIVE_BYTES:
        raise ProbeError("fixed probe archive exceeds its raw size limit")
    return tuple(entries)


def _tar_info(entry: _ArchiveEntry) -> tarfile.TarInfo:
    info = tarfile.TarInfo(entry.name)
    info.size = entry.size
    info.mode = 0o600
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _stream_archive_entry(archive: tarfile.TarFile, entry: _ArchiveEntry) -> None:
    """Write one fixed entry without materializing provider snapshots in memory."""
    info = _tar_info(entry)
    if entry.contents is not None:
        if entry.source is not None or len(entry.contents) != entry.size:
            raise ProbeError("fixed probe archive entry is invalid")
        archive.addfile(info, io.BytesIO(entry.contents))
        return
    if (
        entry.source is None
        or entry.source_device is None
        or entry.source_inode is None
    ):
        raise ProbeError("fixed probe archive entry is invalid")
    try:
        initial = entry.source.lstat()
        descriptor = os.open(entry.source, _source_open_flags(entry.label, directory=False))
    except OSError as exc:
        raise ProbeError(f"{entry.label} is unavailable") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(initial.st_mode)
            or stat.S_ISLNK(initial.st_mode)
            or initial.st_nlink != 1
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or initial.st_dev != entry.source_device
            or initial.st_ino != entry.source_inode
            or initial.st_size != entry.size
            or opened.st_dev != entry.source_device
            or opened.st_ino != entry.source_inode
            or opened.st_size != entry.size
        ):
            raise ProbeError(f"{entry.label} changed before archive streaming")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            archive.addfile(info, source)
        final = os.fstat(descriptor)
        if (
            final.st_dev != opened.st_dev
            or final.st_ino != opened.st_ino
            or final.st_size != opened.st_size
        ):
            raise ProbeError(f"{entry.label} changed during archive streaming")
    except OSError as exc:
        raise ProbeError(f"{entry.label} is unavailable") from exc
    finally:
        os.close(descriptor)


def _create_fixed_probe_archive(
    provider: ModuleType,
    *,
    snapshots: Any,
    destination: Path,
) -> None:
    """Stage only fixed source bytes plus provider-private snapshots.

    This intentionally remains a small local tar builder until the provider
    publishes a common input-packaging helper that accepts synthetic source
    bytes.  It does not accept a project path, ref, registry, or caller data.
    """
    provider._secure_directory(destination.parent, "fixed probe archive parent")
    if destination.exists() or destination.is_symlink():
        raise ProbeError("fixed probe archive already exists")
    entries = _fixed_archive_entries(provider, snapshots)

    descriptor: int | None = None
    succeeded = False
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | _required_no_follow_flag("fixed probe archive"),
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            capped = _CappedWriter(stream, provider.MAX_COPYIN_ARCHIVE_BYTES)
            with tarfile.open(fileobj=capped, mode="w|gz", format=tarfile.PAX_FORMAT) as archive:
                for entry in entries:
                    _stream_archive_entry(archive, entry)
            capped.flush()
        if destination.stat().st_size > provider.MAX_COPYIN_ARCHIVE_BYTES:
            raise ProbeError("fixed probe archive exceeds its compressed size limit")
        succeeded = True
    except ProbeError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise ProbeError("fixed probe archive cannot be created") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if not succeeded:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass


def _read_exact_probe_artifact(provider: ModuleType, artifact: Path) -> None:
    raw = provider._read_regular_file_capped(
        artifact, "fixed probe artifact", MAX_PROBE_ARTIFACT_BYTES
    )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProbeError("fixed probe artifact is invalid") from exc
    if value != EXPECTED_ARTIFACT:
        raise ProbeError("fixed probe artifact does not match the commissioned result")


def _verify_fixed_return(
    provider: ModuleType,
    extracted: Mapping[str, Path],
) -> tuple[Path, str]:
    """Reject any source effect beyond the fixed artifact in the temporary VM."""
    artifact_key = f"source/{ARTIFACT_PATH}"
    expected = {"receipt/bridge-result.json", "source/README.md", artifact_key}
    if set(extracted) != expected:
        raise ProbeError("fixed probe returned an unexpected source tree")
    source = extracted["source/README.md"]
    source_bytes = provider._read_regular_file_capped(
        source, "fixed probe source", len(FIXED_SOURCE_FILES["README.md"])
    )
    if source_bytes != FIXED_SOURCE_FILES["README.md"]:
        raise ProbeError("fixed probe altered its synthetic source")
    artifact = extracted[artifact_key]
    _read_exact_probe_artifact(provider, artifact)
    return artifact, provider._sha256_path(artifact)


def _sanitized_evidence(
    provider: ModuleType,
    *,
    receipt: Mapping[str, Any],
    artifact_sha256: str,
    probe_binding_sha256: str,
    bridge_manifest_sha256: str,
    provider_source_sha256: str,
    duration_s: int,
) -> dict[str, Any]:
    """Return only evaluator-controlled lineage; no paths, prompts, or model text."""
    required = {
        "bridge_kind",
        "session_scope",
        "subagent_type",
        "terminal_status",
        "session_id_sha256",
        "child_call_id_sha256",
    }
    if not required.issubset(receipt):
        raise ProbeError("fixed probe receipt lacks evidence")
    for field in ("session_id_sha256", "child_call_id_sha256"):
        value = receipt[field]
        if not isinstance(value, str) or provider.SHA256.fullmatch(value) is None:
            raise ProbeError("fixed probe receipt evidence is invalid")
    if not isinstance(artifact_sha256, str) or provider.SHA256.fullmatch(artifact_sha256) is None:
        raise ProbeError("fixed probe artifact digest is invalid")
    _require_provider_sha256(provider, probe_binding_sha256, "fixed probe binding digest")
    _require_provider_sha256(
        provider, bridge_manifest_sha256, "fixed probe bridge manifest digest"
    )
    _require_provider_sha256(
        provider, provider_source_sha256, "fixed probe provider source digest"
    )
    if not isinstance(duration_s, int) or duration_s < 0:
        raise ProbeError("fixed probe duration is invalid")
    return {
        "version": PROBE_VERSION,
        "outcome": "passed",
        "scope": "evaluator-controlled-fixed-generator-child",
        "l2_confirmation": OUT_OF_BAND_MANUAL_CONFIRMATION,
        "runtime": ISOLATED_RUNTIME_LAUNCH_REQUIREMENT,
        "input": "fixed-synthetic",
        "role": "generator",
        "tool": "kimi",
        "provider": {"id": provider.PROVIDER_ID, "kind": provider.PROVIDER_KIND},
        "bridge": {
            "kind": receipt["bridge_kind"],
            "session_scope": receipt["session_scope"],
            "subagent_type": receipt["subagent_type"],
            "terminal_status": receipt["terminal_status"],
            "session_id_sha256": receipt["session_id_sha256"],
            "child_call_id_sha256": receipt["child_call_id_sha256"],
        },
        "artifact_sha256": artifact_sha256,
        "probe_binding_sha256": probe_binding_sha256,
        "bridge_manifest_sha256": bridge_manifest_sha256,
        "provider_source_sha256": provider_source_sha256,
        "effective_timeout_s": PROBE_TIMEOUT_SECONDS,
        "duration_s": duration_s,
    }


def _cleanup_probe_guest(
    provider: ModuleType,
    configuration: Any,
    *,
    guest_root: str,
    unit: str,
    vendor_drop_unit: str,
    guest_job_touched: bool,
    firewall_reset_required: bool,
) -> None:
    """Always reset the shared VM firewall even when guest cleanup itself fails."""
    try:
        if guest_job_touched:
            provider._cleanup_guest_job(
                configuration,
                guest_root,
                vendor_drop_unit,
                unit,
                f"{unit}-copyout",
            )
    finally:
        if firewall_reset_required:
            provider._reset_guest_egress_baseline(configuration)


def _validate_pinned_runner_snapshots(
    provider: ModuleType, snapshots: Any, session: _SourceProviderSession
) -> None:
    """Bind provider snapshot lineage back to the runner bytes staged before exec."""
    if session.closed or set(session.runner_sha256) != set(SOURCE_RUNNER_NAMES):
        raise ProbeError("pinned source runner lineage is unavailable")
    pinned_digests = {
        name: _require_provider_sha256(
            provider, session.runner_sha256[name], f"pinned source runner {name} digest"
        )
        for name in SOURCE_RUNNER_NAMES
    }
    expected = _require_provider_sha256(
        provider,
        provider._canonical_sha256("harness/vm-bridge-runner/v1", pinned_digests),
        "pinned source runner aggregate digest",
    )
    observed = _require_provider_sha256(
        provider, getattr(snapshots, "runner_sha256", None), "provider runner snapshot digest"
    )
    if observed != expected:
        raise ProbeError("provider runner snapshot does not match pinned source")


def _verify_vendor_drop_preflight(
    provider: ModuleType,
    configuration: Any,
    *,
    guest_root: str,
    unit: str,
) -> None:
    """Prove the exact vendor privilege posture before opening a broker lease.

    This opt-in L2 check uses the same root-supervisor systemd profile and
    fixed ``setpriv`` transition as the session bridge. It has no network,
    credential, CLI, or project input; only a fixed sentinel may return.
    """
    result = provider._guest_restricted_unit(
        configuration,
        guest_root=guest_root,
        unit=unit,
        timeout=VENDOR_DROP_PREFLIGHT_TIMEOUT_SECONDS,
        environment={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        network_host=None,
        program=list(VENDOR_DROP_PREFLIGHT_PROGRAM),
        root_supervisor=True,
    )
    if result.returncode != 0 or result.stdout != VENDOR_DROP_PREFLIGHT_SENTINEL:
        raise ProbeError("vendor privilege-drop preflight did not prove isolation")


def run_probe(
    *, confirmed: bool = False, provider: ModuleType | None = None
) -> dict[str, Any]:
    """Run one fixed L2 probe after manual confirmation in an isolated runtime."""
    if confirmed is not True:
        raise ProbeError("fixed probe requires explicit live L2 confirmation")
    if not _has_isolated_runtime():
        raise ProbeError("fixed probe requires an isolated Python runtime")
    loaded_provider = provider or load_source_provider()
    session = _source_provider_session(loaded_provider)
    if session is None or session.closed:
        raise ProbeError("fixed probe requires a pinned source provider session")
    try:
        return _run_pinned_probe(loaded_provider, session=session, confirmed=confirmed)
    finally:
        session.close()


def _run_pinned_probe(
    provider: ModuleType, *, session: _SourceProviderSession, confirmed: bool
) -> dict[str, Any]:
    """Run the fixed probe while its provider stage remains pinned through snapshot."""
    configuration = provider.load_provider_configuration()
    policy = provider._broker_policy(configuration)
    provider._validated_external_timeout(PROBE_TIMEOUT_SECONDS)
    bridge = session.bridge
    target = _fixed_target(provider, configuration, bridge)
    runs_root = provider._provider_private_runs_root()

    with tempfile.TemporaryDirectory(prefix="harness-vm-kimi-l2-", dir=str(runs_root)) as raw_root:
        run_root = Path(raw_root)
        provider._secure_directory(run_root, "fixed probe run root")
        envelope_source = run_root / "fixed-envelope.json"
        _write_private_json(provider, envelope_source, _fixed_envelope(confirmed=confirmed))
        input_root, envelope_snapshot, envelope_sha256 = provider._snapshot_launch_envelope(
            run_root, envelope_source
        )
        snapshots = provider._snapshot_launch_inputs(
            configuration,
            input_root=input_root,
            envelope=envelope_snapshot,
            envelope_sha256=envelope_sha256,
            target=target,
        )
        _validate_pinned_runner_snapshots(provider, snapshots, session)
        # The provider has consumed sibling runners from its staged __file__
        # directory. No VM or vendor process needs that stage afterwards.
        session.close()
        launch_target = provider._load_launch_target(
            snapshots.target, target["execution_provenance_sha256"]
        )
        if launch_target.get("bridge_provider_contract_sha256") != configuration.contract_sha256:
            raise ProbeError("fixed probe target contract drifted")
        if launch_target.get("roles") != ["generator"] or launch_target.get("native_agent_type") != "coder":
            raise ProbeError("fixed probe target is not the fixed Generator/coder route")
        timeout_s = provider._validated_external_timeout(launch_target.get("timeout_s"))
        bridge_command = provider._validate_target_bundle_command(
            configuration, launch_target, cli_bundle=snapshots.cli_bundle
        )
        if bridge_command != ("kimi", "acp"):
            raise ProbeError("fixed probe bridge command drifted")
        kimi_identity = provider._bundle_kimi_identity(snapshots.cli_bundle)
        archive = run_root / "fixed-copyin.tar.gz"
        _create_fixed_probe_archive(provider, snapshots=snapshots, destination=archive)

        guest_token = secrets.token_hex(16)
        guest_root = f"/var/lib/harness-vm-v1/jobs/{guest_token}"
        unit = f"harness-vm-kimi-l2-{guest_token}"
        vendor_drop_unit = f"{unit}-drop"
        copyout = run_root / "copyout"
        copyout.mkdir(mode=0o700)
        provider._secure_directory(copyout, "fixed probe copy-out directory")
        started = time.monotonic()
        guest_job_touched = False
        firewall_reset_required = False
        with provider._exclusive_provider_launch_lock(runs_root):
            provider._assert_vm_ready(configuration)
            binding = _create_probe_binding(
                provider,
                target=launch_target,
                bridge=bridge,
                provider_source_sha256=session.provider_sha256,
                envelope_sha256=snapshots.envelope_sha256,
                runner_sha256=snapshots.runner_sha256,
                cli_bundle_sha256=snapshots.cli_bundle_sha256,
            )
            try:
                guest_job_touched = True
                provider._copy_archive_to_guest(
                    configuration, archive, guest_root, (bridge_command[0],)
                )
                _verify_vendor_drop_preflight(
                    provider,
                    configuration,
                    guest_root=guest_root,
                    unit=vendor_drop_unit,
                )
                with provider.BrokerLease(policy, kimi_identity) as broker:
                    if broker.port is None:
                        raise ProbeError("fixed probe broker is unavailable")
                    firewall_reset_required = True
                    provider._reset_guest_egress_baseline(configuration)
                    provider._set_guest_egress_policy(configuration, policy, broker.port)
                    provider._run_guest_worker(
                        configuration,
                        guest_root=guest_root,
                        unit=unit,
                        timeout_s=timeout_s,
                        launch_nonce=binding.nonce,
                        # The existing worker field is a fixed protocol slot;
                        # this value is the evaluator's private binding, not a
                        # provider-issued launch attestation.
                        launch_attestation_sha256=binding.sha256,
                        broker=broker,
                    )
                    payload = provider._guest_copyout(
                        configuration,
                        guest_root=guest_root,
                        artifact=ARTIFACT_PATH,
                        unit=unit,
                    )
                extracted = provider._extract_copyout(payload, copyout)
                artifact, artifact_sha256 = _verify_fixed_return(provider, extracted)
                receipt = provider._validate_bridge_receipt(
                    extracted["receipt/bridge-result.json"],
                    target=launch_target,
                    launch_nonce=binding.nonce,
                    launch_attestation_sha256=binding.sha256,
                    artifact_sha256=artifact_sha256,
                )
                if artifact != extracted[f"source/{ARTIFACT_PATH}"]:
                    raise ProbeError("fixed probe artifact path drifted")
                return _sanitized_evidence(
                    provider,
                    receipt=receipt,
                    artifact_sha256=artifact_sha256,
                    probe_binding_sha256=binding.sha256,
                    bridge_manifest_sha256=binding.bridge_manifest_sha256,
                    provider_source_sha256=binding.provider_source_sha256,
                    duration_s=max(0, int(time.monotonic() - started)),
                )
            finally:
                _cleanup_probe_guest(
                    provider,
                    configuration,
                    guest_root=guest_root,
                    unit=unit,
                    vendor_drop_unit=vendor_drop_unit,
                    guest_job_touched=guest_job_touched,
                    firewall_reset_required=firewall_reset_required,
                )


def _failure_evidence() -> dict[str, str]:
    return {
        "version": PROBE_VERSION,
        "outcome": "failed",
        "reason": "probe_failed",
        "confirmation_mode": OUT_OF_BAND_MANUAL_CONFIRMATION,
    }


def _refused_evidence() -> dict[str, str]:
    return {
        "version": PROBE_VERSION,
        "outcome": "refused",
        "reason": "confirmation_required",
        "confirmation_mode": OUT_OF_BAND_MANUAL_CONFIRMATION,
    }


def _isolated_runtime_refused_evidence() -> dict[str, str]:
    return {
        "version": PROBE_VERSION,
        "outcome": "refused",
        "reason": "isolated_runtime_required",
        "confirmation_mode": OUT_OF_BAND_MANUAL_CONFIRMATION,
        "launch_requirement": ISOLATED_RUNTIME_LAUNCH_REQUIREMENT,
    }


def _emit(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values != [CONFIRMATION_FLAG]:
        _emit(_refused_evidence())
        return 2
    if not _has_isolated_runtime():
        _emit(_isolated_runtime_refused_evidence())
        return 2
    try:
        evidence = run_probe(confirmed=True)
    except Exception:
        _emit(_failure_evidence())
        return 2
    _emit(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
