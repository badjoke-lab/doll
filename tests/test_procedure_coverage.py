from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.procedure import (
    MAX_ITEMS,
    MAX_LINKS,
    MAX_LIST_LIMIT,
    ProcedureActor,
    ProcedureCorruptError,
    ProcedureService,
    ProcedureStatus,
    ProcedureValidationError,
    _audit_actor,
    _canonical_json,
    _draft_provenance,
    _metadata_ids,
    _metadata_list,
    _metadata_text_items,
    _metadata_tokens,
    _optional_utc,
    _optional_uuid,
    _procedure_from_record,
    _reference_ids,
    _require_approvable,
    _require_record,
    _required_string,
    _status,
    _text,
    _text_items,
    _tokens,
    _uuid,
    _validate_persisted_semantics,
    _version,
)
from doll.project_state import ProjectService
from doll.state import RecordProvenance, RecordStatus
from doll.state_repository import StateRepository


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str = "Project") -> str:
    return ProjectService(repository).create_v2(
        name=name,
        description="Procedure coverage project.",
        objective="Exercise ProcedureRecord defensive branches.",
        in_scope=("Procedure validation",),
        out_of_scope=("Procedure execution",),
        success_criteria=("Invalid state fails closed",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
    ).project_id


def _approved(
    service: ProcedureService,
    project_id: str,
    *,
    title: str = "Approved procedure",
    version: int = 1,
    supersedes_id: str | None = None,
    sensitivity: state.RecordSensitivity = "personal",
) -> object:
    return service.create_approved(
        project_id=project_id,
        title=title,
        purpose="Approved procedure coverage fixture.",
        version=version,
        ordered_steps=("Apply the bounded accepted step.",),
        validation_steps=("Validate the bounded result.",),
        rollback_steps=("Restore the prior accepted state.",),
        required_capability_ids=("workspace.read",),
        supersedes_id=supersedes_id,
        approved_at="2026-06-25T01:00:00Z",
        sensitivity=sensitivity,
    )


def _draft(
    service: ProcedureService,
    project_id: str,
    *,
    title: str = "Draft procedure",
    version: int = 1,
    actor_type: ProcedureActor = "user",
    supersedes_id: str | None = None,
) -> object:
    return service.create_draft(
        project_id=project_id,
        title=title,
        purpose="Draft procedure coverage fixture.",
        version=version,
        ordered_steps=("Inspect the draft step.",),
        validation_steps=("Validate the draft record.",),
        rollback_steps=("Discard the unaccepted draft.",),
        actor_type=actor_type,
        supersedes_id=supersedes_id,
    )


def test_list_filters_and_lifecycle_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = ProcedureService(repository)
        first = service.create_draft(
            project_id=first_project,
            title="First draft",
            purpose="First list fixture.",
            version=1,
        )
        second = service.create_approved(
            project_id=second_project,
            title="Second approved",
            purpose="Second list fixture.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        archived = service.archive(first.procedure_id, expected_revision=first.revision)

        assert service.list(project_id=first_project) == ()
        assert service.list(project_id=first_project, include_archived=True) == (archived,)
        assert service.list(project_id=second_project, limit=1) == (second,)
        for invalid_limit in (0, MAX_LIST_LIMIT + 1, True):
            with pytest.raises(ProcedureValidationError):
                service.list(limit=invalid_limit)
        with pytest.raises(ProcedureValidationError):
            service.list(project_id="invalid")
        with pytest.raises(ProcedureValidationError):
            service.archive(archived.procedure_id, expected_revision=archived.revision)
        with pytest.raises(ProcedureValidationError):
            service.update_draft(
                second.procedure_id,
                expected_revision=second.revision,
                title=second.title,
                purpose=second.purpose,
                version=second.version,
            )
        with pytest.raises(ProcedureValidationError):
            service.approve(second.procedure_id, expected_revision=second.revision)
        with pytest.raises(ProcedureValidationError):
            service.verify(
                archived.procedure_id,
                expected_revision=archived.revision,
                verified_at="2026-06-25T02:00:00Z",
            )
        with pytest.raises(ProcedureValidationError):
            service.deprecate(archived.procedure_id, expected_revision=archived.revision)


def test_trusted_actor_and_secret_export_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Actor draft",
            purpose="Actor guard fixture.",
            version=1,
        )
        actors: tuple[ProcedureActor, ...] = ("model", "runtime", "importer", "system")
        for actor in actors:
            with pytest.raises(ProcedureValidationError):
                service.update_draft(
                    draft.procedure_id,
                    expected_revision=draft.revision,
                    title=draft.title,
                    purpose=draft.purpose,
                    version=draft.version,
                    actor_type=actor,
                )
            with pytest.raises(ProcedureValidationError):
                service.approve(
                    draft.procedure_id,
                    expected_revision=draft.revision,
                    actor_type=actor,
                )
        with pytest.raises(ProcedureValidationError):
            service.create_approved(
                project_id=project_id,
                title="Rejected approved create",
                purpose="Non-user actor cannot create accepted procedure.",
                version=1,
                ordered_steps=("Step",),
                validation_steps=("Validate",),
                rollback_steps=("Rollback",),
                actor_type="model",
            )
        secret = service.create_approved(
            project_id=project_id,
            title="Secret procedure",
            purpose="Secret export guard.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
            sensitivity="secret",
        )
        with pytest.raises(ProcedureValidationError):
            service.export_json(secret.procedure_id)


def test_transition_guards_and_supersession_integrity(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = ProcedureService(repository)
        original = service.create_approved(
            project_id=first_project,
            title="Original",
            purpose="Original accepted method.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        replacement_draft = service.create_draft(
            project_id=first_project,
            title="Draft replacement",
            purpose="Unapproved replacement.",
            version=2,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
            supersedes_id=original.procedure_id,
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=replacement_draft.procedure_id,
                expected_revision=original.revision,
            )
        mismatch = service.create_approved(
            project_id=first_project,
            title="Mismatch replacement",
            purpose="Missing predecessor relation.",
            version=2,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=mismatch.procedure_id,
                expected_revision=original.revision,
            )
        cross = service.create_approved(
            project_id=second_project,
            title="Cross replacement",
            purpose="Cross-project relation.",
            version=2,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=cross.procedure_id,
                expected_revision=original.revision,
            )
        lower = service.create_approved(
            project_id=first_project,
            title="Lower replacement",
            purpose="Non-increasing version.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=lower.procedure_id,
                expected_revision=original.revision,
            )
        with pytest.raises(ProcedureValidationError):
            service.deprecate(replacement_draft.procedure_id, expected_revision=1)
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                replacement_draft.procedure_id,
                replacement_id=mismatch.procedure_id,
                expected_revision=1,
            )


def test_invalid_project_source_and_evidence_links(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        wrong = repository.create_record(record_type="other", metadata={})
        inactive = repository.create_record(record_type="source", metadata={})
        repository.update_record(inactive.id, expected_revision=1, status="archived")

        for invalid_project in (str(uuid4()), wrong.id):
            with pytest.raises(ProcedureValidationError):
                service.create_draft(
                    project_id=invalid_project,
                    title="Bad project",
                    purpose="Invalid parent.",
                    version=1,
                )
        for invalid_source in (str(uuid4()), inactive.id):
            with pytest.raises(ProcedureValidationError):
                service.create_draft(
                    project_id=project_id,
                    title="Bad source",
                    purpose="Invalid source.",
                    version=1,
                    source_ids=(invalid_source,),
                )
        approved = service.create_approved(
            project_id=project_id,
            title="Evidence target",
            purpose="Invalid evidence fixture.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
            approved_at="2026-06-25T02:00:00Z",
        )
        with pytest.raises(ProcedureValidationError):
            service.verify(
                approved.procedure_id,
                expected_revision=approved.revision,
                verified_at="2026-06-25T01:00:00Z",
            )
        for invalid_evidence in (str(uuid4()), wrong.id):
            with pytest.raises(ProcedureValidationError):
                service.verify(
                    approved.procedure_id,
                    expected_revision=approved.revision,
                    verified_at="2026-06-25T03:00:00Z",
                    evidence_ids=(invalid_evidence,),
                )


def test_malformed_envelopes_and_metadata_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        draft = ProcedureService(repository).create_draft(
            project_id=project_id,
            title="Malformed base",
            purpose="Malformed record fixture.",
            version=1,
        )
        record = repository.get_record(draft.procedure_id)

        invalid_envelopes = (
            replace(record, record_type="other"),
            replace(record, schema_version=2),
            replace(record, status=cast(RecordStatus, "deleted")),
            replace(record, revision=0),
            replace(record, title="different"),
        )
        for invalid in invalid_envelopes:
            with pytest.raises(ProcedureCorruptError):
                _procedure_from_record(invalid)

        mutations: tuple[tuple[str, object], ...] = (
            ("status", "approved"),
            ("status", "superseded"),
            ("superseded_by_id", str(uuid4())),
            ("verification_evidence_ids", [str(uuid4())]),
            ("source_ids", [record.id]),
            ("ordered_steps", "not-list"),
            ("required_capability_ids", ["bad token"]),
        )
        for key, value in mutations:
            metadata: dict[str, object] = dict(record.metadata)
            metadata[key] = value
            with pytest.raises(ProcedureCorruptError):
                _procedure_from_record(replace(record, metadata=metadata))

        accepted = dict(record.metadata)
        accepted["status"] = "approved"
        accepted["approved_at"] = "2026-06-25T01:00:00Z"
        accepted["ordered_steps"] = ["Step"]
        accepted["validation_steps"] = ["Validate"]
        accepted["rollback_steps"] = ["Rollback"]
        with pytest.raises(ProcedureCorruptError):
            _procedure_from_record(
                replace(
                    record,
                    metadata=accepted,
                    provenance=cast(RecordProvenance, "model-proposed"),
                )
            )


def test_validation_helper_defenses() -> None:
    for value in (None, "unknown", 1):
        with pytest.raises(ProcedureValidationError):
            _status(value)
    for value in (0, -1, True, "1"):
        with pytest.raises(ProcedureValidationError):
            _version(value)
    for value in (None, "", "/private/path", "C:/private/path"):
        with pytest.raises(ProcedureValidationError):
            _text("text", value, 20)
    with pytest.raises(ProcedureValidationError):
        _text("text", "x" * 21, 20)
    with pytest.raises(ProcedureValidationError):
        _text_items("items", cast(tuple[str, ...], "invalid"))
    with pytest.raises(ProcedureValidationError):
        _text_items("items", tuple("x" for _ in range(MAX_ITEMS + 1)))
    with pytest.raises(ProcedureValidationError):
        _tokens("tokens", cast(tuple[str, ...], "invalid"))
    with pytest.raises(ProcedureValidationError):
        _tokens("tokens", ("bad token",))
    with pytest.raises(ProcedureValidationError):
        _tokens("tokens", ("same", "same"))
    with pytest.raises(ProcedureValidationError):
        _reference_ids("IDs", cast(tuple[str, ...], "invalid"))
    with pytest.raises(ProcedureValidationError):
        _reference_ids("IDs", tuple(str(uuid4()) for _ in range(MAX_LINKS + 1)))
    identifier = str(uuid4())
    with pytest.raises(ProcedureValidationError):
        _reference_ids("IDs", (identifier, identifier))
    with pytest.raises(ProcedureValidationError):
        _metadata_text_items({"items": [1]}, "items")
    with pytest.raises(ProcedureValidationError):
        _metadata_tokens({"items": [1]}, "items")
    with pytest.raises(ProcedureValidationError):
        _metadata_ids({"items": [1]}, "items")
    with pytest.raises(ProcedureValidationError):
        _metadata_list({"items": "invalid"}, "items")
    with pytest.raises(ProcedureValidationError):
        _required_string({}, "missing")
    with pytest.raises(ProcedureValidationError):
        _uuid("ID", None)
    with pytest.raises(ProcedureValidationError):
        _uuid("ID", "invalid")
    assert _optional_uuid("ID", None) is None
    for value in (1, "not-utc", "badZ"):
        with pytest.raises(ProcedureValidationError):
            _optional_utc("time", value)
    assert _optional_utc("time", None) is None
    with pytest.raises(ProcedureValidationError):
        _canonical_json({"invalid": {1, 2}})
    assert _audit_actor("importer") == "system"
    assert _audit_actor("model") == "model"
    assert _draft_provenance("user") == "user-created"
    assert _draft_provenance("model") == "model-proposed"
    assert _draft_provenance("importer") == "imported"
    assert _draft_provenance("runtime") == "system-generated"
    with pytest.raises(ProcedureValidationError):
        _require_approvable({"ordered_steps": [], "validation_steps": [], "rollback_steps": []})


def test_persisted_semantic_guards() -> None:
    procedure_id = str(uuid4())
    replacement_id = str(uuid4())
    invalid_calls = (
        lambda: _validate_persisted_semantics(
            procedure_id,
            "draft",
            (),
            (),
            (),
            (),
            None,
            (),
            None,
            replacement_id,
            None,
        ),
        lambda: _validate_persisted_semantics(
            procedure_id,
            "approved",
            (),
            (),
            (),
            (),
            None,
            (),
            None,
            None,
            "2026-06-25T01:00:00Z",
        ),
        lambda: _validate_persisted_semantics(
            procedure_id,
            "superseded",
            ("Step",),
            ("Validate",),
            ("Rollback",),
            (),
            None,
            (),
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
            None,
            (str(uuid4()),),
            None,
            None,
            "2026-06-25T01:00:00Z",
        ),
    )
    for invalid_call in invalid_calls:
        with pytest.raises(ProcedureValidationError):
            invalid_call()


def test_record_lookup_and_read_only_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Read-only fixture",
            purpose="Read-only mutation fixture.",
            version=1,
        )
        wrong = repository.create_record(record_type="other", metadata={})
        assert _require_record(repository, draft.procedure_id).id == draft.procedure_id
        with pytest.raises(ProcedureValidationError):
            _require_record(repository, str(uuid4()))
        with pytest.raises(ProcedureValidationError):
            _require_record(repository, wrong.id)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ProcedureService(repository)
        with pytest.raises(state.ReadOnlyStateError):
            service.create_draft(
                project_id=project_id,
                title="Rejected create",
                purpose="Read-only repository.",
                version=1,
            )
        with pytest.raises(state.ReadOnlyStateError):
            service.update_draft(
                draft.procedure_id,
                expected_revision=draft.revision,
                title=draft.title,
                purpose=draft.purpose,
                version=draft.version,
            )
