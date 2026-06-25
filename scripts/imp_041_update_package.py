from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def rep(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")

def main() -> None:
    path = ROOT / "src/doll/state_package.py"
    rep(path,
'''from doll.trust import (
    TruthCorruptError,
    _claim_from_record,
    _evidence_from_record,
    _inference_from_record,
    _trust_assessment_from_record,
)
''',
'''from doll.trust import (
    TruthCorruptError,
    _claim_from_record,
    _evidence_from_record,
    _inference_from_record,
    _trust_assessment_from_record,
)
from doll.work_item import WorkItemCorruptError, _work_item_from_record
''')
    rep(path, '    "backup_manifest": _backup_manifest_from_record,\n}', '    "backup_manifest": _backup_manifest_from_record,\n    "work_item": _work_item_from_record,\n}')
    rep(path, '        TruthCorruptError,\n    ) as exc:', '        TruthCorruptError,\n        WorkItemCorruptError,\n    ) as exc:')
    anchor = '''        elif record.record_type == "decision":
            project_id = _metadata_optional_id(metadata, "project_id")
            if project_id is not None:
                _require_link_type(records, project_id, "project")
            supersedes_id = _metadata_optional_id(metadata, "supersedes_id")
            if supersedes_id is not None:
                if supersedes_id == record.id:
                    raise StatePackageValidationError("decision cannot supersede itself")
                _require_link_type(records, supersedes_id, "decision")
            for linked_id in _metadata_id_list(metadata, "memory_ids"):
                _require_link_type(records, linked_id, "memory")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")


def _validate_active_setting_identities(records: list[RecordEnvelope]) -> None:
'''
    replacement = anchor.replace('\n\n\ndef _validate_active_setting_identities', '''
        elif record.record_type == "work_item":
            _require_link_type(records, _metadata_string(metadata, "project_id"), "project")
            for key in ("depends_on_ids", "blocked_by_ids"):
                for linked_id in _metadata_id_list(metadata, key):
                    _require_link_type(records, linked_id, "work_item")
            for linked_id in _metadata_id_list(metadata, "source_decision_ids"):
                _require_link_type(records, linked_id, "decision")
            for linked_id in _metadata_id_list(metadata, "verification_evidence_ids"):
                _require_link_type(records, linked_id, "evidence")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError("work-item source link is missing or inactive")
    _validate_work_item_package_graph(records)


def _validate_work_item_package_graph(records: dict[str, RecordEnvelope]) -> None:
    items = {
        record.id: _work_item_from_record(record)
        for record in records.values()
        if record.record_type == "work_item"
    }
    graph: dict[str, tuple[str, ...]] = {}
    for item in items.values():
        project = records.get(item.project_id)
        if project is None or project.record_type != "project" or project.status != "active":
            raise StatePackageValidationError("work item requires an active project")
        for linked_id in (*item.depends_on_ids, *item.blocked_by_ids):
            linked = items.get(linked_id)
            linked_record = records.get(linked_id)
            if linked is None or linked_record is None or linked_record.status != "active" or linked.project_id != item.project_id:
                raise StatePackageValidationError("work-item relation is invalid or crosses project scope")
        for blocker_id in item.blocked_by_ids:
            if items[blocker_id].work_status in {"completed", "cancelled"}:
                raise StatePackageValidationError("terminal work cannot be a current blocker")
        graph[item.work_item_id] = item.depends_on_ids
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            raise StatePackageValidationError("work-item dependency graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)


def _validate_active_setting_identities''')
    rep(path, anchor, replacement)

if __name__ == "__main__":
    main()
