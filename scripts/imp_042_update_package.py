from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    path = ROOT / "src/doll/state_package.py"
    replace_once(
        path,
        "from doll.project_state import (\n",
        "from doll.procedure import ProcedureCorruptError, _procedure_from_record\n"
        "from doll.project_state import (\n",
    )
    replace_once(
        path,
        '    "work_item": _work_item_from_record,\n}',
        '    "work_item": _work_item_from_record,\n'
        '    "procedure": _procedure_from_record,\n'
        '}',
    )
    replace_once(
        path,
        '''        ProjectDecisionCorruptError,
        SettingsCorruptError,
''',
        '''        ProcedureCorruptError,
        ProjectDecisionCorruptError,
        SettingsCorruptError,
''',
    )
    replace_once(
        path,
        '''            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError(
                        "work-item source link is missing or inactive"
                    )
    _validate_work_item_package_graph(records)
''',
        '''            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError(
                        "work-item source link is missing or inactive"
                    )
        elif record.record_type == "procedure":
            _require_link_type(
                records,
                _metadata_string(metadata, "project_id"),
                "project",
            )
            for linked_id in _metadata_id_list(
                metadata,
                "verification_evidence_ids",
            ):
                _require_link_type(records, linked_id, "evidence")
            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError(
                        "procedure source link is missing or inactive"
                    )
            for key in ("supersedes_id", "superseded_by_id"):
                linked_id = _metadata_optional_id(metadata, key)
                if linked_id is not None:
                    _require_link_type(records, linked_id, "procedure")
    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
''',
    )
    replace_once(
        path,
        '''def _validate_active_setting_identities(records: list[RecordEnvelope]) -> None:
''',
        '''def _validate_procedure_package_graph(
    records: dict[str, RecordEnvelope],
) -> None:
    procedures = {
        record.id: _procedure_from_record(record)
        for record in records.values()
        if record.record_type == "procedure"
    }
    for procedure in procedures.values():
        project = records.get(procedure.project_id)
        if (
            project is None
            or project.record_type != "project"
            or project.status != "active"
        ):
            raise StatePackageValidationError(
                "procedure requires an active project"
            )
        if procedure.supersedes_id is not None:
            predecessor = procedures.get(procedure.supersedes_id)
            if (
                predecessor is None
                or predecessor.project_id != procedure.project_id
                or predecessor.version >= procedure.version
            ):
                raise StatePackageValidationError(
                    "procedure predecessor relation is invalid"
                )
        if procedure.superseded_by_id is not None:
            replacement = procedures.get(procedure.superseded_by_id)
            if (
                replacement is None
                or replacement.project_id != procedure.project_id
                or replacement.version <= procedure.version
                or replacement.supersedes_id != procedure.procedure_id
            ):
                raise StatePackageValidationError(
                    "procedure replacement relation is invalid"
                )


def _validate_active_setting_identities(records: list[RecordEnvelope]) -> None:
''',
    )


if __name__ == "__main__":
    main()
