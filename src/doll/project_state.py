"""Durable project and explicit decision records for Doll State."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.artifact import ArtifactError, WorkspaceFileService
from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.memory import ConfirmedMemoryError, ConfirmedMemoryService
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
from doll.state_repository import (
    StateRepository,
    _validate_record_fields,
)
from doll.state_repository import (
    _serialize_metadata as _serialize_record_metadata,
)

ProjectStatus = Literal["planned", "active", "on_hold", "completed", "cancelled"]
DecisionStatus = Literal["accepted", "superseded", "reversed"]
AuthorityActor = Literal["user", "model", "runtime", "capability", "system"]

_PROJECT_STATUSES = frozenset({"planned", "active", "on_hold", "completed", "cancelled"})
_DECISION_STATUSES = frozenset({"accepted", "superseded", "reversed"})
_ALLOWED_SENSITIVITY = frozenset({"public", "internal", "personal", "sensitive", "secret"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:[\\/]")

MAX_NAME_LENGTH = 240
MAX_DECISION_LENGTH = 1000
MAX_DESCRIPTION_LENGTH = 6000
MAX_REASON_LENGTH = 6000
MAX_LIST_ITEM_LENGTH = 1000
MAX_LIST_ITEMS = 100
MAX_LINKS = 100
MAX_LIST_LIMIT = 200


class ProjectDecisionError(StateError):
    """Base class for project and decision state failures."""


class ProjectDecisionValidationError(ProjectDecisionError):
    """Raised when project or decision values are invalid."""


class ForbiddenAuthorityMutationError(ProjectDecisionError):
    """Raised when a non-user path attempts an authoritative mutation."""


class ProjectDecisionExportError(ProjectDecisionError):
    """Raised when a project or decision cannot be exported safely."""


class ProjectDecisionCorruptError(ProjectDecisionError):
    """Raised when a stored project or decision record is malformed."""


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    project_id: str
    name: str
    description: str
    project_status: ProjectStatus
    started_at: str
    ended_at: str | None
    decision_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DecisionInfo:
    decision_id: str
    decision: str
    reason: str
    decision_status: DecisionStatus
    decided_at: str
    alternatives: tuple[str, ...]
    constraints: tuple[str, ...]
    review_after: str | None
    supersedes_id: str | None
    project_id: str | None
    memory_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ProjectService:
    repository: StateRepository

    def create(
        self,
        *,
        name: str,
        description: str,
        project_status: ProjectStatus,
        started_at: str,
        ended_at: str | None = None,
        decision_ids: Sequence[str] = (),
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> ProjectInfo:
        _require_user_actor(actor_type)
        metadata = _validated_project_values(
            self.repository,
            name=name,
            description=description,
            project_status=project_status,
            started_at=started_at,
            ended_at=ended_at,
            decision_ids=decision_ids,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
        )
        project_id = _create_record(
            self.repository,
            record_type="project",
            title=cast(str, metadata["name"]),
            metadata=metadata,
            provenance="user-created",
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="project.create",
        )
        return self.get(project_id)

    def update(
        self,
        project_id: str,
        *,
        expected_revision: int,
        name: str,
        description: str,
        project_status: ProjectStatus,
        started_at: str,
        ended_at: str | None = None,
        decision_ids: Sequence[str] = (),
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> ProjectInfo:
        _require_user_actor(actor_type)
        current_record = _require_record(self.repository, project_id, "project")
        current = _project_from_record(current_record)
        _require_active(current.lifecycle_status)
        metadata = _validated_project_values(
            self.repository,
            name=name,
            description=description,
            project_status=project_status,
            started_at=started_at,
            ended_at=ended_at,
            decision_ids=decision_ids,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
        )
        _update_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=cast(str, metadata["name"]),
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-created",
            operation_id=operation_id,
            action="project.update",
        )
        return self.get(project_id)

    def archive(
        self,
        project_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> ProjectInfo:
        _require_user_actor(actor_type)
        current_record = _require_record(self.repository, project_id, "project")
        current = _project_from_record(current_record)
        _require_active(current.lifecycle_status)
        _update_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=current.name,
            metadata=current_record.metadata,
            lifecycle_status="archived",
            provenance="user-created",
            operation_id=operation_id,
            action="project.archive",
        )
        return self.get(project_id)

    def get(self, project_id: str) -> ProjectInfo:
        return _project_from_record(_require_record(self.repository, project_id, "project"))

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[ProjectInfo, ...]:
        ids = _list_record_ids(
            self.repository,
            record_type="project",
            include_archived=include_archived,
            limit=limit,
        )
        return tuple(self.get(record_id) for record_id in ids)

    def export_json(self, project_id: str) -> str:
        project = self.get(project_id)
        _require_exportable(project.sensitivity)
        return _deterministic_json(
            {
                "export_schema": "doll.project.v1",
                "record": {
                    "id": project.project_id,
                    "record_type": "project",
                    "schema_version": 1,
                    "created_at": project.created_at,
                    "updated_at": project.updated_at,
                    "revision": project.revision,
                    "status": project.lifecycle_status,
                    "provenance": project.provenance,
                    "sensitivity": project.sensitivity,
                    "title": project.name,
                    "project": {
                        "name": project.name,
                        "description": project.description,
                        "status": project.project_status,
                        "started_at": project.started_at,
                        "ended_at": project.ended_at,
                        "decision_ids": list(project.decision_ids),
                        "memory_ids": list(project.memory_ids),
                        "artifact_ids": list(project.artifact_ids),
                    },
                },
            }
        )


@dataclass(slots=True)
class DecisionService:
    repository: StateRepository

    def create(
        self,
        *,
        decision: str,
        reason: str,
        decision_status: DecisionStatus,
        decided_at: str,
        alternatives: Sequence[str] = (),
        constraints: Sequence[str] = (),
        review_after: str | None = None,
        supersedes_id: str | None = None,
        project_id: str | None = None,
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> DecisionInfo:
        _require_user_actor(actor_type)
        metadata = _validated_decision_values(
            self.repository,
            decision=decision,
            reason=reason,
            decision_status=decision_status,
            decided_at=decided_at,
            alternatives=alternatives,
            constraints=constraints,
            review_after=review_after,
            supersedes_id=supersedes_id,
            project_id=project_id,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
            self_id=None,
        )
        decision_id = _create_record(
            self.repository,
            record_type="decision",
            title=cast(str, metadata["decision"]),
            metadata=metadata,
            provenance="user-confirmed",
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="decision.create",
        )
        return self.get(decision_id)

    def update(
        self,
        decision_id: str,
        *,
        expected_revision: int,
        decision: str,
        reason: str,
        decision_status: DecisionStatus,
        decided_at: str,
        alternatives: Sequence[str] = (),
        constraints: Sequence[str] = (),
        review_after: str | None = None,
        supersedes_id: str | None = None,
        project_id: str | None = None,
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> DecisionInfo:
        _require_user_actor(actor_type)
        current_record = _require_record(self.repository, decision_id, "decision")
        current = _decision_from_record(current_record)
        _require_active(current.lifecycle_status)
        metadata = _validated_decision_values(
            self.repository,
            decision=decision,
            reason=reason,
            decision_status=decision_status,
            decided_at=decided_at,
            alternatives=alternatives,
            constraints=constraints,
            review_after=review_after,
            supersedes_id=supersedes_id,
            project_id=project_id,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
            self_id=decision_id,
        )
        _update_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=cast(str, metadata["decision"]),
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="decision.update",
        )
        return self.get(decision_id)

    def archive(
        self,
        decision_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> DecisionInfo:
        _require_user_actor(actor_type)
        current_record = _require_record(self.repository, decision_id, "decision")
        current = _decision_from_record(current_record)
        _require_active(current.lifecycle_status)
        _update_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=current.decision,
            metadata=current_record.metadata,
            lifecycle_status="archived",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="decision.archive",
        )
        return self.get(decision_id)

    def get(self, decision_id: str) -> DecisionInfo:
        return _decision_from_record(_require_record(self.repository, decision_id, "decision"))

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[DecisionInfo, ...]:
        ids = _list_record_ids(
            self.repository,
            record_type="decision",
            include_archived=include_archived,
            limit=limit,
        )
        return tuple(self.get(record_id) for record_id in ids)

    def export_json(self, decision_id: str) -> str:
        decision = self.get(decision_id)
        _require_exportable(decision.sensitivity)
        return _deterministic_json(
            {
                "export_schema": "doll.decision.v1",
                "record": {
                    "id": decision.decision_id,
                    "record_type": "decision",
                    "schema_version": 1,
                    "created_at": decision.created_at,
                    "updated_at": decision.updated_at,
                    "revision": decision.revision,
                    "status": decision.lifecycle_status,
                    "provenance": decision.provenance,
                    "sensitivity": decision.sensitivity,
                    "title": decision.decision,
                    "decision": {
                        "decision": decision.decision,
                        "reason": decision.reason,
                        "status": decision.decision_status,
                        "decided_at": decision.decided_at,
                        "alternatives": list(decision.alternatives),
                        "constraints": list(decision.constraints),
                        "review_after": decision.review_after,
                        "supersedes_id": decision.supersedes_id,
                        "project_id": decision.project_id,
                        "memory_ids": list(decision.memory_ids),
                        "artifact_ids": list(decision.artifact_ids),
                    },
                },
            }
        )


def _validated_project_values(
    repository: StateRepository,
    *,
    name: str,
    description: str,
    project_status: ProjectStatus,
    started_at: str,
    ended_at: str | None,
    decision_ids: Sequence[str],
    memory_ids: Sequence[str],
    artifact_ids: Sequence[str],
) -> dict[str, object]:
    safe_name = _validate_text("project name", name, MAX_NAME_LENGTH)
    safe_description = _validate_text(
        "project description",
        description,
        MAX_DESCRIPTION_LENGTH,
    )
    safe_status = _validate_project_status(project_status)
    safe_started_at = _validate_utc("project started-at", started_at)
    safe_ended_at = _validate_optional_utc("project ended-at", ended_at)
    if safe_ended_at is not None:
        _require_later_or_equal(
            "project ended-at",
            safe_ended_at,
            safe_started_at,
        )

    safe_decisions = _validate_reference_ids("project decision IDs", decision_ids)
    safe_memories = _validate_reference_ids("project memory IDs", memory_ids)
    safe_artifacts = _validate_reference_ids("project artifact IDs", artifact_ids)
    _validate_typed_links(
        repository,
        decision_ids=safe_decisions,
        memory_ids=safe_memories,
        artifact_ids=safe_artifacts,
    )
    return {
        "name": safe_name,
        "description": safe_description,
        "status": safe_status,
        "started_at": safe_started_at,
        "ended_at": safe_ended_at,
        "decision_ids": list(safe_decisions),
        "memory_ids": list(safe_memories),
        "artifact_ids": list(safe_artifacts),
    }


def _validated_decision_values(
    repository: StateRepository,
    *,
    decision: str,
    reason: str,
    decision_status: DecisionStatus,
    decided_at: str,
    alternatives: Sequence[str],
    constraints: Sequence[str],
    review_after: str | None,
    supersedes_id: str | None,
    project_id: str | None,
    memory_ids: Sequence[str],
    artifact_ids: Sequence[str],
    self_id: str | None,
) -> dict[str, object]:
    safe_decision = _validate_text("decision", decision, MAX_DECISION_LENGTH)
    safe_reason = _validate_text("decision reason", reason, MAX_REASON_LENGTH)
    safe_status = _validate_decision_status(decision_status)
    safe_decided_at = _validate_utc("decision decided-at", decided_at)
    safe_review_after = _validate_optional_utc("decision review-after", review_after)
    if safe_review_after is not None:
        _require_later_or_equal(
            "decision review-after",
            safe_review_after,
            safe_decided_at,
        )

    safe_alternatives = _validate_text_items("decision alternatives", alternatives)
    safe_constraints = _validate_text_items("decision constraints", constraints)
    safe_supersedes_id = _validate_optional_reference_id(
        "decision supersedes ID",
        supersedes_id,
    )
    safe_project_id = _validate_optional_reference_id("decision project ID", project_id)
    safe_memories = _validate_reference_ids("decision memory IDs", memory_ids)
    safe_artifacts = _validate_reference_ids("decision artifact IDs", artifact_ids)

    if self_id is not None and safe_supersedes_id == self_id:
        raise ProjectDecisionValidationError("decision cannot supersede itself")

    _validate_typed_links(
        repository,
        project_id=safe_project_id,
        supersedes_id=safe_supersedes_id,
        memory_ids=safe_memories,
        artifact_ids=safe_artifacts,
    )
    return {
        "decision": safe_decision,
        "reason": safe_reason,
        "status": safe_status,
        "decided_at": safe_decided_at,
        "alternatives": list(safe_alternatives),
        "constraints": list(safe_constraints),
        "review_after": safe_review_after,
        "supersedes_id": safe_supersedes_id,
        "project_id": safe_project_id,
        "memory_ids": list(safe_memories),
        "artifact_ids": list(safe_artifacts),
    }


def _create_record(
    repository: StateRepository,
    *,
    record_type: Literal["project", "decision"],
    title: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    action: str,
) -> str:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type=record_type,
        schema_version=1,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    safe_operation_id = _validate_operation_id(operation_id)
    record_id = str(uuid4())
    now = _utc_now()
    connection = repository.connection

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at,
                revision, status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, ?, 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                record_type,
                now,
                now,
                provenance,
                sensitivity,
                title,
                _serialize_record_metadata(metadata),
            ),
        )
        _insert_audit(
            repository,
            operation_id=safe_operation_id,
            action=action,
            record_type=record_type,
            target_id=record_id,
            metadata=metadata,
            sensitivity=sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError(f"{record_type} record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    repository._sync_after_commit(state_revision)
    return record_id


def _update_record(
    repository: StateRepository,
    *,
    current_record: RecordEnvelope,
    expected_revision: int,
    title: str,
    metadata: dict[str, object],
    lifecycle_status: RecordStatus,
    provenance: RecordProvenance,
    operation_id: str | None,
    action: str,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    safe_operation_id = _validate_operation_id(operation_id)
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
            raise ProjectDecisionValidationError("archived authoritative record cannot be changed")
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
                title,
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
            operation_id=safe_operation_id,
            action=action,
            record_type=cast(Literal["project", "decision"], current_record.record_type),
            target_id=current_record.id,
            metadata=metadata,
            sensitivity=current_record.sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError(
            f"{current_record.record_type} record could not be updated"
        ) from exc
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
    record_type: Literal["project", "decision"],
    target_id: str,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
) -> None:
    audit_metadata: dict[str, object] = {
        "record_type": record_type,
        "domain_status": _required_string(metadata, "status"),
        "sensitivity": sensitivity,
        "memory_count": len(_metadata_list(metadata, "memory_ids")),
        "artifact_count": len(_metadata_list(metadata, "artifact_ids")),
    }
    if record_type == "project":
        audit_metadata["decision_count"] = len(_metadata_list(metadata, "decision_ids"))
        audit_metadata["has_ended_at"] = metadata.get("ended_at") is not None
    else:
        audit_metadata["has_project"] = metadata.get("project_id") is not None
        audit_metadata["has_supersedes"] = metadata.get("supersedes_id") is not None
        audit_metadata["has_review_after"] = metadata.get("review_after") is not None

    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, 'user', ?, ?, ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _validate_audit_token("action", action, 120),
            record_type,
            target_id,
            f"Changed authoritative {record_type} record",
            _serialize_audit_metadata(audit_metadata),
        ),
    )


def _project_from_record(record: RecordEnvelope) -> ProjectInfo:
    try:
        _validate_envelope(record, "project", "user-created")
        name = _validate_text(
            "project name",
            _required_string(record.metadata, "name"),
            MAX_NAME_LENGTH,
        )
        description = _validate_text(
            "project description",
            _required_string(record.metadata, "description"),
            MAX_DESCRIPTION_LENGTH,
        )
        if record.title != name:
            raise ProjectDecisionValidationError("project title and name are inconsistent")
        project_status = _validate_project_status(_required_string(record.metadata, "status"))
        started_at = _validate_utc(
            "project started-at",
            _required_string(record.metadata, "started_at"),
        )
        ended_at = _validate_optional_utc(
            "project ended-at",
            _optional_string(record.metadata, "ended_at"),
        )
        if ended_at is not None:
            _require_later_or_equal("project ended-at", ended_at, started_at)
        decision_ids = _metadata_reference_ids(record.metadata, "decision_ids")
        memory_ids = _metadata_reference_ids(record.metadata, "memory_ids")
        artifact_ids = _metadata_reference_ids(record.metadata, "artifact_ids")
    except (KeyError, TypeError, ValueError, ProjectDecisionValidationError) as exc:
        raise ProjectDecisionCorruptError("project record is malformed") from exc

    return ProjectInfo(
        project_id=record.id,
        name=name,
        description=description,
        project_status=project_status,
        started_at=started_at,
        ended_at=ended_at,
        decision_ids=decision_ids,
        memory_ids=memory_ids,
        artifact_ids=artifact_ids,
        revision=record.revision,
        lifecycle_status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _decision_from_record(record: RecordEnvelope) -> DecisionInfo:
    try:
        _validate_envelope(record, "decision", "user-confirmed")
        decision = _validate_text(
            "decision",
            _required_string(record.metadata, "decision"),
            MAX_DECISION_LENGTH,
        )
        reason = _validate_text(
            "decision reason",
            _required_string(record.metadata, "reason"),
            MAX_REASON_LENGTH,
        )
        if record.title != decision:
            raise ProjectDecisionValidationError("decision title and content are inconsistent")
        decision_status = _validate_decision_status(_required_string(record.metadata, "status"))
        decided_at = _validate_utc(
            "decision decided-at",
            _required_string(record.metadata, "decided_at"),
        )
        alternatives = _metadata_text_items(record.metadata, "alternatives")
        constraints = _metadata_text_items(record.metadata, "constraints")
        review_after = _validate_optional_utc(
            "decision review-after",
            _optional_string(record.metadata, "review_after"),
        )
        if review_after is not None:
            _require_later_or_equal(
                "decision review-after",
                review_after,
                decided_at,
            )
        supersedes_id = _metadata_optional_reference_id(
            record.metadata,
            "supersedes_id",
        )
        project_id = _metadata_optional_reference_id(record.metadata, "project_id")
        memory_ids = _metadata_reference_ids(record.metadata, "memory_ids")
        artifact_ids = _metadata_reference_ids(record.metadata, "artifact_ids")
        if supersedes_id == record.id:
            raise ProjectDecisionValidationError("decision cannot supersede itself")
    except (KeyError, TypeError, ValueError, ProjectDecisionValidationError) as exc:
        raise ProjectDecisionCorruptError("decision record is malformed") from exc

    return DecisionInfo(
        decision_id=record.id,
        decision=decision,
        reason=reason,
        decision_status=decision_status,
        decided_at=decided_at,
        alternatives=alternatives,
        constraints=constraints,
        review_after=review_after,
        supersedes_id=supersedes_id,
        project_id=project_id,
        memory_ids=memory_ids,
        artifact_ids=artifact_ids,
        revision=record.revision,
        lifecycle_status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_envelope(
    record: RecordEnvelope,
    record_type: Literal["project", "decision"],
    provenance: RecordProvenance,
) -> None:
    if record.record_type != record_type:
        raise ProjectDecisionValidationError("record type is inconsistent")
    if record.schema_version != 1:
        raise ProjectDecisionValidationError("record schema version is unsupported")
    if record.revision < 1:
        raise ProjectDecisionValidationError("record revision must be positive")
    if record.status not in {"active", "archived"}:
        raise ProjectDecisionValidationError("record lifecycle status is unsupported")
    if record.provenance != provenance:
        raise ProjectDecisionValidationError("record provenance is inconsistent")
    if record.sensitivity not in _ALLOWED_SENSITIVITY:
        raise ProjectDecisionValidationError("record sensitivity is unsupported")
    created_at = _validate_utc("record created-at", record.created_at)
    updated_at = _validate_utc("record updated-at", record.updated_at)
    _require_later_or_equal("record updated-at", updated_at, created_at)


def _validate_typed_links(
    repository: StateRepository,
    *,
    project_id: str | None = None,
    supersedes_id: str | None = None,
    decision_ids: Sequence[str] = (),
    memory_ids: Sequence[str] = (),
    artifact_ids: Sequence[str] = (),
) -> None:
    if project_id is not None:
        try:
            _project_from_record(_require_record(repository, project_id, "project"))
        except (KeyError, ProjectDecisionError) as exc:
            raise ProjectDecisionValidationError(
                "project link does not reference a valid project"
            ) from exc

    if supersedes_id is not None:
        try:
            _decision_from_record(_require_record(repository, supersedes_id, "decision"))
        except (KeyError, ProjectDecisionError) as exc:
            raise ProjectDecisionValidationError(
                "supersedes link does not reference a valid decision"
            ) from exc

    for decision_id in decision_ids:
        try:
            _decision_from_record(_require_record(repository, decision_id, "decision"))
        except (KeyError, ProjectDecisionError) as exc:
            raise ProjectDecisionValidationError("project decision link is invalid") from exc

    memory_service = ConfirmedMemoryService(repository)
    for memory_id in memory_ids:
        try:
            memory_service.get(memory_id)
        except (KeyError, ConfirmedMemoryError) as exc:
            raise ProjectDecisionValidationError(
                "memory link does not reference valid confirmed memory"
            ) from exc

    artifact_service = WorkspaceFileService(repository)
    for artifact_id in artifact_ids:
        try:
            artifact_service.get(artifact_id)
        except (KeyError, ArtifactError) as exc:
            raise ProjectDecisionValidationError(
                "artifact link does not reference a valid managed artifact"
            ) from exc


def _require_record(
    repository: StateRepository,
    record_id: str,
    record_type: Literal["project", "decision"],
) -> RecordEnvelope:
    record = repository.get_record(record_id)
    if record.record_type != record_type:
        raise KeyError(record_id)
    return record


def _list_record_ids(
    repository: StateRepository,
    *,
    record_type: Literal["project", "decision"],
    include_archived: bool,
    limit: int,
) -> tuple[str, ...]:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ProjectDecisionValidationError(f"list limit must be between 1 and {MAX_LIST_LIMIT}")
    status_clause = (
        "AND status IN ('active', 'archived')" if include_archived else "AND status = 'active'"
    )
    try:
        rows = repository.connection.execute(
            f"""
            SELECT id
            FROM records
            WHERE record_type = ? {status_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (record_type, limit),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StateCorruptError(f"{record_type} records are unreadable") from exc
    return tuple(cast(str, row[0]) for row in rows)


def _validate_text(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ProjectDecisionValidationError(f"{name} must be text")
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if not normalized or len(normalized) > maximum:
        raise ProjectDecisionValidationError(f"{name} is empty or too long")
    if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
        raise ProjectDecisionValidationError(f"{name} contains control characters")
    _reject_absolute_path(normalized)
    return normalized


def _validate_text_items(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ProjectDecisionValidationError(f"{name} must be a sequence")
    if len(values) > MAX_LIST_ITEMS:
        raise ProjectDecisionValidationError(f"{name} exceeds {MAX_LIST_ITEMS} entries")
    normalized = tuple(_validate_text(name, value, MAX_LIST_ITEM_LENGTH) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ProjectDecisionValidationError(f"{name} contains duplicates")
    return normalized


def _validate_project_status(value: str) -> ProjectStatus:
    if value not in _PROJECT_STATUSES:
        raise ProjectDecisionValidationError(f"invalid project status: {value}")
    return cast(ProjectStatus, value)


def _validate_decision_status(value: str) -> DecisionStatus:
    if value not in _DECISION_STATUSES:
        raise ProjectDecisionValidationError(f"invalid decision status: {value}")
    return cast(DecisionStatus, value)


def _validate_utc(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProjectDecisionValidationError(f"{name} must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProjectDecisionValidationError(f"{name} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ProjectDecisionValidationError(f"{name} must be UTC")
    return value


def _validate_optional_utc(name: str, value: str | None) -> str | None:
    return None if value is None else _validate_utc(name, value)


def _require_later_or_equal(name: str, later: str, earlier: str) -> None:
    later_value = datetime.fromisoformat(later[:-1] + "+00:00")
    earlier_value = datetime.fromisoformat(earlier[:-1] + "+00:00")
    if later_value < earlier_value:
        raise ProjectDecisionValidationError(f"{name} precedes its reference time")


def _validate_reference_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ProjectDecisionValidationError(f"{name} must be a sequence")
    if len(values) > MAX_LINKS:
        raise ProjectDecisionValidationError(f"{name} exceeds {MAX_LINKS} entries")
    normalized: list[str] = []
    for value in values:
        canonical = _validate_reference_id(name, value)
        if canonical in normalized:
            raise ProjectDecisionValidationError(f"{name} contains duplicate IDs")
        normalized.append(canonical)
    return tuple(normalized)


def _validate_reference_id(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProjectDecisionValidationError(f"{name} must contain text IDs")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ProjectDecisionValidationError(f"{name} contains an invalid record ID") from exc


def _validate_optional_reference_id(name: str, value: str | None) -> str | None:
    return None if value is None else _validate_reference_id(name, value)


def _validate_operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _require_user_actor(actor_type: AuthorityActor) -> None:
    if actor_type != "user":
        raise ForbiddenAuthorityMutationError(
            "authoritative project and decision mutation requires the user path"
        )


def _require_active(status: RecordStatus) -> None:
    if status != "active":
        raise ProjectDecisionValidationError("archived authoritative record cannot be changed")


def _require_exportable(sensitivity: RecordSensitivity) -> None:
    if sensitivity == "secret":
        raise ProjectDecisionExportError("secret records are excluded from normal export")


def _deterministic_json(payload: dict[str, object]) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )


def _reject_absolute_path(value: str) -> None:
    if "file://" in value or _POSIX_PATH_PATTERN.search(value):
        raise ProjectDecisionValidationError(
            "authoritative record must not contain an absolute local path"
        )
    if _WINDOWS_PATH_PATTERN.search(value):
        raise ProjectDecisionValidationError(
            "authoritative record must not contain an absolute local path"
        )


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ProjectDecisionValidationError(f"{key} is missing or invalid")
    return value


def _optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ProjectDecisionValidationError(f"{key} is invalid")
    return value


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise ProjectDecisionValidationError(f"{key} must be a list")
    return value


def _metadata_reference_ids(
    metadata: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    values = _metadata_list(metadata, key)
    return _validate_reference_ids(key, cast(list[str], values))


def _metadata_text_items(
    metadata: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    values = _metadata_list(metadata, key)
    return _validate_text_items(key, cast(list[str], values))


def _metadata_optional_reference_id(
    metadata: dict[str, object],
    key: str,
) -> str | None:
    return _validate_optional_reference_id(key, _optional_string(metadata, key))
