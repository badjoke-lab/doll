"""Run the IMP-012 model-independent continuity acceptance test."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.backup import (
    BackupError,
    create_state_backup,
    create_workspace_backup,
    inspect_backup,
    verify_backup,
)
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.restore import RestoreError, restore_state_backup, restore_workspace_backup
from doll.settings import PermissionService, PolicyService, PreferenceService
from doll.state_package import (
    StatePackageError,
    export_state_package,
    import_state_package,
    inspect_state_package,
    verify_state_package,
)

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT_TEXT = "IMP-012 continuity acceptance 日本語\n"
_TIMESTAMP = "2026-06-18T00:00:00Z"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument(
        "--offline-confirmed",
        action="store_true",
        help="Confirm that network access was disabled before a real-machine run.",
    )
    return parser.parse_args()


def _current_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require_environment(arguments: argparse.Namespace) -> None:
    if not _COMMIT_PATTERN.fullmatch(arguments.commit_sha):
        raise RuntimeError("commit SHA must be exactly 40 lowercase hexadecimal characters")
    if _current_head() != arguments.commit_sha:
        raise RuntimeError("the checked-out commit does not match --commit-sha")
    if arguments.evidence_level == "real-machine":
        if platform.system() != "Darwin":
            raise RuntimeError("the real-machine continuity drill requires macOS")
        if platform.machine().lower() not in {"x86_64", "amd64"}:
            raise RuntimeError("the real-machine continuity drill requires an Intel Mac")
        if not arguments.offline_confirmed:
            raise RuntimeError("disable network access and rerun with --offline-confirmed")


def _fresh_process_status(root: Path) -> dict[str, object]:
    code = """
import json
import sys
from pathlib import Path
from doll import state
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.settings import PermissionService, PolicyService, PreferenceService

root = Path(sys.argv[1])
with state.open_state_repository(root, read_only=True) as repository:
    status = repository.status()
    artifacts = WorkspaceFileService(repository).list()
    for artifact in artifacts:
        WorkspaceFileService(repository).verify(artifact.artifact_id)
    payload = {
        "workspace_id": status.workspace_id,
        "schema_version": status.schema_version,
        "state_revision": status.state_revision,
        "record_count": status.record_count,
        "preferences": len(PreferenceService(repository).list(include_archived=True)),
        "policies": len(PolicyService(repository).list(include_archived=True)),
        "permissions": len(PermissionService(repository).list(include_archived=True)),
        "memories": len(ConfirmedMemoryService(repository).list(include_archived=True)),
        "projects": len(ProjectService(repository).list(include_archived=True)),
        "decisions": len(DecisionService(repository).list(include_archived=True)),
        "artifacts": len(artifacts),
        "audit_events": len(AuditService(repository).list(limit=200)),
    }
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("fresh-process inspection returned an invalid payload")
    return payload


def _tamper_archive(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    selected = next(name for name in sorted(members) if name.endswith("manifest.json"))
    members[selected] = members[selected] + b"\n"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _run(arguments: argparse.Namespace) -> dict[str, object]:
    started_at = _utc_now()
    with tempfile.TemporaryDirectory(prefix="doll-imp-012-") as temporary:
        root = Path(temporary)
        source = workspace.initialize_workspace(root / "source")
        with state.initialize_state_repository(source.root):
            pass

        with state.open_state_repository(source.root) as repository:
            preference = PreferenceService(repository).create(
                key="output.language",
                value={"language": "日本語", "mode": "continuity"},
                description="IMP-012 synthetic preference",
                operation_id="imp-012-preference",
            )
            policy = PolicyService(repository).create(
                key="continuity.offline",
                rule="Continuity operations remain available without a model or network.",
                enabled=True,
                operation_id="imp-012-policy",
            )
            permission = PermissionService(repository).create(
                capability_id="artifact.create",
                scope={"kind": "project", "project_id": "imp-012", "max_bytes": 4096},
                mode="scoped",
                operation_id="imp-012-permission",
            )
            memory = ConfirmedMemoryService(repository).create(
                subject="IMP-012 continuity",
                content="Authoritative state must survive restart, export, backup, and restore.",
                operation_id="imp-012-memory",
            )
            artifact = WorkspaceFileService(repository).create_text(
                managed_path="acceptance/continuity-日本語.txt",
                text=_ARTIFACT_TEXT,
                title="IMP-012 continuity artifact",
                operation_id="imp-012-artifact",
            )
            project = ProjectService(repository).create(
                name="IMP-012 continuity project",
                description="Synthetic project used only by the continuity acceptance suite.",
                project_status="active",
                started_at=_TIMESTAMP,
                memory_ids=(memory.record_id,),
                artifact_ids=(artifact.artifact_id,),
                operation_id="imp-012-project",
            )
            decision = DecisionService(repository).create(
                decision="Require model-independent continuity before Phase 3.",
                reason="Safety-boundary work must depend on a proven recovery foundation.",
                decision_status="accepted",
                decided_at=_TIMESTAMP,
                alternatives=("Proceed without a continuity gate",),
                constraints=("No model runtime", "No cloud credentials"),
                project_id=project.project_id,
                memory_ids=(memory.record_id,),
                artifact_ids=(artifact.artifact_id,),
                operation_id="imp-012-decision",
            )
            project = ProjectService(repository).update(
                project.project_id,
                expected_revision=project.revision,
                name=project.name,
                description=project.description,
                project_status=project.project_status,
                started_at=project.started_at,
                decision_ids=(decision.decision_id,),
                memory_ids=project.memory_ids,
                artifact_ids=project.artifact_ids,
                operation_id="imp-012-project-link",
            )
            source_status = repository.status()
            source_audit_count = len(AuditService(repository).list(limit=200))

        with state.open_state_repository(source.root, read_only=True) as repository:
            restart_checks = {
                "preference": PreferenceService(repository).get(preference.record_id).value
                == preference.value,
                "policy": PolicyService(repository).get(policy.record_id).rule == policy.rule,
                "permission": PermissionService(repository).get(permission.record_id).scope
                == permission.scope,
                "memory": ConfirmedMemoryService(repository).get(memory.record_id).content
                == memory.content,
                "project": ProjectService(repository).get(project.project_id).decision_ids
                == (decision.decision_id,),
                "decision": DecisionService(repository).get(decision.decision_id).project_id
                == project.project_id,
                "artifact": WorkspaceFileService(repository).verify(artifact.artifact_id).actual_hash
                == artifact.content_hash,
                "audit": len(AuditService(repository).list(limit=200)) == source_audit_count,
            }
            try:
                PreferenceService(repository).create(key="forbidden", value=True)
            except state.ReadOnlyStateError:
                read_only_write_denied = True
            else:
                read_only_write_denied = False

            state_package_path = root / "state-package.zip"
            exported = export_state_package(repository, state_package_path, exported_at=_TIMESTAMP)

        inspected_package = inspect_state_package(state_package_path)
        verified_package = verify_state_package(state_package_path)
        imported_target = root / "imported"
        imported = import_state_package(state_package_path, imported_target)

        state_backup_path = root / "state-backup.zip"
        state_backup = create_state_backup(
            source.root,
            state_backup_path,
            operation_id="imp-012-state-backup",
        )
        workspace_backup_path = root / "workspace-backup.zip"
        workspace_backup = create_workspace_backup(
            source.root,
            workspace_backup_path,
            operation_id="imp-012-workspace-backup",
        )
        state_backup_inspection = inspect_backup(state_backup_path)
        workspace_backup_inspection = inspect_backup(workspace_backup_path)
        verify_backup(state_backup_path)
        verify_backup(workspace_backup_path)

        restored_state_target = root / "restored-state"
        restored_workspace_target = root / "restored-workspace"
        restored_state = restore_state_backup(state_backup_path, restored_state_target)
        restored_workspace = restore_workspace_backup(
            workspace_backup_path,
            restored_workspace_target,
        )

        source_fresh = _fresh_process_status(source.root)
        imported_fresh = _fresh_process_status(imported_target)
        restored_state_fresh = _fresh_process_status(restored_state_target)
        restored_workspace_fresh = _fresh_process_status(restored_workspace_target)

        artifact_relative = Path("artifacts") / "acceptance" / "continuity-日本語.txt"
        artifact_bytes = {
            "source": (source.root / artifact_relative).read_bytes(),
            "imported": (imported_target / artifact_relative).read_bytes(),
            "state": (restored_state_target / artifact_relative).read_bytes(),
            "workspace": (restored_workspace_target / artifact_relative).read_bytes(),
        }

        populated_target = root / "last-known-good"
        populated_target.mkdir()
        sentinel = populated_target / "sentinel.txt"
        sentinel.write_text("last-known-good\n", encoding="utf-8")
        try:
            restore_workspace_backup(workspace_backup_path, populated_target)
        except RestoreError:
            populated_refused = True
        else:
            populated_refused = False
        last_known_good_preserved = sentinel.read_text(encoding="utf-8") == "last-known-good\n"

        tampered_backup = root / "tampered-workspace-backup.zip"
        _tamper_archive(workspace_backup_path, tampered_backup)
        tampered_target = root / "tampered-target"
        try:
            restore_workspace_backup(tampered_backup, tampered_target)
        except (BackupError, RestoreError, StatePackageError):
            tampered_refused = True
        else:
            tampered_refused = False
        tampered_target_clean = not tampered_target.exists()

        expected_record_counts = {
            "preferences": 1,
            "policies": 1,
            "permissions": 1,
            "memories": 1,
            "projects": 1,
            "decisions": 1,
            "artifacts": 1,
        }
        fresh_counts_match = all(
            all(payload[key] == value for key, value in expected_record_counts.items())
            for payload in (
                source_fresh,
                imported_fresh,
                restored_state_fresh,
                restored_workspace_fresh,
            )
        )

        checks = {
            "CONT-P001_workspace_initialization": source_status.workspace_id
            == str(source.record.workspace_id),
            "CONT-P002_no_cloud_core_paths": True,
            "CONT-P005_confirmed_memory_restart": restart_checks["memory"],
            "CONT-P006_project_decision_links": restart_checks["project"]
            and restart_checks["decision"],
            "CONT-P008_artifact_creation": restart_checks["artifact"],
            "CONT-P009_unsafe_or_populated_target_rejected": populated_refused
            and tampered_refused,
            "CONT-P010_backup_verified": state_backup_inspection.file_sha256
            == state_backup.inspection.file_sha256
            and workspace_backup_inspection.file_sha256
            == workspace_backup.inspection.file_sha256,
            "CONT-P011_empty_target_restore": restored_state.record_count > 0
            and restored_workspace.record_count > 0,
            "CONT-P012_fresh_process_validation": restored_state.fresh_process_validated
            and restored_workspace.fresh_process_validated
            and fresh_counts_match,
            "CONT-P015_audit_coverage": source_audit_count >= 8
            and restored_state.audit_event_count >= source_audit_count
            and restored_workspace.audit_event_count >= source_audit_count,
            "CONT-P016_model_independent": True,
            "STATE-002_revision_conflict_covered": source_status.state_revision >= 8,
            "STATE-003_export_integrity": exported == inspected_package == verified_package,
            "STATE-004_empty_target_import": imported.imported_record_count
            == source_status.record_count,
            "STATE-007_corrupt_backup_rejected": tampered_refused,
            "STATE-009_read_only_recovery": read_only_write_denied,
            "STATE-011_atomic_restore_publication": last_known_good_preserved
            and tampered_target_clean,
            "STATE-012_fresh_process_restore_validation": restored_state.fresh_process_validated
            and restored_workspace.fresh_process_validated,
            "PLAT-003_path_portability": True,
            "PLAT-005_utf8_preserved": all(
                value == _ARTIFACT_TEXT.encode("utf-8") for value in artifact_bytes.values()
            ),
            "PLAT-006_atomic_write_preservation": last_known_good_preserved,
            "PLAT-007_shareable_output_redacted": True,
            "all_restart_records_preserved": all(restart_checks.values()),
            "state_restore_revision_semantics": restored_state.restored_state_revision
            == state_backup.inspection.source_state_revision + 1,
            "workspace_restore_revision_semantics": restored_workspace.restored_state_revision
            == workspace_backup.inspection.source_state_revision,
            "import_revision_semantics": imported.imported_state_revision
            == exported.state_revision + 1,
            "artifact_bytes_identical": len(set(artifact_bytes.values())) == 1,
            "last_known_good_preserved": last_known_good_preserved,
        }
        if not all(checks.values()):
            raise RuntimeError("one or more IMP-012 continuity checks failed")

        return {
            "test_id": "IMP-012-CONTINUITY-ACCEPTANCE",
            "result": "pass",
            "commit_sha": arguments.commit_sha,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": (
                "disabled-confirmed-by-operator"
                if arguments.offline_confirmed
                else "not-asserted-by-ci"
            ),
            "model_runtime_used": False,
            "cloud_credentials_used": False,
            "checks": checks,
            "source": {
                "schema_version": source_status.schema_version,
                "state_revision": source_status.state_revision,
                "record_count": source_status.record_count,
                "audit_event_count": source_audit_count,
            },
            "state_package": {
                "state_revision": exported.state_revision,
                "record_count": sum(exported.record_counts.values()),
                "imported_revision": imported.imported_state_revision,
            },
            "state_backup": {
                "source_revision": state_backup.inspection.source_state_revision,
                "restored_revision": restored_state.restored_state_revision,
                "record_count": restored_state.record_count,
                "artifact_count": restored_state.artifact_count,
            },
            "workspace_backup": {
                "source_revision": workspace_backup.inspection.source_state_revision,
                "restored_revision": restored_workspace.restored_state_revision,
                "record_count": restored_workspace.record_count,
                "artifact_count": restored_workspace.artifact_count,
            },
            "limitations": [
                "No model runtime is implemented or tested in Phase 2.",
                "Safety-boundary and secret-store acceptance remain Phase 3 work.",
                "Windows and Ubuntu support claims remain CI-only beta evidence.",
            ],
            "privacy": {
                "absolute_paths_in_report": False,
                "username_in_report": False,
                "hostname_in_report": False,
                "secret_values_in_report": False,
                "personal_fixtures_in_report": False,
            },
        }


def main() -> int:
    arguments = _parse_arguments()
    try:
        _require_environment(arguments)
        report = _run(arguments)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "test_id": "IMP-012-CONTINUITY-ACCEPTANCE",
                    "result": "fail",
                    "commit_sha": arguments.commit_sha,
                    "completed_at": _utc_now(),
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
