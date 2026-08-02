"""Deterministic secret-safe read-only workspace diagnostics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from doll.state import CURRENT_SCHEMA_VERSION, StateError, open_state_repository
from doll.workspace import WORKSPACE_DIRECTORIES, WorkspaceError, load_workspace

DoctorCheckStatus = Literal["pass", "warn", "fail"]
DoctorOverallStatus = Literal["pass", "warn", "fail"]

DOCTOR_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One bounded diagnostic result with fixed local-only guidance."""

    check_id: str
    status: DoctorCheckStatus
    summary: str
    guidance: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "summary": self.summary,
            "guidance": list(self.guidance),
        }


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Content-free machine-readable result for one read-only doctor run."""

    overall_status: DoctorOverallStatus
    checks: tuple[DoctorCheck, ...]
    profile_preference: str | None = None
    state_schema_version: int | None = None
    state_revision: int | None = None
    record_count: int | None = None
    read_only: bool | None = None

    @property
    def passed(self) -> bool:
        return self.overall_status != "fail"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": DOCTOR_REPORT_SCHEMA_VERSION,
            "overall_status": self.overall_status,
            "profile_preference": self.profile_preference,
            "state_schema_version": self.state_schema_version,
            "state_revision": self.state_revision,
            "record_count": self.record_count,
            "read_only": self.read_only,
            "checks": [check.to_dict() for check in self.checks],
        }


def run_doctor(path: Path | None = None) -> DoctorReport:
    """Inspect one workspace without migration, repair, model execution, or writes."""

    checks: list[DoctorCheck] = []
    try:
        workspace = load_workspace(path)
    except (WorkspaceError, OSError):
        checks.append(
            DoctorCheck(
                check_id="workspace_identity",
                status="fail",
                summary="Workspace identity could not be validated.",
                guidance=(
                    "Select an initialized doll workspace.",
                    "Use a verified backup in an empty compatible target when the workspace identity cannot be recovered.",
                ),
            )
        )
        return _report(checks)

    checks.append(
        DoctorCheck(
            check_id="workspace_identity",
            status="pass",
            summary="Workspace identity is valid and supported.",
        )
    )

    unsafe_directories = tuple(
        name for name in WORKSPACE_DIRECTORIES if not _safe_workspace_directory(workspace.root, name)
    )
    if unsafe_directories:
        checks.append(
            DoctorCheck(
                check_id="workspace_directories",
                status="fail",
                summary="One or more required workspace directories are missing or unsafe.",
                guidance=(
                    "Do not follow or replace workspace directory links automatically.",
                    "Restore a verified workspace backup into an empty compatible target when required directories are unavailable.",
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                check_id="workspace_directories",
                status="pass",
                summary="Required workspace directories are present and confined.",
            )
        )

    try:
        with open_state_repository(workspace.root, read_only=True) as repository:
            status = repository.status()
            checks.append(
                DoctorCheck(
                    check_id="state_repository",
                    status="pass",
                    summary="Authoritative state opened successfully in read-only mode.",
                )
            )
            checks.append(
                _boolean_check(
                    check_id="state_read_only",
                    passed=status.read_only,
                    pass_summary="State repository is read-only.",
                    fail_summary="State repository did not report read-only mode.",
                    guidance=(
                        "Stop the diagnostic run and reopen the workspace through the read-only recovery path.",
                    ),
                )
            )
            checks.append(
                _boolean_check(
                    check_id="state_identity",
                    passed=status.workspace_id == str(workspace.record.workspace_id),
                    pass_summary="Workspace and database identities agree.",
                    fail_summary="Workspace and database identities do not agree.",
                    guidance=(
                        "Do not merge or overwrite mismatched workspace state.",
                        "Restore a verified matching backup into an empty compatible target.",
                    ),
                )
            )
            checks.append(
                _boolean_check(
                    check_id="state_schema",
                    passed=status.schema_version == CURRENT_SCHEMA_VERSION,
                    pass_summary="State schema matches the current supported version.",
                    fail_summary="State schema does not match the current supported version.",
                    guidance=(
                        "Use a compatible doll version or perform the documented migration outside doctor mode.",
                        "Keep the current workspace unchanged until compatibility is confirmed.",
                    ),
                )
            )
            checks.append(
                _boolean_check(
                    check_id="state_revision",
                    passed=status.state_revision == workspace.record.state_revision,
                    pass_summary="Workspace and database state revisions agree.",
                    fail_summary="Workspace and database state revisions do not agree.",
                    guidance=(
                        "Keep the workspace read-only and inspect the last verified backup.",
                        "Do not rewrite revision metadata manually.",
                    ),
                )
            )
            checks.append(_quick_check(repository.connection))
            return _report(
                checks,
                profile_preference=workspace.record.profile_preference,
                state_schema_version=status.schema_version,
                state_revision=status.state_revision,
                record_count=status.record_count,
                read_only=status.read_only,
            )
    except (StateError, sqlite3.DatabaseError, OSError):
        checks.append(
            DoctorCheck(
                check_id="state_repository",
                status="fail",
                summary="Authoritative state could not be opened safely in read-only mode.",
                guidance=(
                    "Keep the workspace unchanged and use the documented read-only recovery path.",
                    "Verify the most recent backup before attempting restore into an empty compatible target.",
                ),
            )
        )
        return _report(
            checks,
            profile_preference=workspace.record.profile_preference,
        )


def _safe_workspace_directory(root: Path, name: str) -> bool:
    candidate = root / name
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _quick_check(connection: sqlite3.Connection) -> DoctorCheck:
    try:
        rows = tuple(str(row[0]) for row in connection.execute("PRAGMA quick_check").fetchall())
    except sqlite3.DatabaseError:
        rows = ()
    if rows == ("ok",):
        return DoctorCheck(
            check_id="sqlite_quick_check",
            status="pass",
            summary="SQLite quick check passed.",
        )
    return DoctorCheck(
        check_id="sqlite_quick_check",
        status="fail",
        summary="SQLite quick check did not pass.",
        guidance=(
            "Keep the workspace read-only and preserve the current files for investigation.",
            "Verify a known-good backup before restoring into an empty compatible target.",
        ),
    )


def _boolean_check(
    *,
    check_id: str,
    passed: bool,
    pass_summary: str,
    fail_summary: str,
    guidance: tuple[str, ...],
) -> DoctorCheck:
    return DoctorCheck(
        check_id=check_id,
        status="pass" if passed else "fail",
        summary=pass_summary if passed else fail_summary,
        guidance=() if passed else guidance,
    )


def _report(
    checks: list[DoctorCheck],
    *,
    profile_preference: str | None = None,
    state_schema_version: int | None = None,
    state_revision: int | None = None,
    record_count: int | None = None,
    read_only: bool | None = None,
) -> DoctorReport:
    statuses = {check.status for check in checks}
    overall_status: DoctorOverallStatus
    if "fail" in statuses:
        overall_status = "fail"
    elif "warn" in statuses:
        overall_status = "warn"
    else:
        overall_status = "pass"
    return DoctorReport(
        overall_status=overall_status,
        checks=tuple(checks),
        profile_preference=profile_preference,
        state_schema_version=state_schema_version,
        state_revision=state_revision,
        record_count=record_count,
        read_only=read_only,
    )


__all__ = [
    "DOCTOR_REPORT_SCHEMA_VERSION",
    "DoctorCheck",
    "DoctorCheckStatus",
    "DoctorOverallStatus",
    "DoctorReport",
    "run_doctor",
]
