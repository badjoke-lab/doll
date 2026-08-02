from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import doctor as doctor_module
from doll.cli import app
from doll.doctor import DOCTOR_REPORT_SCHEMA_VERSION, run_doctor
from doll.state import initialize_state_repository
from doll.workspace import WORKSPACE_RECORD_NAME, initialize_workspace, load_workspace

runner = CliRunner()


def _workspace(tmp_path: Path) -> Path:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    return initialized.root


def _file_snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_healthy_workspace_passes_read_only_doctor_without_mutation(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    before = _file_snapshot(root)

    report = run_doctor(root)

    assert report.overall_status == "pass"
    assert report.passed is True
    assert report.read_only is True
    assert report.state_schema_version is not None
    assert report.state_revision == 0
    assert report.record_count == 0
    assert [check.check_id for check in report.checks] == [
        "workspace_identity",
        "workspace_directories",
        "state_repository",
        "state_read_only",
        "state_identity",
        "state_schema",
        "state_revision",
        "sqlite_quick_check",
    ]
    assert all(check.status == "pass" for check in report.checks)
    assert _file_snapshot(root) == before


def test_json_report_is_deterministic_content_free_and_machine_readable(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    workspace_identifier = str(load_workspace(root).record.workspace_id)

    first = run_doctor(root).to_dict()
    second = run_doctor(root).to_dict()
    encoded = json.dumps(first, ensure_ascii=False, sort_keys=True)

    assert first == second
    assert first["schema_version"] == DOCTOR_REPORT_SCHEMA_VERSION
    assert first["overall_status"] == "pass"
    assert str(root) not in encoded
    assert str(tmp_path) not in encoded
    assert workspace_identifier not in encoded
    assert "database_path" not in encoded


def test_cli_human_and_json_output_use_stable_exit_codes(tmp_path: Path) -> None:
    root = _workspace(tmp_path)

    human = runner.invoke(app, ["doctor", "--workspace", str(root)])
    machine = runner.invoke(app, ["doctor", "--workspace", str(root), "--json"])

    assert human.exit_code == 0
    assert "Doctor status: PASS" in human.stdout
    assert "[PASS] sqlite_quick_check" in human.stdout
    assert machine.exit_code == 0
    payload = json.loads(machine.stdout)
    assert payload["overall_status"] == "pass"
    assert payload["read_only"] is True
    assert str(root) not in machine.stdout


def test_invalid_workspace_fails_without_path_disclosure_or_creation(tmp_path: Path) -> None:
    target = tmp_path / "private-user-workspace"

    result = runner.invoke(app, ["doctor", "--workspace", str(target), "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "fail"
    assert payload["checks"][0]["check_id"] == "workspace_identity"
    assert str(target) not in result.stdout
    assert not target.exists()


def test_missing_required_directory_fails_closed(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    (root / "artifacts").rmdir()

    report = run_doctor(root)

    check = next(item for item in report.checks if item.check_id == "workspace_directories")
    assert report.overall_status == "fail"
    assert check.status == "fail"
    assert check.guidance


def test_symlinked_required_directory_is_rejected_when_supported(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts = root / "artifacts"
    artifacts.rmdir()
    try:
        artifacts.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this runner")

    report = run_doctor(root)

    check = next(item for item in report.checks if item.check_id == "workspace_directories")
    assert check.status == "fail"
    assert str(outside) not in json.dumps(report.to_dict(), sort_keys=True)


def test_corrupt_state_fails_without_repair(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    database = root / "state" / "doll-state.sqlite3"
    database.write_bytes(b"not a sqlite database")
    before = database.read_bytes()

    report = run_doctor(root)

    assert report.overall_status == "fail"
    assert report.checks[-1].check_id == "state_repository"
    assert report.checks[-1].status == "fail"
    assert database.read_bytes() == before


def test_revision_mismatch_fails_without_rewriting_workspace_record(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    record_path = root / WORKSPACE_RECORD_NAME
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["state_revision"] = 9
    record_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    before = record_path.read_bytes()

    report = run_doctor(root)

    assert report.overall_status == "fail"
    assert record_path.read_bytes() == before


def test_quick_check_failure_is_reported_without_automatic_action(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    root = _workspace(tmp_path)
    workspace = doctor_module.load_workspace(root)

    class FakeCursor:
        def fetchall(self) -> list[tuple[str]]:
            return [("integrity error",)]

    class FakeConnection:
        def execute(self, statement: str) -> FakeCursor:
            assert statement == "PRAGMA quick_check"
            return FakeCursor()

    class FakeRepository:
        connection = FakeConnection()

        def status(self) -> SimpleNamespace:
            return SimpleNamespace(
                workspace_id=str(workspace.record.workspace_id),
                schema_version=doctor_module.CURRENT_SCHEMA_VERSION,
                state_revision=workspace.record.state_revision,
                record_count=0,
                read_only=True,
            )

    @contextmanager
    def fake_open(*args: object, **kwargs: object) -> Iterator[FakeRepository]:
        assert kwargs == {"read_only": True}
        yield FakeRepository()

    monkeypatch.setattr(doctor_module, "open_state_repository", fake_open)

    report = run_doctor(root)

    check = next(item for item in report.checks if item.check_id == "sqlite_quick_check")
    assert report.overall_status == "fail"
    assert check.status == "fail"
    combined = " ".join(check.guidance).lower()
    assert "automatic" not in combined
    assert "cloud" not in combined
    assert "shell" not in combined


def test_doctor_report_repr_contains_no_workspace_path(tmp_path: Path) -> None:
    root = _workspace(tmp_path)

    report = run_doctor(root)

    assert str(root) not in repr(report)
    assert str(tmp_path) not in repr(report)
