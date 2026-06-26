"""Run one fresh-process project-continuity acceptance scenario."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import cast

from tests.project_continuity_support import (
    assert_project_continuity,
    create_project_continuity_fixture,
    initialize_workspace,
)

import doll.backup as backup
import doll.restore as restore
import doll.state_package as package
from doll import state
from doll.checkpoint import ProjectCheckpointService
from doll.project_status import ProjectStatusService
from doll.resume_bundle import ResumeBundleService, verify_resume_bundle
from doll.state_repository import StateRepository

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "imp_047_bundle_inspector.py"


def _audit_count(repository: StateRepository) -> int:
    row = repository.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()
    return cast(int, row[0])


def _fresh_cli(workspace_root: Path, project_id: str, output: Path) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    status = subprocess.run(
        [
            sys.executable,
            "-m",
            "doll",
            "project",
            "status",
            project_id,
            "--json",
            "--workspace",
            str(workspace_root),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode or status.stderr:
        raise RuntimeError("fresh status failed")
    resume = subprocess.run(
        [
            sys.executable,
            "-m",
            "doll",
            "project",
            "resume",
            "export",
            project_id,
            "--output",
            str(output),
            "--workspace",
            str(workspace_root),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if resume.returncode or resume.stderr or not output.is_file():
        raise RuntimeError("fresh Resume Bundle failed")
    payload = json.loads(status.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("fresh status output is invalid")
    return cast(dict[str, object], payload)


def _independent_inspection(bundle: Path) -> dict[str, bool]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(INSPECTOR), str(bundle)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    checks = payload.get("checks")
    if result.returncode or payload.get("result") != "pass" or not isinstance(checks, dict):
        raise RuntimeError("independent inspection failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("independent inspection output is invalid")
    return cast(dict[str, bool], checks)


def run(root: Path) -> tuple[dict[str, bool], dict[str, object]]:
    source = initialize_workspace(root, "source")
    with state.open_state_repository(source.root) as repository:
        fixture = create_project_continuity_fixture(repository, include_secret=True)
        before_revision = repository.status().state_revision
        before_audits = _audit_count(repository)

    bundle_one = root / "resume-one.zip"
    bundle_two = root / "resume-two.zip"
    with state.open_state_repository(source.root, read_only=True) as repository:
        status_service = ProjectStatusService(repository)
        status_one = status_service.export_json(fixture.project_id)
        status_two = status_service.export_json(fixture.project_id)
        first = ResumeBundleService(repository).export(fixture.project_id, bundle_one)
        second = ResumeBundleService(repository).export(fixture.project_id, bundle_two)
        checkpoint = ProjectCheckpointService(repository).get(fixture.checkpoint_id)
        after_revision = repository.status().state_revision
        after_audits = _audit_count(repository)

    package_path = root / "state-package.zip"
    with state.open_state_repository(source.root, read_only=True) as repository:
        package_inspection = package.export_state_package(repository, package_path)
    package_target = root / "package-target"
    package.import_state_package(package_path, package_target)
    assert_project_continuity(
        package_target,
        fixture,
        root / "package-target-resume.zip",
    )

    backup_path = root / "state-backup.zip"
    backup.create_state_backup(source.root, backup_path)
    backup_target = root / "backup-target"
    restore_result = restore.restore_state_backup(backup_path, backup_target)
    assert_project_continuity(
        backup_target,
        fixture,
        root / "backup-target-resume.zip",
    )

    workspace_source = initialize_workspace(root, "workspace-source")
    with state.open_state_repository(workspace_source.root) as repository:
        workspace_fixture = create_project_continuity_fixture(
            repository,
            include_secret=False,
        )
    workspace_backup = root / "workspace-backup.zip"
    backup.create_workspace_backup(workspace_source.root, workspace_backup)
    workspace_target = root / "workspace-target"
    workspace_restore = restore.restore_workspace_backup(
        workspace_backup,
        workspace_target,
    )
    assert_project_continuity(
        workspace_target,
        workspace_fixture,
        root / "workspace-target-resume.zip",
    )

    fresh_output = root / "fresh-resume.zip"
    fresh_status = _fresh_cli(backup_target, fixture.project_id, fresh_output)
    independent = _independent_inspection(bundle_one)

    with zipfile.ZipFile(bundle_one, "r") as archive:
        combined = b"".join(archive.read(name) for name in archive.namelist())
    checks = {
        "project_status_deterministic": status_one == status_two,
        "resume_bundle_deterministic": bundle_one.read_bytes() == bundle_two.read_bytes(),
        "derived_views_read_only": before_revision == after_revision
        and before_audits == after_audits,
        "checkpoint_current": first.checkpoint_freshness == "current"
        and second.checkpoint_freshness == "current",
        "package_v2_verified": package_inspection.package_format_version == 2,
        "package_round_trip_current": verify_resume_bundle(
            root / "package-target-resume.zip"
        ).checkpoint_freshness
        == "current",
        "backup_restore_validated": restore_result.fresh_process_validated is True,
        "backup_round_trip_current": verify_resume_bundle(
            root / "backup-target-resume.zip"
        ).checkpoint_freshness
        == "current",
        "workspace_backup_restore_validated": workspace_restore.fresh_process_validated is True,
        "workspace_round_trip_current": verify_resume_bundle(
            root / "workspace-target-resume.zip"
        ).checkpoint_freshness
        == "current",
        "workspace_artifact_preserved": (
            workspace_target / "artifacts" / "continuity" / "evidence.txt"
        ).read_bytes()
        == b"project continuity artifact bytes\n",
        "fresh_process_status_current": isinstance(fresh_status.get("latest_checkpoint"), dict)
        and cast(dict[str, object], fresh_status["latest_checkpoint"]).get("freshness")
        == "current",
        "fresh_process_resume_valid": verify_resume_bundle(fresh_output).checkpoint_freshness
        == "current",
        "secret_record_omitted": package_inspection.omitted_secret_counts.get("work_item") == 1
        and b"PRIVATE IMP-046 MARKER" not in combined,
        "independent_bundle_inspection": all(independent.values()),
    }
    evidence: dict[str, object] = {
        "project_schema_version": 2,
        "project_status_schema": "doll.project-status.v1",
        "state_package_format_version": package_inspection.package_format_version,
        "resume_bundle_format_version": first.bundle_format_version,
        "checkpoint_freshness": first.checkpoint_freshness,
        "basis_fingerprint": checkpoint.basis_fingerprint,
        "record_counts": dict(sorted(package_inspection.record_counts.items())),
        "omitted_secret_counts": dict(sorted(package_inspection.omitted_secret_counts.items())),
        "independent_inspector_check_count": len(independent),
        "backup_modes": ["state", "workspace"],
    }
    return checks, evidence


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="doll-imp047-") as directory:
            checks, evidence = run(Path(directory))
        if not all(checks.values()):
            raise RuntimeError("project-continuity probe failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "evidence": evidence,
        }
    except BaseException as exc:
        payload = {"result": "fail", "error_class": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
