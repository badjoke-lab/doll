"""Durable, inspectable procedures that never grant execution authority."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.project_state import ProjectDecisionCorruptError, _project_from_record
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StaleRevisionError,
    StateCorruptError,
    StateError,
    _utc_now,
)
from doll.state_repository import StateRepository, _validate_record_fields
from doll.state_repository import _serialize_metadata as _serialize_record_metadata
from doll.trust import TruthCorruptError, _evidence_from_record

ProcedureStatus = Literal["draft", "approved", "deprecated", "superseded"]
ProcedureActor = Literal["user", "model", "runtime", "importer", "system"]

PROCEDURE_SCHEMA_VERSION = 1
_PROCEDURE_STATUSES = frozenset({"draft", "approved", "deprecated", "superseded"})
_TRUSTED_PROVENANCE = frozenset({"user-created", "user-confirmed"})
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_POSIX_PATH = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]")

MAX_TITLE_LENGTH = 240
MAX_PURPOSE_LENGTH = 6000
MAX_ITEM_LENGTH = 2000
MAX_ITEMS = 200
MAX_LINKS = 100
MAX_LIST_LIMIT = 500


class ProcedureError(StateError):
    """Base class for ProcedureRecord failures."""


class ProcedureValidationError(ProcedureError):
    """Raised when a requested procedure value or transition is invalid."""


class ProcedureCorruptError(ProcedureError):
    """Raised when a persisted ProcedureRecord is malformed."""


@dataclass(frozen=True, slots=True)
class ProcedureInfo:
    procedure_id: str
    project_id: str
    title: str
    purpose: str
    procedure_status: ProcedureStatus
    version: int
    prerequisites: tuple[str, ...]
    ordered_steps: tuple[str, ...]
    required_capability_ids: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    validation_steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    platform_constraints: tuple[str, ...]
    source_ids: tuple[str, ...]
    last_verified_at: str | None
    verification_evidence_ids: tuple[str, ...]
    supersedes_id: str | None
    superseded_by_id: str | None
    approved_at: str | None
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ProcedureService:
    repository: StateRepository

    def create_draft(
        self,
        *,
        project_id: str,
        title: str,
        purpose: str,
        version: int,
        prerequisites: Sequence[str] = (),
        ordered_steps: Sequence[str] = (),
        required_capability_ids: Sequence[str] = (),
        expected_outputs: Sequence[str] = (),
        validation_steps: Sequence[str] = (),
        rollback_steps: Sequence[str] = (),
        platform_constraints: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        supersedes_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        record_id = str(uuid4())
        metadata = _validated_values(
            self.repository,
            self_id=record_id,
            project_id=project_id,
            title=title,
            purpose=purpose,
            procedure_status="draft",
            version=version,
            prerequisites=prerequisites,
            ordered_steps=ordered_steps,
            required_capability_ids=required_capability_ids,
            expected_outputs=expected_outputs,
            validation_steps=validation_steps,
            rollback_steps=rollback_steps,
            platform_constraints=platform_constraints,
            source_ids=source_ids,
            last_verified_at=None,
            verification_evidence_ids=(),
            supersedes_id=supersedes_id,
            superseded_by_id=None,
            approved_at=None,
        )
        _create_procedure(
            self.repository,
            record_id=record_id,
            metadata=metadata,
            provenance=_draft_provenance(actor_type),
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="procedure.create-draft",
            actor_type=actor_type,
        )
        return self.get(record_id)

    def create_approved(
        self,
        *,
        project_id: str,
        title: str,
        purpose: str,
        version: int,
        prerequisites: Sequence[str] = (),
        ordered_steps: Sequence[str],
        required_capability_ids: Sequence[str] = (),
        expected_outputs: Sequence[str] = (),
        validation_steps: Sequence[str],
        rollback_steps: Sequence[str],
        platform_constraints: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        supersedes_id: str | None = None,
        approved_at: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        record_id = str(uuid4())
        safe_approved_at = _optional_utc("procedure approved-at", approved_at) or _utc_now()
        metadata = _validated_values(
            self.repository,
            self_id=record_id,
            project_id=project_id,
            title=title,
            purpose=purpose,
            procedure_status="approved",
            version=version,
            prerequisites=prerequisites,
            ordered_steps=ordered_steps,
            required_capability_ids=required_capability_ids,
            expected_outputs=expected_outputs,
            validation_steps=validation_steps,
            rollback_steps=rollback_steps,
            platform_constraints=platform_constraints,
            source_ids=source_ids,
            last_verified_at=None,
            verification_evidence_ids=(),
            supersedes_id=supersedes_id,
            superseded_by_id=None,
            approved_at=safe_approved_at,
        )
        _require_approvable(metadata)
        _create_procedure(
            self.repository,
            record_id=record_id,
            metadata=metadata,
            provenance="user-created",
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="procedure.create-approved",
            actor_type="user",
        )
        return self.get(record_id)

    def get(self, procedure_id: str) -> ProcedureInfo:
        return _procedure_from_record(
            _require_record(self.repository, procedure_id),
            self.repository,
        )

    def list(
        self,
        *,
        project_id: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> tuple[ProcedureInfo, ...]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise ProcedureValidationError("procedure list limit is invalid")
        safe_project_id = _optional_uuid("project ID", project_id)
        rows = self.repository.connection.execute(
            "SELECT id FROM records WHERE record_type = 'procedure' ORDER BY created_at, id"
        ).fetchall()
        result: list[ProcedureInfo] = []
        for row in rows:
            procedure = self.get(cast(str, row[0]))
            if not include_archived and procedure.lifecycle_status != "active":
                continue
            if safe_project_id is not None and procedure.project_id != safe_project_id:
                continue
            result.append(procedure)
            if len(result) >= limit:
                break
        return tuple(result)

    def update_draft(
        self,
        procedure_id: str,
        *,
        expected_revision: int,
        title: str,
        purpose: str,
        version: int,
        prerequisites: Sequence[str] = (),
        ordered_steps: Sequence[str] = (),
        required_capability_ids: Sequence[str] = (),
        expected_outputs: Sequence[str] = (),
        validation_steps: Sequence[str] = (),
        rollback_steps: Sequence[str] = (),
        platform_constraints: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        supersedes_id: str | None = None,
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        if current.procedure_status != "draft":
            raise ProcedureValidationError("only draft procedures may be edited in place")
        metadata = _validated_values(
            self.repository,
            self_id=current.procedure_id,
            project_id=current.project_id,
            title=title,
            purpose=purpose,
            procedure_status="draft",
            version=version,
            prerequisites=prerequisites,
            ordered_steps=ordered_steps,
            required_capability_ids=required_capability_ids,
            expected_outputs=expected_outputs,
            validation_steps=validation_steps,
            rollback_steps=rollback_steps,
            platform_constraints=platform_constraints,
            source_ids=source_ids,
            last_verified_at=None,
            verification_evidence_ids=(),
            supersedes_id=supersedes_id,
            superseded_by_id=None,
            approved_at=None,
        )
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.update-draft",
        )
        return self.get(procedure_id)

    def approve(
        self,
        procedure_id: str,
        *,
        expected_revision: int,
        approved_at: str | None = None,
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        if current.procedure_status != "draft":
            raise ProcedureValidationError("only draft procedures may be approved")
        metadata = dict(current_record.metadata)
        metadata["status"] = "approved"
        metadata["approved_at"] = _optional_utc("procedure approved-at", approved_at) or _utc_now()
        _require_approvable(metadata)
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.approve",
        )
        return self.get(procedure_id)

    def verify(
        self,
        procedure_id: str,
        *,
        expected_revision: int,
        verified_at: str,
        evidence_ids: Sequence[str] = (),
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        if current.procedure_status != "approved":
            raise ProcedureValidationError("only approved procedures may be verified")
        safe_verified_at = _optional_utc("procedure verified-at", verified_at)
        if safe_verified_at is None:
            raise ProcedureValidationError("procedure verified-at is required")
        if current.approved_at is None or _parse_utc(safe_verified_at) < _parse_utc(
            current.approved_at
        ):
            raise ProcedureValidationError("procedure verification precedes approval")
        safe_evidence = _reference_ids("verification evidence IDs", evidence_ids)
        _validate_evidence_links(self.repository, safe_evidence)
        metadata = dict(current_record.metadata)
        metadata["last_verified_at"] = safe_verified_at
        metadata["verification_evidence_ids"] = list(safe_evidence)
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.verify",
        )
        return self.get(procedure_id)

    def deprecate(
        self,
        procedure_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        if current.procedure_status != "approved":
            raise ProcedureValidationError("only approved procedures may be deprecated")
        metadata = dict(current_record.metadata)
        metadata["status"] = "deprecated"
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.deprecate",
        )
        return self.get(procedure_id)

    def supersede(
        self,
        procedure_id: str,
        *,
        replacement_id: str,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        if current.procedure_status != "approved":
            raise ProcedureValidationError("only approved procedures may be superseded")
        replacement = self.get(replacement_id)
        if replacement.lifecycle_status != "active" or replacement.procedure_status != "approved":
            raise ProcedureValidationError("replacement procedure must be active and approved")
        if replacement.project_id != current.project_id:
            raise ProcedureValidationError("replacement procedure crosses project scope")
        if replacement.version <= current.version:
            raise ProcedureValidationError("replacement procedure version must increase")
        if replacement.supersedes_id != current.procedure_id:
            raise ProcedureValidationError(
                "replacement procedure does not identify its predecessor"
            )
        metadata = dict(current_record.metadata)
        metadata["status"] = "superseded"
        metadata["superseded_by_id"] = replacement.procedure_id
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.supersede",
        )
        return self.get(procedure_id)

    def archive(
        self,
        procedure_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: ProcedureActor = "user",
    ) -> ProcedureInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, procedure_id)
        current = _procedure_from_record(current_record, self.repository)
        _require_active(current)
        _update_procedure(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=current_record.metadata,
            lifecycle_status="archived",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="procedure.archive",
        )
        return self.get(procedure_id)

    def export_json(self, procedure_id: str) -> str:
        procedure = self.get(procedure_id)
        if procedure.sensitivity == "secret":
            raise ProcedureValidationError("secret procedures cannot use normal export")
        return _canonical_json(
            {
                "export_schema": "doll.procedure.v1",
                "record": _record_payload(_require_record(self.repository, procedure_id)),
            }
        )


def _validated_values(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    title: str,
    purpose: str,
    procedure_status: str,
    version: int,
    prerequisites: Sequence[str],
    ordered_steps: Sequence[str],
    required_capability_ids: Sequence[str],
    expected_outputs: Sequence[str],
    validation_steps: Sequence[str],
    rollback_steps: Sequence[str],
    platform_constraints: Sequence[str],
    source_ids: Sequence[str],
    last_verified_at: str | None,
    verification_evidence_ids: Sequence[str],
    supersedes_id: str | None,
    superseded_by_id: str | None,
    approved_at: str | None,
) -> dict[str, object]:
    safe_self_id = _uuid("procedure ID", self_id)
    safe_project_id = _uuid("procedure project ID", project_id)
    safe_title = _text("procedure title", title, MAX_TITLE_LENGTH)
    safe_purpose = _text("procedure purpose", purpose, MAX_PURPOSE_LENGTH)
    safe_status = _status(procedure_status)
    safe_version = _version(version)
    safe_prerequisites = _text_items("procedure prerequisites", prerequisites)
    safe_steps = _text_items("procedure ordered steps", ordered_steps)
    safe_capabilities = _tokens("required capability IDs", required_capability_ids)
    safe_outputs = _text_items("procedure expected outputs", expected_outputs)
    safe_validation = _text_items("procedure validation steps", validation_steps)
    safe_rollback = _text_items("procedure rollback steps", rollback_steps)
    safe_platforms = _text_items("procedure platform constraints", platform_constraints)
    safe_sources = _reference_ids("procedure source IDs", source_ids)
    safe_verified_at = _optional_utc("procedure verified-at", last_verified_at)
    safe_evidence = _reference_ids("verification evidence IDs", verification_evidence_ids)
    safe_supersedes = _optional_uuid("procedure supersedes ID", supersedes_id)
    safe_superseded_by = _optional_uuid("procedure replacement ID", superseded_by_id)
    safe_approved_at = _optional_utc("procedure approved-at", approved_at)
    if safe_self_id in safe_sources or safe_self_id in {safe_supersedes, safe_superseded_by}:
        raise ProcedureValidationError("procedure cannot link to itself")
    if safe_status == "draft" and (safe_approved_at is not None or safe_superseded_by is not None):
        raise ProcedureValidationError("draft procedure contains accepted lifecycle metadata")
    if safe_status in {"approved", "deprecated", "superseded"} and safe_approved_at is None:
        raise ProcedureValidationError("accepted procedure requires approved-at")
    if safe_status == "superseded" and safe_superseded_by is None:
        raise ProcedureValidationError("superseded procedure requires replacement link")
    if safe_status != "superseded" and safe_superseded_by is not None:
        raise ProcedureValidationError("replacement link requires superseded status")
    if safe_verified_at is None and safe_evidence:
        raise ProcedureValidationError("verification evidence requires verified-at")
    _validate_project_link(repository, safe_project_id)
    _validate_source_links(repository, safe_sources)
    _validate_evidence_links(repository, safe_evidence)
    _validate_procedure_links(
        repository,
        self_id=safe_self_id,
        project_id=safe_project_id,
        version=safe_version,
        supersedes_id=safe_supersedes,
        superseded_by_id=safe_superseded_by,
    )
    return {
        "project_id": safe_project_id,
        "title": safe_title,
        "purpose": safe_purpose,
        "status": safe_status,
        "version": safe_version,
        "prerequisites": list(safe_prerequisites),
        "ordered_steps": list(safe_steps),
        "required_capability_ids": list(safe_capabilities),
        "expected_outputs": list(safe_outputs),
        "validation_steps": list(safe_validation),
        "rollback_steps": list(safe_rollback),
        "platform_constraints": list(safe_platforms),
        "source_ids": list(safe_sources),
        "last_verified_at": safe_verified_at,
        "verification_evidence_ids": list(safe_evidence),
        "supersedes_id": safe_supersedes,
        "superseded_by_id": safe_superseded_by,
        "approved_at": safe_approved_at,
    }


def _procedure_from_record(
    record: RecordEnvelope,
    repository: StateRepository | None = None,
) -> ProcedureInfo:
    try:
        if record.record_type != "procedure" or record.schema_version != PROCEDURE_SCHEMA_VERSION:
            raise ProcedureValidationError("procedure envelope is unsupported")
        if record.status not in {"active", "archived"} or record.revision < 1:
            raise ProcedureValidationError("procedure envelope state is invalid")
        project_id = _uuid("procedure project ID", _required_string(record.metadata, "project_id"))
        title = _text(
            "procedure title", _required_string(record.metadata, "title"), MAX_TITLE_LENGTH
        )
        if record.title != title:
            raise ProcedureValidationError("procedure title is inconsistent")
        purpose = _text(
            "procedure purpose",
            _required_string(record.metadata, "purpose"),
            MAX_PURPOSE_LENGTH,
        )
        procedure_status = _status(_required_string(record.metadata, "status"))
        if procedure_status != "draft" and record.provenance not in _TRUSTED_PROVENANCE:
            raise ProcedureValidationError("accepted procedure requires trusted provenance")
        version = _version(record.metadata.get("version"))
        prerequisites = _metadata_text_items(record.metadata, "prerequisites")
        ordered_steps = _metadata_text_items(record.metadata, "ordered_steps")
        capabilities = _metadata_tokens(record.metadata, "required_capability_ids")
        expected_outputs = _metadata_text_items(record.metadata, "expected_outputs")
        validation_steps = _metadata_text_items(record.metadata, "validation_steps")
        rollback_steps = _metadata_text_items(record.metadata, "rollback_steps")
        platform_constraints = _metadata_text_items(record.metadata, "platform_constraints")
        source_ids = _metadata_ids(record.metadata, "source_ids")
        last_verified_at = _optional_utc(
            "procedure verified-at",
            record.metadata.get("last_verified_at"),
        )
        verification_evidence_ids = _metadata_ids(
            record.metadata,
            "verification_evidence_ids",
        )
        supersedes_id = _optional_uuid(
            "procedure supersedes ID", record.metadata.get("supersedes_id")
        )
        superseded_by_id = _optional_uuid(
            "procedure replacement ID",
            record.metadata.get("superseded_by_id"),
        )
        approved_at = _optional_utc("procedure approved-at", record.metadata.get("approved_at"))
        _validate_persisted_semantics(
            record.id,
            procedure_status,
            ordered_steps,
            validation_steps,
            rollback_steps,
            source_ids,
            last_verified_at,
            verification_evidence_ids,
            supersedes_id,
            superseded_by_id,
            approved_at,
        )
        if repository is not None:
            _validate_project_link(repository, project_id)
            _validate_source_links(repository, source_ids)
            _validate_evidence_links(repository, verification_evidence_ids)
            _validate_procedure_links(
                repository,
                self_id=record.id,
                project_id=project_id,
                version=version,
                supersedes_id=supersedes_id,
                superseded_by_id=superseded_by_id,
            )
    except (KeyError, TypeError, ValueError, ProcedureValidationError) as exc:
        raise ProcedureCorruptError("procedure record is malformed") from exc
    return ProcedureInfo(
        procedure_id=record.id,
        project_id=project_id,
        title=title,
        purpose=purpose,
        procedure_status=procedure_status,
        version=version,
        prerequisites=prerequisites,
        ordered_steps=ordered_steps,
        required_capability_ids=capabilities,
        expected_outputs=expected_outputs,
        validation_steps=validation_steps,
        rollback_steps=rollback_steps,
        platform_constraints=platform_constraints,
        source_ids=source_ids,
        last_verified_at=last_verified_at,
        verification_evidence_ids=verification_evidence_ids,
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
        approved_at=approved_at,
        revision=record.revision,
        lifecycle_status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_persisted_semantics(
    self_id: str,
    status: ProcedureStatus,
    ordered_steps: tuple[str, ...],
    validation_steps: tuple[str, ...],
    rollback_steps: tuple[str, ...],
    source_ids: tuple[str, ...],
    last_verified_at: str | None,
    evidence_ids: tuple[str, ...],
    supersedes_id: str | None,
    superseded_by_id: str | None,
    approved_at: str | None,
) -> None:
    if self_id in source_ids or self_id in {supersedes_id, superseded_by_id}:
        raise ProcedureValidationError("procedure relation contains self")
    if status == "draft" and (approved_at is not None or superseded_by_id is not None):
        raise ProcedureValidationError("draft procedure contains accepted metadata")
    if status in {"approved", "deprecated", "superseded"}:
        if approved_at is None:
            raise ProcedureValidationError("accepted procedure requires approved-at")
        if not ordered_steps or not validation_steps or not rollback_steps:
            raise ProcedureValidationError("accepted procedure is incomplete")
    if status == "superseded" and superseded_by_id is None:
        raise ProcedureValidationError("superseded procedure requires replacement")
    if status != "superseded" and superseded_by_id is not None:
        raise ProcedureValidationError("replacement link requires superseded status")
    if last_verified_at is None and evidence_ids:
        raise ProcedureValidationError("verification evidence requires verified-at")
    if (
        last_verified_at is not None
        and approved_at is not None
        and _parse_utc(last_verified_at) < _parse_utc(approved_at)
    ):
        raise ProcedureValidationError("procedure verification precedes approval")


def _require_approvable(metadata: dict[str, object]) -> None:
    for key in ("ordered_steps", "validation_steps", "rollback_steps"):
        value = metadata.get(key)
        if not isinstance(value, list) or not value:
            raise ProcedureValidationError(f"approved procedure requires {key}")


def _validate_project_link(repository: StateRepository, project_id: str) -> None:
    try:
        record = repository.get_record(project_id)
        if record.record_type != "project" or record.status != "active":
            raise ProcedureValidationError("procedure project link is invalid")
        _project_from_record(record, repository)
    except (KeyError, ProjectDecisionCorruptError, ProcedureValidationError) as exc:
        raise ProcedureValidationError("procedure requires a valid active project") from exc


def _validate_source_links(repository: StateRepository, source_ids: tuple[str, ...]) -> None:
    for source_id in source_ids:
        try:
            record = repository.get_record(source_id)
        except KeyError as exc:
            raise ProcedureValidationError("procedure source link is missing") from exc
        if record.status != "active" or record.sensitivity == "secret":
            raise ProcedureValidationError("procedure source link is not portable")


def _validate_evidence_links(repository: StateRepository, evidence_ids: tuple[str, ...]) -> None:
    for evidence_id in evidence_ids:
        try:
            record = repository.get_record(evidence_id)
            if record.record_type != "evidence" or record.status != "active":
                raise ProcedureValidationError("procedure evidence link is invalid")
            _evidence_from_record(record)
        except (KeyError, TruthCorruptError, ProcedureValidationError) as exc:
            raise ProcedureValidationError("procedure evidence link is invalid") from exc


def _validate_procedure_links(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    version: int,
    supersedes_id: str | None,
    superseded_by_id: str | None,
) -> None:
    for relation, linked_id in (
        ("predecessor", supersedes_id),
        ("replacement", superseded_by_id),
    ):
        if linked_id is None:
            continue
        try:
            linked = _procedure_from_record(repository.get_record(linked_id))
        except (KeyError, ProcedureCorruptError) as exc:
            raise ProcedureValidationError(f"procedure {relation} link is invalid") from exc
        if linked.project_id != project_id:
            raise ProcedureValidationError(f"procedure {relation} crosses project scope")
        if relation == "predecessor":
            if linked.version >= version:
                raise ProcedureValidationError("procedure predecessor version must be lower")
            if linked.procedure_status not in {"approved", "superseded"}:
                raise ProcedureValidationError("procedure predecessor is not accepted")
            if linked.procedure_status == "superseded" and linked.superseded_by_id != self_id:
                raise ProcedureValidationError("procedure predecessor has another replacement")
        if relation == "replacement":
            if linked.version <= version:
                raise ProcedureValidationError("procedure replacement version must be higher")
            if linked.supersedes_id != self_id:
                raise ProcedureValidationError("procedure replacement is not reciprocal")


def _create_procedure(
    repository: StateRepository,
    *,
    record_id: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    action: str,
    actor_type: ProcedureActor,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type="procedure",
        schema_version=PROCEDURE_SCHEMA_VERSION,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    connection = repository.connection
    now = _utc_now()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at,
                revision, status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, 'procedure', 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                now,
                now,
                provenance,
                sensitivity,
                cast(str, metadata["title"]),
                _serialize_record_metadata(metadata),
            ),
        )
        _insert_audit(
            repository,
            operation_id=_operation_id(operation_id),
            action=action,
            target_id=record_id,
            actor_type=actor_type,
            metadata=metadata,
            sensitivity=sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("procedure record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _update_procedure(
    repository: StateRepository,
    *,
    current_record: RecordEnvelope,
    expected_revision: int,
    metadata: dict[str, object],
    lifecycle_status: RecordStatus,
    provenance: RecordProvenance,
    operation_id: str | None,
    action: str,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    connection = repository.connection
    now = _utc_now()
    try:
        connection.execute("BEGIN IMMEDIATE")
        refreshed = repository.get_record(current_record.id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        if refreshed.status != "active":
            raise ProcedureValidationError("archived procedure cannot be changed")
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = ?,
                provenance = ?, title = ?, metadata_json = ?
            WHERE id = ? AND revision = ? AND status = 'active'
            """,
            (
                now,
                lifecycle_status,
                provenance,
                cast(str, metadata["title"]),
                _serialize_record_metadata(metadata),
                current_record.id,
                expected_revision,
            ),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("record revision changed during update")
        _insert_audit(
            repository,
            operation_id=_operation_id(operation_id),
            action=action,
            target_id=current_record.id,
            actor_type="user",
            metadata=metadata,
            sensitivity=current_record.sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("procedure record could not be updated") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _insert_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    action: str,
    target_id: str,
    actor_type: ProcedureActor,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
) -> None:
    audit_metadata = {
        "record_type": "procedure",
        "domain_status": _required_string(metadata, "status"),
        "version": cast(int, metadata["version"]),
        "sensitivity": sensitivity,
        "step_count": len(_metadata_list(metadata, "ordered_steps")),
        "capability_reference_count": len(_metadata_list(metadata, "required_capability_ids")),
    }
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'procedure', ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
            target_id,
            "Changed authoritative procedure record",
            _serialize_audit_metadata(audit_metadata),
        ),
    )


def _require_record(repository: StateRepository, procedure_id: str) -> RecordEnvelope:
    safe_id = _uuid("procedure ID", procedure_id)
    try:
        record = repository.get_record(safe_id)
    except KeyError as exc:
        raise ProcedureValidationError("procedure does not exist") from exc
    if record.record_type != "procedure":
        raise ProcedureValidationError("record is not a procedure")
    return record


def _require_active(procedure: ProcedureInfo) -> None:
    if procedure.lifecycle_status != "active":
        raise ProcedureValidationError("archived procedure cannot be changed")


def _require_user(actor_type: ProcedureActor) -> None:
    if actor_type != "user":
        raise ProcedureValidationError("accepted procedure mutation requires the user path")


def _audit_actor(actor_type: ProcedureActor) -> str:
    return "system" if actor_type == "importer" else actor_type


def _draft_provenance(actor_type: ProcedureActor) -> RecordProvenance:
    if actor_type == "user":
        return "user-created"
    if actor_type == "model":
        return "model-proposed"
    if actor_type == "importer":
        return "imported"
    return "system-generated"


def _status(value: object) -> ProcedureStatus:
    if not isinstance(value, str) or value not in _PROCEDURE_STATUSES:
        raise ProcedureValidationError("procedure status is invalid")
    return cast(ProcedureStatus, value)


def _version(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProcedureValidationError("procedure version must be a positive integer")
    return value


def _text(name: str, value: object, max_length: int) -> str:
    if not isinstance(value, str):
        raise ProcedureValidationError(f"{name} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        raise ProcedureValidationError(f"{name} length is invalid")
    if _POSIX_PATH.search(normalized) or _WINDOWS_PATH.search(normalized):
        raise ProcedureValidationError(f"{name} must not contain a local absolute path")
    return normalized


def _text_items(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_ITEMS:
        raise ProcedureValidationError(f"{name} are invalid")
    return tuple(_text(name, value, MAX_ITEM_LENGTH) for value in values)


def _tokens(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_ITEMS:
        raise ProcedureValidationError(f"{name} are invalid")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            raise ProcedureValidationError(f"{name} contain an invalid token")
        if value in result:
            raise ProcedureValidationError(f"{name} contain duplicates")
        result.append(value)
    return tuple(result)


def _reference_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_LINKS:
        raise ProcedureValidationError(f"{name} are invalid")
    result: list[str] = []
    for value in values:
        record_id = _uuid(name, value)
        if record_id in result:
            raise ProcedureValidationError(f"{name} contain duplicates")
        result.append(record_id)
    return tuple(result)


def _metadata_text_items(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ProcedureValidationError(f"{key} must be a text list")
    return _text_items(key, cast(list[str], value))


def _metadata_tokens(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ProcedureValidationError(f"{key} must be a token list")
    return _tokens(key, cast(list[str], value))


def _metadata_ids(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ProcedureValidationError(f"{key} must be an ID list")
    return _reference_ids(key, cast(list[str], value))


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise ProcedureValidationError(f"{key} must be a list")
    return value


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ProcedureValidationError(f"{key} is missing or invalid")
    return value


def _uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ProcedureValidationError(f"{name} is invalid")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ProcedureValidationError(f"{name} is invalid") from exc


def _optional_uuid(name: str, value: object) -> str | None:
    return None if value is None else _uuid(name, value)


def _optional_utc(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProcedureValidationError(f"{name} must use UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProcedureValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ProcedureValidationError(f"{name} must be UTC")
    return value


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _record_payload(record: RecordEnvelope) -> dict[str, object]:
    return {
        "id": record.id,
        "record_type": record.record_type,
        "schema_version": record.schema_version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "revision": record.revision,
        "status": record.status,
        "provenance": record.provenance,
        "sensitivity": record.sensitivity,
        "title": record.title,
        "metadata": record.metadata,
    }


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProcedureValidationError("procedure export is not strict JSON") from exc
