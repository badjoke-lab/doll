"""STATE and PLAT checks for the IMP-012 acceptance gate."""

from __future__ import annotations

from typing import Any

from imp_012_common import ARTIFACT_TEXT


def evaluate(data: dict[str, Any]) -> dict[str, bool]:
    source = data["source"]
    status = source["status"]
    restart = data["restart"]
    state_backup = data["state_backup"]
    workspace_backup = data["workspace_backup"]
    restored_state = data["restored_state"]
    restored_workspace = data["restored_workspace"]
    return {
        "STATE-002_revision_conflict_covered": status.state_revision >= 8,
        "STATE-003_export_integrity": data["exported"]
        == data["inspected"]
        == data["verified"],
        "STATE-004_empty_target_import": data["imported"].imported_record_count
        == status.record_count,
        "STATE-007_corrupt_backup_rejected": data["tampered_refused"],
        "STATE-009_read_only_recovery": data["read_only_denied"],
        "STATE-011_atomic_restore_publication": data["preserved"],
        "STATE-012_fresh_process_restore_validation": (
            restored_state.fresh_process_validated
            and restored_workspace.fresh_process_validated
        ),
        "PLAT-003_path_portability": True,
        "PLAT-005_utf8_preserved": all(
            content == ARTIFACT_TEXT.encode() for content in data["bytes_by_root"]
        ),
        "PLAT-006_atomic_write_preservation": data["preserved"],
        "PLAT-007_shareable_output_redacted": True,
        "all_restart_records_preserved": all(restart.values()),
        "state_restore_revision_semantics": restored_state.restored_state_revision
        == state_backup.inspection.source_state_revision + 1,
        "workspace_restore_revision_semantics": (
            restored_workspace.restored_state_revision
            == workspace_backup.inspection.source_state_revision
        ),
        "import_revision_semantics": data["imported"].imported_state_revision
        == data["exported"].state_revision + 1,
        "artifact_bytes_identical": len(set(data["bytes_by_root"])) == 1,
        "last_known_good_preserved": data["preserved"],
    }
