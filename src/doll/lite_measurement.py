"""Bounded privacy-safe resource measurement for the doll Lite client itself."""

from __future__ import annotations

import ctypes
import os
import platform
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from doll.doctor import run_doctor
from doll.state import initialize_state_repository, open_state_repository
from doll.workspace import initialize_workspace, load_workspace

LITE_CLIENT_MEASUREMENT_SCHEMA_VERSION: Final = 1
_MAX_WORKSPACE_ENTRIES: Final = 20_000
_MAX_WORKSPACE_DEPTH: Final = 32

RssMeasurementSource = Literal[
    "resource-ru_maxrss",
    "windows-process-memory-counters",
    "unavailable",
]


class LiteClientMeasurementError(RuntimeError):
    """Raised when a bounded Lite client measurement cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class LiteClientMeasurementStep:
    """One named monotonic-duration measurement in the fixed client workload."""

    step_id: str
    duration_ns: int

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "duration_ns": self.duration_ns,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceDiskUsage:
    """Content-free bounded disk usage for one explicit workspace tree."""

    total_bytes: int
    file_count: int
    directory_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total_bytes": self.total_bytes,
            "file_count": self.file_count,
            "directory_count": self.directory_count,
        }


@dataclass(frozen=True, slots=True)
class ProcessRssSnapshot:
    """Doll-process RSS values only; external runtime/model memory is excluded."""

    source: RssMeasurementSource
    current_bytes: int | None
    peak_bytes: int | None

    @property
    def available(self) -> bool:
        return self.current_bytes is not None or self.peak_bytes is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "available": self.available,
            "current_bytes": self.current_bytes,
            "peak_bytes": self.peak_bytes,
        }


@dataclass(frozen=True, slots=True)
class LiteClientResourceMeasurement:
    """Privacy-safe measurement result for one synthetic Lite client workload."""

    operating_system: str
    architecture: str
    python_version: str
    steps: tuple[LiteClientMeasurementStep, ...]
    total_duration_ns: int
    process_rss: ProcessRssSnapshot
    workspace_disk: WorkspaceDiskUsage
    doctor_overall_status: str
    state_schema_version: int
    state_revision: int
    state_record_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": LITE_CLIENT_MEASUREMENT_SCHEMA_VERSION,
            "measurement_scope": "doll-lite-client-only",
            "operating_system": self.operating_system,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "steps": [step.to_dict() for step in self.steps],
            "total_duration_ns": self.total_duration_ns,
            "process_rss": self.process_rss.to_dict(),
            "workspace_disk": self.workspace_disk.to_dict(),
            "doctor_overall_status": self.doctor_overall_status,
            "state_schema_version": self.state_schema_version,
            "state_revision": self.state_revision,
            "state_record_count": self.state_record_count,
            "synthetic_fixture_created": True,
            "post_setup_read_only_operations": True,
            "external_runtime_memory_included": False,
            "model_memory_included": False,
            "model_execution_used": False,
            "network_access_used": False,
            "cloud_access_used": False,
            "automatic_download_used": False,
            "thresholds_applied": False,
            "lite_performance_gate_complete": False,
            "phase6_gate_complete": False,
            "lite_v1_complete": False,
        }


def measure_lite_client_resources(
    workspace_path: Path,
    *,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
    rss_reader: Callable[[], ProcessRssSnapshot] | None = None,
) -> LiteClientResourceMeasurement:
    """Measure a fixed local-only doll client workload in one new explicit workspace."""

    if not isinstance(workspace_path, Path):
        raise LiteClientMeasurementError("Lite measurement workspace path is invalid")
    if workspace_path.exists() and (not workspace_path.is_dir() or any(workspace_path.iterdir())):
        raise LiteClientMeasurementError("Lite measurement workspace must be absent or empty")

    reader = rss_reader or read_process_rss
    steps: list[LiteClientMeasurementStep] = []
    overall_start = _clock_value(clock_ns)

    start = _clock_value(clock_ns)
    initialized = initialize_workspace(
        workspace_path,
        instance_label="lite-measurement",
        profile_preference="lite",
    )
    steps.append(_step("workspace_initialize", start, _clock_value(clock_ns)))

    start = _clock_value(clock_ns)
    with initialize_state_repository(initialized.root) as repository:
        initialized_status = repository.status()
    steps.append(_step("state_initialize", start, _clock_value(clock_ns)))

    start = _clock_value(clock_ns)
    loaded = load_workspace(initialized.root)
    steps.append(_step("workspace_load", start, _clock_value(clock_ns)))

    start = _clock_value(clock_ns)
    with open_state_repository(
        loaded.root,
        read_only=True,
        immutable=True,
    ) as repository:
        read_only_status = repository.status()
    steps.append(_step("state_read_only_open", start, _clock_value(clock_ns)))

    start = _clock_value(clock_ns)
    doctor = run_doctor(loaded.root)
    steps.append(_step("doctor_read_only", start, _clock_value(clock_ns)))

    total_duration_ns = _duration(overall_start, _clock_value(clock_ns))
    disk = inspect_workspace_disk_usage(loaded.root)
    rss = reader()
    _validate_rss_snapshot(rss)

    if doctor.overall_status != "pass":
        raise LiteClientMeasurementError("Lite measurement doctor check did not pass")
    if read_only_status.read_only is not True:
        raise LiteClientMeasurementError("Lite measurement state read-only check failed")
    if initialized_status.schema_version != read_only_status.schema_version:
        raise LiteClientMeasurementError("Lite measurement state schema changed unexpectedly")
    if initialized_status.state_revision != read_only_status.state_revision:
        raise LiteClientMeasurementError("Lite measurement state revision changed unexpectedly")
    if initialized_status.record_count != read_only_status.record_count:
        raise LiteClientMeasurementError("Lite measurement record count changed unexpectedly")

    return LiteClientResourceMeasurement(
        operating_system=platform.system(),
        architecture=platform.machine(),
        python_version=platform.python_version(),
        steps=tuple(steps),
        total_duration_ns=total_duration_ns,
        process_rss=rss,
        workspace_disk=disk,
        doctor_overall_status=doctor.overall_status,
        state_schema_version=read_only_status.schema_version,
        state_revision=read_only_status.state_revision,
        state_record_count=read_only_status.record_count,
    )


def inspect_workspace_disk_usage(root: Path) -> WorkspaceDiskUsage:
    """Count regular workspace bytes without following links or escaping the selected root."""

    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise LiteClientMeasurementError("Lite measurement workspace root is invalid")
    try:
        canonical_root = root.resolve(strict=True)
    except OSError as exc:
        raise LiteClientMeasurementError("Lite measurement workspace root is unavailable") from exc

    total_bytes = 0
    file_count = 0
    directory_count = 1
    entry_count = 0
    pending: list[tuple[Path, int]] = [(canonical_root, 0)]

    while pending:
        directory, depth = pending.pop()
        if depth > _MAX_WORKSPACE_DEPTH:
            raise LiteClientMeasurementError("Lite measurement workspace exceeds depth limit")
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entry_count += 1
                    if entry_count > _MAX_WORKSPACE_ENTRIES:
                        raise LiteClientMeasurementError(
                            "Lite measurement workspace exceeds entry limit"
                        )
                    if entry.is_symlink():
                        raise LiteClientMeasurementError(
                            "Lite measurement workspace contains a symbolic link"
                        )
                    entry_path = Path(entry.path)
                    try:
                        resolved = entry_path.resolve(strict=True)
                        resolved.relative_to(canonical_root)
                    except (OSError, ValueError) as exc:
                        raise LiteClientMeasurementError(
                            "Lite measurement workspace entry escaped the selected root"
                        ) from exc
                    if entry.is_dir(follow_symlinks=False):
                        directory_count += 1
                        pending.append((resolved, depth + 1))
                    elif entry.is_file(follow_symlinks=False):
                        try:
                            size = entry.stat(follow_symlinks=False).st_size
                        except OSError as exc:
                            raise LiteClientMeasurementError(
                                "Lite measurement workspace file is unreadable"
                            ) from exc
                        if size < 0:
                            raise LiteClientMeasurementError(
                                "Lite measurement workspace file size is invalid"
                            )
                        total_bytes += size
                        file_count += 1
                    else:
                        raise LiteClientMeasurementError(
                            "Lite measurement workspace contains an unsupported entry"
                        )
        except LiteClientMeasurementError:
            raise
        except OSError as exc:
            raise LiteClientMeasurementError(
                "Lite measurement workspace could not be traversed"
            ) from exc

    return WorkspaceDiskUsage(
        total_bytes=total_bytes,
        file_count=file_count,
        directory_count=directory_count,
    )


def read_process_rss() -> ProcessRssSnapshot:
    """Read doll-process RSS through bounded standard-library platform adapters."""

    if os.name == "nt":
        current, peak = _windows_process_rss()
        return ProcessRssSnapshot(
            source=("windows-process-memory-counters" if peak is not None else "unavailable"),
            current_bytes=current,
            peak_bytes=peak,
        )
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        raw_peak = int(usage.ru_maxrss)
    except (ImportError, OSError, ValueError):
        return ProcessRssSnapshot(
            source="unavailable",
            current_bytes=None,
            peak_bytes=None,
        )
    if raw_peak < 0:
        raise LiteClientMeasurementError("Lite measurement peak RSS is invalid")
    peak_bytes = raw_peak if sys.platform == "darwin" else raw_peak * 1024
    current_bytes = _linux_current_rss_bytes() if sys.platform.startswith("linux") else None
    return ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=current_bytes,
        peak_bytes=peak_bytes,
    )


def _linux_current_rss_bytes() -> int | None:
    try:
        parts = Path("/proc/self/statm").read_text(encoding="ascii").split()
        if len(parts) < 2:
            return None
        resident_pages = int(parts[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, TypeError):
        return None
    if resident_pages < 0 or not isinstance(page_size, int) or page_size <= 0:
        return None
    return resident_pages * page_size


def _windows_process_rss() -> tuple[int | None, int | None]:
    try:
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return None, None
        kernel32 = cast(Any, win_dll("kernel32", use_last_error=True))
        psapi = cast(Any, win_dll("psapi", use_last_error=True))

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        handle = get_current_process()
        if not get_process_memory_info(handle, ctypes.byref(counters), counters.cb):
            return None, None
        current = int(counters.WorkingSetSize)
        peak = int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError, TypeError, ValueError):
        return None, None
    if current < 0 or peak < 0:
        return None, None
    return current, peak


def _clock_value(clock_ns: Callable[[], int]) -> int:
    value = clock_ns()
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LiteClientMeasurementError("Lite measurement monotonic clock is invalid")
    return value


def _duration(start: int, end: int) -> int:
    if end < start:
        raise LiteClientMeasurementError("Lite measurement monotonic clock moved backwards")
    return end - start


def _step(step_id: str, start: int, end: int) -> LiteClientMeasurementStep:
    return LiteClientMeasurementStep(step_id=step_id, duration_ns=_duration(start, end))


def _validate_rss_snapshot(snapshot: ProcessRssSnapshot) -> None:
    if not isinstance(snapshot, ProcessRssSnapshot):
        raise LiteClientMeasurementError("Lite measurement RSS snapshot is invalid")
    for value in (snapshot.current_bytes, snapshot.peak_bytes):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise LiteClientMeasurementError("Lite measurement RSS value is invalid")
    if (
        snapshot.current_bytes is not None
        and snapshot.peak_bytes is not None
        and snapshot.current_bytes > snapshot.peak_bytes
    ):
        raise LiteClientMeasurementError("Lite measurement RSS values are inconsistent")


__all__ = [
    "LITE_CLIENT_MEASUREMENT_SCHEMA_VERSION",
    "LiteClientMeasurementError",
    "LiteClientMeasurementStep",
    "LiteClientResourceMeasurement",
    "ProcessRssSnapshot",
    "RssMeasurementSource",
    "WorkspaceDiskUsage",
    "inspect_workspace_disk_usage",
    "measure_lite_client_resources",
    "read_process_rss",
]
