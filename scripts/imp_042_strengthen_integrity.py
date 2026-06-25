from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"integrity anchor mismatch in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    procedure = ROOT / "src/doll/procedure.py"
    replace_once(
        procedure,
        '''        safe_verified_at = _optional_utc("procedure verified-at", verified_at)
        if safe_verified_at is None:
            raise ProcedureValidationError("procedure verified-at is required")
        safe_evidence = _reference_ids("verification evidence IDs", evidence_ids)
''',
        '''        safe_verified_at = _optional_utc("procedure verified-at", verified_at)
        if safe_verified_at is None:
            raise ProcedureValidationError("procedure verified-at is required")
        if (
            current.approved_at is None
            or _parse_utc(safe_verified_at) < _parse_utc(current.approved_at)
        ):
            raise ProcedureValidationError("procedure verification precedes approval")
        safe_evidence = _reference_ids("verification evidence IDs", evidence_ids)
''',
    )
    replace_once(
        procedure,
        '''    if last_verified_at is None and evidence_ids:
        raise ProcedureValidationError("verification evidence requires verified-at")
''',
        '''    if last_verified_at is None and evidence_ids:
        raise ProcedureValidationError("verification evidence requires verified-at")
    if (
        last_verified_at is not None
        and approved_at is not None
        and _parse_utc(last_verified_at) < _parse_utc(approved_at)
    ):
        raise ProcedureValidationError("procedure verification precedes approval")
''',
    )
    replace_once(
        procedure,
        '''        if relation == "predecessor" and linked.version >= version:
            raise ProcedureValidationError("procedure predecessor version must be lower")
        if relation == "replacement" and linked.version <= version:
            raise ProcedureValidationError("procedure replacement version must be higher")
''',
        '''        if relation == "predecessor":
            if linked.version >= version:
                raise ProcedureValidationError(
                    "procedure predecessor version must be lower"
                )
            if linked.procedure_status not in {"approved", "superseded"}:
                raise ProcedureValidationError(
                    "procedure predecessor is not accepted"
                )
            if (
                linked.procedure_status == "superseded"
                and linked.superseded_by_id != self_id
            ):
                raise ProcedureValidationError(
                    "procedure predecessor has another replacement"
                )
        if relation == "replacement":
            if linked.version <= version:
                raise ProcedureValidationError(
                    "procedure replacement version must be higher"
                )
            if linked.supersedes_id != self_id:
                raise ProcedureValidationError(
                    "procedure replacement is not reciprocal"
                )
''',
    )
    replace_once(
        procedure,
        '''def _operation_id(value: str | None) -> str:
''',
        '''def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _operation_id(value: str | None) -> str:
''',
    )

    state_package = ROOT / "src/doll/state_package.py"
    replace_once(
        state_package,
        '''                predecessor is None
                or predecessor.project_id != procedure.project_id
                or predecessor.version >= procedure.version
''',
        '''                predecessor is None
                or predecessor.project_id != procedure.project_id
                or predecessor.version >= procedure.version
                or predecessor.procedure_status not in {"approved", "superseded"}
                or (
                    predecessor.procedure_status == "superseded"
                    and predecessor.superseded_by_id != procedure.procedure_id
                )
''',
    )

    tests = ROOT / "tests/test_procedure_coverage.py"
    replace_once(
        tests,
        "from dataclasses import replace\n",
        "from collections.abc import Callable\nfrom dataclasses import replace\n",
    )
    replace_once(
        tests,
        "from doll.state import RecordProvenance, RecordStatus\n",
        "",
    )
    replace_once(
        tests,
        '            replace(record, status=cast(RecordStatus, "deleted")),\n',
        '            replace(record, status="deleted"),\n',
    )
    replace_once(
        tests,
        '                    provenance=cast(RecordProvenance, "model-proposed"),\n',
        '                    provenance="model-proposed",\n',
    )
    replace_once(
        tests,
        "    invalid_calls = (\n",
        "    invalid_calls: tuple[Callable[[], None], ...] = (\n",
    )
    replace_once(
        tests,
        '''        lambda: _validate_persisted_semantics(
            procedure_id,
            "approved",
            ("Step",),
            ("Validate",),
            ("Rollback",),
            (),
            None,
            (str(uuid4()),),
            None,
            None,
            "2026-06-25T01:00:00Z",
        ),
''',
        '''        lambda: _validate_persisted_semantics(
            procedure_id,
            "approved",
            ("Step",),
            ("Validate",),
            ("Rollback",),
            (),
            None,
            (str(uuid4()),),
            None,
            None,
            "2026-06-25T01:00:00Z",
        ),
        lambda: _validate_persisted_semantics(
            procedure_id,
            "approved",
            ("Step",),
            ("Validate",),
            ("Rollback",),
            (),
            "2026-06-25T00:00:00Z",
            (),
            None,
            None,
            "2026-06-25T01:00:00Z",
        ),
''',
    )


if __name__ == "__main__":
    main()
