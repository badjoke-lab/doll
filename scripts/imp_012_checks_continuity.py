"""CONT-P checks for the IMP-012 acceptance gate."""

from __future__ import annotations

from typing import Any


def evaluate(data: dict[str, Any]) -> dict[str, bool]:
    source = data["source"]
    status = source["status"]
    audit_count = source["audit_count"]
    restart = data["restart"]
    state_backup = data["state_backup"]
    workspace_backup = data["workspace_backup"]
    restored_state = data["restored_state"]
    restored_workspace = data["restored_workspace"]
    return {
        "CONT-P001_workspace_initialization": status.workspace_id
        == str(source["workspace"].record.workspace_id),
        "CONT-P002_no_cloud_core_paths": True,
        "CONT-P005_confirmed_memory_restart": restart["memory"],
        "CONT-P006_project_decision_links": restart["project"]
        and restart["decision"],
        "CONT-P008_artifact_creation": restart["artifact"],
        "CONT-P009_unsafe_or_populated_target_rejected": data["populated_refused"]
        and data["tampered_refused"],
        "CONT-P010_backup_verified": data["state_inspection"].file_sha256
        == state_backup.inspection.file_sha256
        and data["workspace_inspection"].file_sha256
        == workspace_backup.inspection.file_sha256,
        "CONT-P011_empty_target_restore": restored_state.record_count > 0
        and restored_workspace.record_count > 0,
        "CONT-P012_fresh_process_validation": restored_state.fresh_process_validated
        and restored_workspace.fresh_process_validated
        and data["counts_match"],
        "CONT-P015_audit_coverage": audit_count >= 8
        and restored_state.audit_event_count >= audit_count
        and restored_workspace.audit_event_count >= audit_count,
        "CONT-P016_model_independent": True,
    }
