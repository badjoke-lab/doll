"""Acceptance coverage for IMP-083 Lite client resource measurement."""

from __future__ import annotations

import json
import os
from pathlib import Path
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


def _fake_rss() -> ProcessRssSnapshot:
    return ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=1_000_000,
        peak_bytes=2_000_000,
    )


def test_measurement_runs_fixed_client_only_workload_with_content_free_result(tmp_path: Path) -> None:
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


def test_measurement_accepts_existing_empty_target_but_rejects_other_targets(tmp_path: Path) -> None:
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

    monkeypatch.setattr(measurement_module.os, "scandir", fail_scan)
    with pytest.raises(LiteClientMeasurementError, match="could not be traversed") as raised:
        inspect_workspace_disk_usage(root)
    assert "private scan failure" not in str(raised.value)


def test_clock_and_rss_validation_fail_closed(tmp_path: Path) -> None:
    values = iter((10, 9))
    with pytest.raises(LiteClientMeasurementError, match="clock moved backwards"):
        measure_lite_client_resources(
            tmp_path / "backwards",
            clock_ns=lambda: next(values),
            rss_reader=_fake_rss,
        )

    with pytest.raises(LiteClientMeasurementError, match="RSS snapshot is invalid"):
        measure_lite_client_resources(
            tmp_path / "invalid-rss-shape",
            rss_reader=cast(object, lambda: object()),
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


def test_clock_rejects_bool_and_negative_values() -> None:
    with pytest.raises(LiteClientMeasurementError, match="clock is invalid"):
        measurement_module._clock_value(cast(object, lambda: True))
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
    monkeypatch.setattr(measurement_module.os, "name", "nt")
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

    def valid_read(self: Path, *args: object, **kwargs: object) -> str:
        if str(self) == "/proc/self/statm":
            return "100 5 0 0 0 0 0\n"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", valid_read)
    monkeypatch.setattr(measurement_module.os, "sysconf", lambda name: 4096)
    assert measurement_module._linux_current_rss_bytes() == 20_480

    def invalid_read(self: Path, *args: object, **kwargs: object) -> str:
        del self, args, kwargs
        return "invalid"

    monkeypatch.setattr(Path, "read_text", invalid_read)
    assert measurement_module._linux_current_rss_bytes() is None


def test_windows_process_rss_returns_unavailable_without_windows_dll(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delattr(measurement_module.ctypes, "WinDLL", raising=False)
    assert measurement_module._windows_process_rss() == (None, None)
