from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    marker = "\n\ndef _validate_active_setting_identities(records: list[RecordEnvelope]) -> None:\n"
    if text.count(marker) != 1:
        raise RuntimeError("checkpoint package graph anchor mismatch")
    helper = '''

def _validate_checkpoint_package_graph(
    records: dict[str, RecordEnvelope],
) -> None:
    checkpoints = {
        record.id: _checkpoint_from_record(record)
        for record in records.values()
        if record.record_type == "project_checkpoint"
    }
    for checkpoint in checkpoints.values():
        basis_current = True
        for record_id, expected_revision in checkpoint.basis_record_revisions:
            linked = records.get(record_id)
            if linked is None or linked.revision != expected_revision:
                basis_current = False
                break
        if checkpoint.confirmation_state != "proposed" and not basis_current:
            continue
        _validate_current_checkpoint_package_links(records, checkpoint)


def _validate_current_checkpoint_package_links(
    records: dict[str, RecordEnvelope],
    checkpoint: ProjectCheckpointInfo,
) -> None:
    project = records.get(checkpoint.project_id)
    if project is None or project.record_type != "project" or project.status != "active":
        raise StatePackageValidationError("checkpoint requires an active project")
    expected_groups = (
        (checkpoint.active_work_item_ids, {"in_progress"}, None),
        (checkpoint.next_work_item_ids, {"ready"}, None),
        (checkpoint.blocked_work_item_ids, {"blocked"}, None),
        (checkpoint.completed_milestone_ids, {"completed"}, "milestone"),
    )
    for record_ids, statuses, expected_kind in expected_groups:
        for record_id in record_ids:
            record = records.get(record_id)
            if record is None or record.record_type != "work_item" or record.status != "active":
                raise StatePackageValidationError("checkpoint work-item link is invalid")
            item = _work_item_from_record(record)
            if item.project_id != checkpoint.project_id or item.work_status not in statuses:
                raise StatePackageValidationError("checkpoint work-item role is invalid")
            if expected_kind is not None and item.kind != expected_kind:
                raise StatePackageValidationError("checkpoint milestone link is invalid")
    for record_id in (
        *checkpoint.required_validation_ids,
        *checkpoint.basis_record_ids,
    ):
        record = records.get(record_id)
        if record is None or record.status != "active":
            raise StatePackageValidationError("checkpoint basis link is invalid")
'''
    PATH.write_text(text.replace(marker, helper + marker), encoding="utf-8")


if __name__ == "__main__":
    main()
