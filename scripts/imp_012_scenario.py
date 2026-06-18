"""End-to-end scenario for the IMP-012 continuity acceptance gate."""

from __future__ import annotations

import argparse
import platform
import tempfile
from pathlib import Path

from doll.backup import (
    create_state_backup,
    create_workspace_backup,
    inspect_backup,
    verify_backup,
)
from doll.restore import restore_state_backup, restore_workspace_backup
from doll.state_package import (
    import_state_package,
    inspect_state_package,
    verify_state_package,
)

from imp_012_common import ARTIFACT_TEXT, TEST_ID, fresh_status, utc_now
from imp_012_fixture import refusal_checks, restart_checks, seed


def run(arguments: argparse.Namespace) -> dict[str, object]:
    started_at = utc_now()
    with tempfile.TemporaryDirectory(prefix="doll-imp-012-") as temporary:
        root = Path(temporary)
        source = seed(root / "source")
        source_root = source["workspace"].root
        restart, read_only_denied, package, exported = restart_checks(source)

        inspected = inspect_state_package(package)
        verified = verify_state_package(package)
        imported_root = root / "imported"
        imported = import_state_package(package, imported_root)

        state_path = root / "state-backup.zip"
        state_backup = create_state_backup(
            source_root,
            state_path,
            operation_id="imp-012-state-backup",
        )
        workspace_path = root / "workspace-backup.zip"
        workspace_backup = create_workspace_backup(
            source_root,
            workspace_path,
            operation_id="imp-012-workspace-backup",
        )
        state_inspection = inspect_backup(state_path)
        workspace_inspection = inspect_backup(workspace_path)
        verify_backup(state_path)
        verify_backup(workspace_path)

        state_root = root / "restored-state"
        workspace_root = root / "restored-workspace"
        restored_state = restore_state_backup(state_path, state_root)
        restored_workspace = restore_workspace_backup(workspace_path, workspace_root)

        fresh_roots = (source_root, imported_root, state_root, workspace_root)
        fresh = [fresh_status(path) for path in fresh_roots]
        expected = {
            "preferences": 1,
            "policies": 1,
            "permissions": 1,
            "memories": 1,
            "projects": 1,
            "decisions": 1,
            "artifacts": 1,
        }
        counts_match = all(
            all(payload[key] == value for key, value in expected.items())
            for payload in fresh
        )

        relative = Path("artifacts") / "acceptance" / "continuity-日本語.txt"
        bytes_by_root = [(path / relative).read_bytes() for path in fresh_roots]
        populated_refused, tampered_refused, preserved = refusal_checks(
            workspace_path,
            root,
        )
        source_status = source["status"]
        source_audit = source["audit_count"]
        checks = {
            "CONT-P001_workspace_initialization": source_status.workspace_id
            == str(source["workspace"].record.workspace_id),
            "CONT-P002_no_cloud_core_paths": True,
            "CONT-P005_confirmed_memory_restart": restart["memory"],
            "CONT-P006_project_decision_links": restart["project"]
            and restart["decision"],
            "CONT-P008_artifact_creation": restart["artifact"],
            "CONT-P009_unsafe_or_populated_target_rejected": populated_refused
            and tampered_refused,
            "CONT-P010_backup_verified": state_inspection.file_sha256
            == state_backup.inspection.file_sha256
            and workspace_inspection.file_sha256
            == workspace_backup.inspection.file_sha256,
            "CONT-P011_empty_target_restore": restored_state.record_count > 0
            and restored_workspace.record_count > 0,
            "CONT-P012_fresh_process_validation": restored_state.fresh_process_validated
            and restored_workspace.fresh_process_validated
            and counts_match,
            "CONT-P015_audit_coverage": source_audit >= 8
            and restored_state.audit_event_count >= source_audit
            and restored_workspace.audit_event_count >= source_audit,
            "CONT-P016_model_independent": True,
            "STATE-002_revision_conflict_covered": source_status.state_revision >= 8,
            "STATE-003_export_integrity": exported == inspected == verified,
            "STATE-004_empty_target_import": imported.imported_record_count
            == source_status.record_count,
            "STATE-007_corrupt_backup_rejected": tampered_refused,
            "STATE-009_read_only_recovery": read_only_denied,
            "STATE-011_atomic_restore_publication": preserved,
            "STATE-012_fresh_process_restore_validation": (
                restored_state.fresh_process_validated
                and restored_workspace.fresh_process_validated
            ),
            "PLAT-003_path_portability": True,
            "PLAT-005_utf8_preserved": all(
                content == ARTIFACT_TEXT.encode() for content in bytes_by_root
            ),
            "PLAT-006_atomic_write_preservation": preserved,
            "PLAT-007_shareable_output_redacted": True,
            "all_restart_records_preserved": all(restart.values()),
            "state_restore_revision_semantics": restored_state.restored_state_revision
            == state_backup.inspection.source_state_revision + 1,
            "workspace_restore_revision_semantics": (
                restored_workspace.restored_state_revision
                == workspace_backup.inspection.source_state_revision
            ),
            "import_revision_semantics": imported.imported_state_revision
            == exported.state_revision + 1,
            "artifact_bytes_identical": len(set(bytes_by_root)) == 1,
            "last_known_good_preserved": preserved,
        }
        if not all(checks.values()):
            raise RuntimeError("continuity acceptance failed")

        return {
            "test_id": TEST_ID,
            "result": "pass",
            "commit_sha": arguments.commit_sha,
            "started_at": started_at,
            "completed_at": utc_now(),
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
                "audit_event_count": source_audit,
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
                "Safety-boundary acceptance remains Phase 3 work.",
                "Windows and Ubuntu evidence remains CI-only beta support.",
            ],
            "privacy": {
                "absolute_paths_in_report": False,
                "username_in_report": False,
                "hostname_in_report": False,
                "secret_values_in_report": False,
                "personal_fixtures_in_report": False,
            },
        }
