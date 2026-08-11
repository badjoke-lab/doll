"""Acceptance coverage for IMP-083 Lite client resource measurement."""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
from pytest import MonkeyPatch

from doll import lite_measurement as measurement_module
from doll.lite_measurement import (
    LiteClientMeasurementError,
    ProcessRssSnapshot,
    WorkspaceDiskUsage,
    inspect_workspace_disk_usage,
    measure_lite_client_resources,
    read_process_rss,
)
from doll.state import CURRENT_SCHEMA_VERSION


def _fake_rss() -> ProcessRssSnapshot:
    return ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=1_000_000,
        peak_bytes=2_000_000,
    )


def _load_runner() -> ModuleType:
    runner_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_imp_083_lite_client_measurement.py"
    )
    spec = importlib.util.spec_from_file_location("_imp083_test_runner", runner_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _temporary_git_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "git-repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "IMP-083 Test")
    _git(repository, "config", "user.email", "imp083@example.invalid")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "--quiet", "-m", "baseline")
    return repository, _git(repository, "rev-parse", "HEAD")


class _FakeDiskEntry:
    def __init__(
        self,
        path: Path,
        *,
        directory: bool = False,
        regular_file: bool = True,
        stat_size: int = 0,
        stat_error: bool = False,
    ) -> None:
        self.path = str(path)
        self._directory = directory
        self._regular_file = regular_file
        self._stat_size = stat_size
        self._stat_error = stat_error

    def is_symlink(self) -> bool:
        return False

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        del follow_symlinks
        return self._directory

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        del follow_symlinks
        return self._regular_file

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        del follow_symlinks
        if self._stat_error:
            raise OSError("private stat failure")
        return SimpleNamespace(st_size=self._stat_size)


class _FakeWindowsFunction:
    def __init__(self, result: object) -> None:
        self.result = result
        self.restype: object | None = None
        self.argtypes: object | None = None

    def __call__(self, *arguments: object) -> object:
        del arguments
        return self.result


class _FakeWindowsDll:
    def __init__(self, *, memory_query_result: object = False) -> None:
        self.GetCurrentProcess = _FakeWindowsFunction(1)
        self.GetProcessMemoryInfo = _FakeWindowsFunction(memory_query_result)


class _StaticStatusRepository:
    def __init__(self, status: SimpleNamespace) -> None:
        self._status = status

    def __enter__(self) -> _StaticStatusRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc, traceback

    def status(self) -> SimpleNamespace:
        return self._status


def test_measurement_runs_fixed_client_only_workload_with_content_free_result(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "measurement-workspace"
    result = measure_lite_client_resources(workspace, rss_reader=_fake_rss)

    assert tuple(step.step_id for step in result.steps) == (
        "workspace_initialize",
        "state_initialize",
        "workspace_load",
        "state_read_only_open",
        "doctor_read_only",
    )
    assert all(step.duration_ns >= 0 for step in result.steps)
    assert result.total_duration_ns >= 0
    assert result.process_rss == _fake_rss()
    assert result.workspace_disk.total_bytes > 0
    assert result.workspace_disk.file_count > 0
    assert result.workspace_disk.directory_count >= 7
    assert result.doctor_overall_status == "pass"
    assert result.state_schema_version >= 1
    assert result.state_revision >= 0
    assert result.state_record_count >= 0

    payload = result.to_dict()
    assert payload["schema_version"] == 1
    assert payload["measurement_scope"] == "doll-lite-client-only"
    assert payload["external_runtime_memory_included"] is False
    assert payload["model_memory_included"] is False
    assert payload["model_execution_used"] is False
    assert payload["network_access_used"] is False
    assert payload["cloud_access_used"] is False
    assert payload["thresholds_applied"] is False
    assert payload["lite_performance_gate_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["lite_v1_complete"] is False
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert str(workspace) not in serialized
    assert workspace.name not in serialized
    assert "lite-measurement" not in serialized


def test_measurement_accepts_existing_empty_target_but_rejects_other_targets(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = measure_lite_client_resources(empty, rss_reader=_fake_rss)
    assert result.doctor_overall_status == "pass"

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "existing.txt").write_text("existing", encoding="utf-8")
    with pytest.raises(LiteClientMeasurementError, match="absent or empty"):
        measure_lite_client_resources(nonempty, rss_reader=_fake_rss)

    regular = tmp_path / "regular-file"
    regular.write_text("not a directory", encoding="utf-8")
    with pytest.raises(LiteClientMeasurementError, match="absent or empty"):
        measure_lite_client_resources(regular, rss_reader=_fake_rss)

    with pytest.raises(LiteClientMeasurementError, match="path is invalid"):
        measure_lite_client_resources(cast(Path, "workspace"), rss_reader=_fake_rss)


def test_measurement_rejects_existing_root_symlink_before_initialization(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "workspace-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(LiteClientMeasurementError, match="symbolic link"):
        measure_lite_client_resources(link, rss_reader=_fake_rss)
    assert list(target.iterdir()) == []


def test_measurement_postconditions_fail_closed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        measurement_module,
        "run_doctor",
        lambda root: SimpleNamespace(overall_status="fail"),
    )
    with pytest.raises(LiteClientMeasurementError, match="doctor check did not pass"):
        measure_lite_client_resources(tmp_path / "doctor-fail", rss_reader=_fake_rss)

    monkeypatch.undo()
    cases = (
        (
            SimpleNamespace(
                read_only=False,
                schema_version=CURRENT_SCHEMA_VERSION,
                state_revision=0,
                record_count=0,
            ),
            "read-only check failed",
        ),
        (
            SimpleNamespace(
                read_only=True,
                schema_version=CURRENT_SCHEMA_VERSION + 1,
                state_revision=0,
                record_count=0,
            ),
            "schema changed unexpectedly",
        ),
        (
            SimpleNamespace(
                read_only=True,
                schema_version=CURRENT_SCHEMA_VERSION,
                state_revision=1,
                record_count=0,
            ),
            "revision changed unexpectedly",
        ),
        (
            SimpleNamespace(
                read_only=True,
                schema_version=CURRENT_SCHEMA_VERSION,
                state_revision=0,
                record_count=1,
            ),
            "record count changed unexpectedly",
        ),
    )
    for index, (status, message) in enumerate(cases):
        monkeypatch.setattr(
            measurement_module,
            "open_state_repository",
            lambda *args, status=status, **kwargs: _StaticStatusRepository(status),
        )
        with pytest.raises(LiteClientMeasurementError, match=message):
            measure_lite_client_resources(
                tmp_path / f"postcondition-{index}",
                rss_reader=_fake_rss,
            )


def test_workspace_disk_usage_is_content_free_and_bounded(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    child = root / "nested"
    child.mkdir(parents=True)
    (root / "a.bin").write_bytes(b"abc")
    (child / "b.bin").write_bytes(b"12345")

    usage = inspect_workspace_disk_usage(root)
    assert usage == WorkspaceDiskUsage(total_bytes=8, file_count=2, directory_count=2)
    assert usage.to_dict() == {
        "total_bytes": 8,
        "file_count": 2,
        "directory_count": 2,
    }


def test_workspace_disk_usage_rejects_invalid_root_and_symlinks(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(LiteClientMeasurementError, match="root is invalid"):
        inspect_workspace_disk_usage(missing)
    with pytest.raises(LiteClientMeasurementError, match="root is invalid"):
        inspect_workspace_disk_usage(cast(Path, "bad"))

    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(LiteClientMeasurementError, match="symbolic link"):
        inspect_workspace_disk_usage(root)


def test_workspace_disk_usage_wraps_root_and_escape_resolution_failures(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    original_resolve = Path.resolve

    def fail_root_resolve(self: Path, *, strict: bool = False) -> Path:
        if self == root:
            raise OSError("private root failure")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_root_resolve)
    with pytest.raises(LiteClientMeasurementError, match="root is unavailable") as raised:
        inspect_workspace_disk_usage(root)
    assert "private root failure" not in str(raised.value)

    monkeypatch.undo()
    inside = root / "inside.txt"
    inside.write_text("inside", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    root_resolved = root.resolve(strict=True)
    outside_resolved = outside.resolve(strict=True)
    original_resolve = Path.resolve

    def escape_resolve(self: Path, *, strict: bool = False) -> Path:
        if self == root:
            return root_resolved
        if self == inside:
            return outside_resolved
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", escape_resolve)
    with pytest.raises(LiteClientMeasurementError, match="escaped the selected root"):
        inspect_workspace_disk_usage(root)


def test_workspace_disk_usage_rejects_file_stat_and_entry_types(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    item = root / "item"
    item.write_text("item", encoding="utf-8")

    unreadable = _FakeDiskEntry(item, stat_error=True)
    monkeypatch.setattr(os, "scandir", lambda path: nullcontext([unreadable]))
    with pytest.raises(LiteClientMeasurementError, match="file is unreadable") as raised:
        inspect_workspace_disk_usage(root)
    assert "private stat failure" not in str(raised.value)

    negative = _FakeDiskEntry(item, stat_size=-1)
    monkeypatch.setattr(os, "scandir", lambda path: nullcontext([negative]))
    with pytest.raises(LiteClientMeasurementError, match="file size is invalid"):
        inspect_workspace_disk_usage(root)

    unsupported = _FakeDiskEntry(item, regular_file=False)
    monkeypatch.setattr(os, "scandir", lambda path: nullcontext([unsupported]))
    with pytest.raises(LiteClientMeasurementError, match="unsupported entry"):
        inspect_workspace_disk_usage(root)


def test_workspace_disk_usage_rejects_entry_and_depth_limits(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "one.txt").write_text("1", encoding="utf-8")
    (root / "two.txt").write_text("2", encoding="utf-8")

    monkeypatch.setattr(measurement_module, "_MAX_WORKSPACE_ENTRIES", 1)
    with pytest.raises(LiteClientMeasurementError, match="entry limit"):
        inspect_workspace_disk_usage(root)

    monkeypatch.setattr(measurement_module, "_MAX_WORKSPACE_ENTRIES", 20_000)
    monkeypatch.setattr(measurement_module, "_MAX_WORKSPACE_DEPTH", 0)
    with pytest.raises(LiteClientMeasurementError, match="depth limit"):
        inspect_workspace_disk_usage(root)


def test_workspace_disk_usage_wraps_scan_failures(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()

    def fail_scan(path: object) -> object:
        del path
        raise OSError("private scan failure")

    monkeypatch.setattr(os, "scandir", fail_scan)
    with pytest.raises(LiteClientMeasurementError, match="could not be traversed") as raised:
        inspect_workspace_disk_usage(root)
    assert "private scan failure" not in str(raised.value)


def test_clock_and_rss_validation_fail_closed(tmp_path: Path) -> None:
    values = iter((10, 9, 8))
    with pytest.raises(LiteClientMeasurementError, match="clock moved backwards"):
        measure_lite_client_resources(
            tmp_path / "backwards",
            clock_ns=lambda: next(values),
            rss_reader=_fake_rss,
        )

    with pytest.raises(LiteClientMeasurementError, match="RSS snapshot is invalid"):
        measure_lite_client_resources(
            tmp_path / "invalid-rss-shape",
            rss_reader=cast(Callable[[], ProcessRssSnapshot], lambda: object()),
        )

    def negative_rss() -> ProcessRssSnapshot:
        return ProcessRssSnapshot(
            source="resource-ru_maxrss",
            current_bytes=-1,
            peak_bytes=1,
        )

    with pytest.raises(LiteClientMeasurementError, match="RSS value is invalid"):
        measure_lite_client_resources(tmp_path / "negative-rss", rss_reader=negative_rss)

    def inconsistent_rss() -> ProcessRssSnapshot:
        return ProcessRssSnapshot(
            source="resource-ru_maxrss",
            current_bytes=2,
            peak_bytes=1,
        )

    with pytest.raises(LiteClientMeasurementError, match="RSS values are inconsistent"):
        measure_lite_client_resources(tmp_path / "inconsistent-rss", rss_reader=inconsistent_rss)


def test_clock_rejects_bool_non_integer_and_negative_values() -> None:
    with pytest.raises(LiteClientMeasurementError, match="clock is invalid"):
        measurement_module._clock_value(cast(Callable[[], int], lambda: True))
    with pytest.raises(LiteClientMeasurementError, match="clock is invalid"):
        measurement_module._clock_value(cast(Callable[[], int], lambda: cast(int, "bad")))
    with pytest.raises(LiteClientMeasurementError, match="clock is invalid"):
        measurement_module._clock_value(lambda: -1)
    assert measurement_module._duration(4, 9) == 5
    with pytest.raises(LiteClientMeasurementError, match="clock moved backwards"):
        measurement_module._duration(9, 4)


def test_process_rss_snapshot_serialization_and_actual_adapter() -> None:
    unavailable = ProcessRssSnapshot(source="unavailable", current_bytes=None, peak_bytes=None)
    assert unavailable.available is False
    assert unavailable.to_dict() == {
        "source": "unavailable",
        "available": False,
        "current_bytes": None,
        "peak_bytes": None,
    }

    actual = read_process_rss()
    assert actual.source in {
        "resource-ru_maxrss",
        "windows-process-memory-counters",
        "unavailable",
    }
    assert actual.current_bytes is None or actual.current_bytes >= 0
    assert actual.peak_bytes is None or actual.peak_bytes >= 0
    if actual.current_bytes is not None and actual.peak_bytes is not None:
        assert actual.current_bytes <= actual.peak_bytes


def test_read_process_rss_windows_wrapper_can_be_injected(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(
        measurement_module,
        "_windows_process_rss",
        lambda: (123, 456),
    )
    snapshot = read_process_rss()
    assert snapshot.source == "windows-process-memory-counters"
    assert snapshot.current_bytes == 123
    assert snapshot.peak_bytes == 456

    monkeypatch.setattr(measurement_module, "_windows_process_rss", lambda: (None, None))
    unavailable = read_process_rss()
    assert unavailable.source == "unavailable"
    assert unavailable.available is False


def test_linux_current_rss_parser_handles_valid_and_invalid_data(monkeypatch: MonkeyPatch) -> None:
    original = Path.read_text

    def valid_read(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if str(self).replace("\\", "/").endswith("/proc/self/statm"):
            return "100 5 0 0 0 0 0\n"
        return original(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", valid_read)
    monkeypatch.setattr(os, "sysconf", lambda name: 4096, raising=False)
    assert measurement_module._linux_current_rss_bytes() == 20_480

    def invalid_read(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        del self, encoding, errors
        return "invalid"

    monkeypatch.setattr(Path, "read_text", invalid_read)
    assert measurement_module._linux_current_rss_bytes() is None


def test_linux_current_rss_parser_rejects_invalid_numeric_values(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: "100 -1 0\n")
    monkeypatch.setattr(os, "sysconf", lambda name: 4096, raising=False)
    assert measurement_module._linux_current_rss_bytes() is None

    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: "100 5 0\n")
    monkeypatch.setattr(os, "sysconf", lambda name: 0, raising=False)
    assert measurement_module._linux_current_rss_bytes() is None

    monkeypatch.setattr(os, "sysconf", lambda name: cast(int, "4096"), raising=False)
    assert measurement_module._linux_current_rss_bytes() is None

    def fail_sysconf(name: str) -> int:
        del name
        raise TypeError("private sysconf failure")

    monkeypatch.setattr(os, "sysconf", fail_sysconf, raising=False)
    assert measurement_module._linux_current_rss_bytes() is None


def test_windows_process_rss_returns_unavailable_without_windows_dll(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    assert measurement_module._windows_process_rss() == (None, None)


def test_windows_process_rss_handles_failed_query_and_dll_errors(monkeypatch: MonkeyPatch) -> None:
    kernel32 = _FakeWindowsDll()
    psapi = _FakeWindowsDll(memory_query_result=False)

    def fake_win_dll(name: str, *, use_last_error: bool = False) -> _FakeWindowsDll:
        del use_last_error
        return kernel32 if name == "kernel32" else psapi

    monkeypatch.setattr(ctypes, "WinDLL", fake_win_dll, raising=False)
    assert measurement_module._windows_process_rss() == (None, None)

    def fail_win_dll(name: str, *, use_last_error: bool = False) -> object:
        del name, use_last_error
        raise OSError("private Windows DLL failure")

    monkeypatch.setattr(ctypes, "WinDLL", fail_win_dll, raising=False)
    assert measurement_module._windows_process_rss() == (None, None)


def test_runner_requires_clean_tracked_index_and_worktree(tmp_path: Path) -> None:
    runner = _load_runner()
    repository, head = _temporary_git_repository(tmp_path)
    runner.ROOT = repository
    arguments = argparse.Namespace(
        commit_sha=head,
        evidence_level="ci",
        offline_confirmed=False,
        local_only_confirmed=False,
    )
    assert runner._validate_environment(arguments) is False

    tracked = repository / "tracked.txt"
    tracked.write_text("modified\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="working tree differs from index"):
        runner._validate_environment(arguments)

    _git(repository, "checkout", "--", "tracked.txt")
    tracked.write_text("staged\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    with pytest.raises(RuntimeError, match="tracked index differs from HEAD"):
        runner._validate_environment(arguments)


def test_runner_rejects_commit_mismatch_before_checkout_claim(tmp_path: Path) -> None:
    runner = _load_runner()
    repository, head = _temporary_git_repository(tmp_path)
    runner.ROOT = repository
    arguments = argparse.Namespace(
        commit_sha="0" * 40 if head != "0" * 40 else "1" * 40,
        evidence_level="ci",
        offline_confirmed=False,
        local_only_confirmed=False,
    )
    with pytest.raises(RuntimeError, match="commit mismatch"):
        runner._validate_environment(arguments)
