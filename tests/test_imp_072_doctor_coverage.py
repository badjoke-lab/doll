from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from doll import doctor as doctor_module
from doll.doctor import DoctorCheck, _report, run_doctor
from doll.state import initialize_state_repository, open_state_repository
from doll.state_db import _connect
from doll.workspace import initialize_workspace


def _workspace(tmp_path: Path) -> Path:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    return initialized.root


def test_pending_wal_fails_before_immutable_state_open(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    root = _workspace(tmp_path)
    database = root / "state" / "doll-state.sqlite3"
    Path(f"{database}-wal").write_bytes(b"pending")

    def unexpected_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("state open must not run while a WAL is pending")

    monkeypatch.setattr(doctor_module, "open_state_repository", unexpected_open)

    report = run_doctor(root)

    assert report.overall_status == "fail"
    assert report.checks[-1].check_id == "state_repository"
    assert "journal" in report.checks[-1].summary.lower()


def test_public_state_open_rejects_immutable_write_mode(tmp_path: Path) -> None:
    root = _workspace(tmp_path)

    with pytest.raises(ValueError, match="immutable state access"):
        open_state_repository(root, read_only=False, immutable=True)


def test_sqlite_connector_rejects_immutable_write_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="immutable SQLite access"):
        _connect(tmp_path / "state.sqlite3", read_only=False, immutable=True)


def test_warn_only_doctor_report_remains_non_blocking() -> None:
    report = _report(
        [
            DoctorCheck(
                check_id="advisory",
                status="warn",
                summary="A bounded advisory is present.",
            )
        ]
    )

    assert report.overall_status == "warn"
    assert report.passed is True
