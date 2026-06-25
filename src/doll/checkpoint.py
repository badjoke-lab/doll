"""Explicit project checkpoints with deterministic basis freshness."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
from doll.work_item import WorkItemCorruptError, WorkItemInfo, _work_item_from_record

CheckpointConfirmationState = Literal["proposed", "confirmed", "superseded"]
CheckpointFreshness = Literal["current", "stale", "superseded"]
CheckpointActor = Literal["user", "model", "runtime", "importer", "system"]

CHECKPOINT_SCHEMA_VERSION = 1
FINGERPRINT_FORMAT_VERSION = 1
_FINGERPRINT_PREFIX = "sha256:"
_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONFIRMATION_STATES = frozenset({"proposed", "confirmed", "superseded"})
_TRUSTED_PROVENANCE = frozenset({"user-created", "user-confirmed"})
_POSIX_PATH = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]")

MAX_SUMMARY_LENGTH = 8000
MAX_PHASE_LENGTH = 500
MAX_GOAL_LENGTH = 2000
MAX_LINKS = 300
MAX_LIST_LIMIT = 500


class CheckpointError(StateError):
    """Base class for ProjectCheckpointRecord failures."""


class CheckpointValidationError(CheckpointError):
    """Raised when a requested checkpoint value or transition is invalid."""


class CheckpointCorruptError(CheckpointError):
    """Raised when a persisted checkpoint is malformed."""


@dataclass(frozen=True, slots=True)
class ProjectCheckpointInfo:
    checkpoint_id: str
    project_id: str
    as_of: str
    summary: str
    current_phase: str
    current_goal: str
    active_work_item_ids: tuple[str, ...]
    next_work_item_ids: tuple[str, ...]
    blocked_work_item_ids: tuple[str, ...]
    completed_milestone_ids: tuple[str, ...]
    required_validation_ids: tuple[str, ...]
    basis_record_ids: tuple[str, ...]
    basis_record_revisions: tuple[tuple[str, int], ...]
    basis_fingerprint: str | None
    confirmation_state: CheckpointConfirmationState
    confirmed_by: Literal["user"] | None
    freshness: CheckpointFreshness | None
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ProjectCheckpointService:
    repository: StateRepository

    def propose(
        self,
        *,
        project_id: str,
        as_of: str,
        summary: str,
        current_phase: str,
        current_goal: str,
        active_work_item_ids: Sequence[str] = (),
        next_work_item_ids: Sequence[str] = (),
        blocked_work_item_ids: Sequence[str] = (),
        completed_milestone_ids: Sequence[str] = (),
        required_validation_ids: Sequence[str] = (),
        basis_record_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: CheckpointActor = "model",
    ) -> ProjectCheckpointInfo:
        """Create an unconfirmed checkpoint proposal from any accepted origin."""

        record_id = str(uuid4())
        metadata = _validated_checkpoint_values(
            self.repository,
            self_id=record_id,
            project_id=project_id,
            as_of=as_of,
            summary=summary,
            current_phase=current_phase,
            current_goal=current_goal,
            active_work_item_ids=active_work_item_ids,
            next_work_item_ids=next_work_item_ids,
            blocked_work_item_ids=blocked_work_item_ids,
            completed_milestone_ids=completed_milestone_ids,
            required_validation_ids=required_validation_ids,
            basis_record_ids=basis_record_ids,
            basis_record_revisions={},
            basis_fingerprint=None,
            confirmation_state="proposed",
            confirmed_by=None,
        )
        _create_checkpoint(
            self.repository,
            record_id=record_id,
            metadata=metadata,
            provenance=_proposal_provenance(actor_type),
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="checkpoint.propose",
            actor_type=actor_type,
        )
        return self.get(record_id)

    def get(self, checkpoint_id: str) -> ProjectCheckpointInfo:
        return _checkpoint_from_record(
            _require_record(self.repository, checkpoint_id),
            self.repository,
        )

    def list(
        self,
        *,
        project_id: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> tuple[ProjectCheckpointInfo, ...]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise CheckpointValidationError("checkpoint list limit is invalid")
        safe_project_id = _optional_uuid("project ID", project_id)
        rows = self.repository.connection.execute(
            "SELECT id FROM records "
            "WHERE record_type = 'project_checkpoint' "
            "ORDER BY created_at, id"
        ).fetchall()
        result: list[ProjectCheckpointInfo] = []
        for row in rows:
            checkpoint = self.get(cast(str, row[0]))
            if not include_archived and checkpoint.lifecycle_status != "active":
                continue
            if safe_project_id is not None and checkpoint.project_id != safe_project_id:
                continue
            result.append(checkpoint)
            if len(result) >= limit:
                break
        return tuple(result)

    def confirm(
        self,
        checkpoint_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: CheckpointActor = "user",
    ) -> ProjectCheckpointInfo:
        """Confirm the exact current basis through the trusted user path."""

        _require_user(actor_type)
        current_record = _require_record(self.repository, checkpoint_id)
        current = _checkpoint_from_record(current_record, self.repository)
        _require_active(current)
        if current.confirmation_state != "proposed":
            raise CheckpointValidationError("only proposed checkpoints may be confirmed")
        _validate_live_links(self.repository, current)
        basis_revisions = _capture_basis_revisions(self.repository, current)
        fingerprint = _basis_fingerprint(
            current,
            basis_revisions,
        )
        metadata = dict(current_record.metadata)
        metadata["basis_record_revisions"] = dict(basis_revisions)
        metadata["basis_fingerprint"] = fingerprint
        metadata["confirmation_state"] = "confirmed"
        metadata["confirmed_by"] = "user"
        _update_checkpoint(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="checkpoint.confirm",
        )
        return self.get(checkpoint_id)

    def supersede(
        self,
        checkpoint_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: CheckpointActor = "user",
    ) -> ProjectCheckpointInfo:
        """Mark one confirmed checkpoint superseded without rewriting its basis."""

        _require_user(actor_type)
        current_record = _require_record(self.repository, checkpoint_id)
        current = _checkpoint_from_record(current_record, self.repository)
        _require_active(current)
        if current.confirmation_state != "confirmed":
            raise CheckpointValidationError("only confirmed checkpoints may be superseded")
        metadata = dict(current_record.metadata)
        metadata["confirmation_state"] = "superseded"
        _update_checkpoint(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="checkpoint.supersede",
        )
        return self.get(checkpoint_id)

    def archive(
        self,
        checkpoint_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: CheckpointActor = "user",
    ) -> ProjectCheckpointInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, checkpoint_id)
        current = _checkpoint_from_record(current_record, self.repository)
        _require_active(current)
        _update_checkpoint(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=current_record.metadata,
            lifecycle_status="archived",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="checkpoint.archive",
        )
        return self.get(checkpoint_id)

    def export_json(self, checkpoint_id: str) -> str:
        checkpoint = self.get(checkpoint_id)
        if checkpoint.sensitivity == "secret":
            raise CheckpointValidationError("secret checkpoints cannot use normal export")
        return _canonical_json(
            {
                "export_schema": "doll.project-checkpoint.v1",
                "record": _record_payload(_require_record(self.repository, checkpoint_id)),
                "derived_freshness": checkpoint.freshness,
            }
        )


def _validated_checkpoint_values(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    as_of: str,
    summary: str,
    current_phase: str,
    current_goal: str,
    active_work_item_ids: Sequence[str],
    next_work_item_ids: Sequence[str],
    blocked_work_item_ids: Sequence[str],
    completed_milestone_ids: Sequence[str],
    required_validation_ids: Sequence[str],
    basis_record_ids: Sequence[str],
    basis_record_revisions: Mapping[str, int],
    basis_fingerprint: str | None,
    confirmation_state: str,
    confirmed_by: str | None,
) -> dict[str, object]:
    safe_self_id = _uuid("checkpoint ID", self_id)
    safe_project_id = _uuid("checkpoint project ID", project_id)
    safe_as_of = _utc("checkpoint as-of", as_of)
    safe_summary = _text("checkpoint summary", summary, MAX_SUMMARY_LENGTH)
    safe_phase = _text("checkpoint current phase", current_phase, MAX_PHASE_LENGTH)
    safe_goal = _text("checkpoint current goal", current_goal, MAX_GOAL_LENGTH)
    active_ids = _reference_ids("active work-item IDs", active_work_item_ids)
    next_ids = _reference_ids("next work-item IDs", next_work_item_ids)
    blocked_ids = _reference_ids("blocked work-item IDs", blocked_work_item_ids)
    milestone_ids = _reference_ids("completed milestone IDs", completed_milestone_ids)
    validation_ids = _reference_ids("required validation IDs", required_validation_ids)
    additional_basis_ids = _reference_ids("additional basis record IDs", basis_record_ids)
    _require_disjoint_work_lists(active_ids, next_ids, blocked_ids, milestone_ids)
    automatic_basis = {
        safe_project_id,
        *active_ids,
        *next_ids,
        *blocked_ids,
        *milestone_ids,
        *validation_ids,
    }
    if safe_self_id in automatic_basis or safe_self_id in additional_basis_ids:
        raise CheckpointValidationError("checkpoint cannot include itself in its basis")
    overlap = automatic_basis.intersection(additional_basis_ids)
    if overlap:
        raise CheckpointValidationError("additional basis records duplicate required basis")
    safe_state = _confirmation_state(confirmation_state)
    safe_confirmed_by = _confirmed_by(confirmed_by)
    revisions = _basis_revisions(basis_record_revisions)
    expected_basis_ids = automatic_basis | set(additional_basis_ids)
    if safe_state == "proposed":
        if revisions or basis_fingerprint is not None or safe_confirmed_by is not None:
            raise CheckpointValidationError(
                "proposed checkpoint contains confirmed basis metadata"
            )
    else:
        if safe_confirmed_by != "user":
            raise CheckpointValidationError("confirmed checkpoint requires user confirmation")
        if set(revisions) != expected_basis_ids:
            raise CheckpointValidationError(
                "checkpoint basis revisions do not match its declared basis"
            )
        _fingerprint(basis_fingerprint)
    _validate_project_link(repository, safe_project_id)
    _validate_work_item_lists(
        repository,
        project_id=safe_project_id,
        active_ids=active_ids,
        next_ids=next_ids,
        blocked_ids=blocked_ids,
        milestone_ids=milestone_ids,
    )
    _validate_generic_basis_links(repository, validation_ids, additional_basis_ids)
    return {
        "project_id": safe_project_id,
        "as_of": safe_as_of,
        "summary": safe_summary,
        "current_phase": safe_phase,
        "current_goal": safe_goal,
        "active_work_item_ids": list(active_ids),
        "next_work_item_ids": list(next_ids),
        "blocked_work_item_ids": list(blocked_ids),
        "completed_milestone_ids": list(milestone_ids),
        "required_validation_ids": list(validation_ids),
        "basis_record_ids": list(additional_basis_ids),
        "basis_record_revisions": dict(revisions),
        "basis_fingerprint": basis_fingerprint,
        "confirmation_state": safe_state,
        "confirmed_by": safe_confirmed_by,
        "fingerprint_format_version": FINGERPRINT_FORMAT_VERSION,
    }


def _checkpoint_from_record(
    record: RecordEnvelope,
    repository: StateRepository | None = None,
) -> ProjectCheckpointInfo:
    try:
        if (
            record.record_type != "project_checkpoint"
            or record.schema_version != CHECKPOINT_SCHEMA_VERSION
        ):
            raise CheckpointValidationError("checkpoint envelope is unsupported")
        if record.status not in {"active", "archived"} or record.revision < 1:
            raise CheckpointValidationError("checkpoint envelope state is invalid")
        if record.title is not None:
            raise CheckpointValidationError("checkpoint record must not use an envelope title")
        project_id = _uuid(
            "checkpoint project ID",
            _required_string(record.metadata, "project_id"),
        )
        as_of = _utc("checkpoint as-of", _required_string(record.metadata, "as_of"))
        summary = _text(
            "checkpoint summary",
            _required_string(record.metadata, "summary"),
            MAX_SUMMARY_LENGTH,
        )
        current_phase = _text(
            "checkpoint current phase",
            _required_string(record.metadata, "current_phase"),
            MAX_PHASE_LENGTH,
        )
        current_goal = _text(
            "checkpoint current goal",
            _required_string(record.metadata, "current_goal"),
            MAX_GOAL_LENGTH,
        )
        active_ids = _metadata_ids(record.metadata, "active_work_item_ids")
        next_ids = _metadata_ids(record.metadata, "next_work_item_ids")
        blocked_ids = _metadata_ids(record.metadata, "blocked_work_item_ids")
        milestone_ids = _metadata_ids(record.metadata, "completed_milestone_ids")
        validation_ids = _metadata_ids(record.metadata, "required_validation_ids")
        additional_basis_ids = _metadata_ids(record.metadata, "basis_record_ids")
        _require_disjoint_work_lists(active_ids, next_ids, blocked_ids, milestone_ids)
        confirmation_state = _confirmation_state(
            _required_string(record.metadata, "confirmation_state")
        )
        confirmed_by = _confirmed_by(record.metadata.get("confirmed_by"))
        revisions = _metadata_basis_revisions(record.metadata)
        fingerprint_value = record.metadata.get("basis_fingerprint")
        if fingerprint_value is not None and not isinstance(fingerprint_value, str):
            raise CheckpointValidationError("checkpoint fingerprint is invalid")
        fingerprint = cast(str | None, fingerprint_value)
        format_version = record.metadata.get("fingerprint_format_version")
        if format_version != FINGERPRINT_FORMAT_VERSION:
            raise CheckpointValidationError("checkpoint fingerprint format is unsupported")
        automatic_basis = {
            project_id,
            *active_ids,
            *next_ids,
            *blocked_ids,
            *milestone_ids,
            *validation_ids,
        }
        if record.id in automatic_basis or record.id in additional_basis_ids:
            raise CheckpointValidationError("checkpoint basis contains itself")
        if automatic_basis.intersection(additional_basis_ids):
            raise CheckpointValidationError("checkpoint basis contains duplicate roles")
        expected_basis = automatic_basis | set(additional_basis_ids)
        if confirmation_state == "proposed":
            if revisions or fingerprint is not None or confirmed_by is not None:
                raise CheckpointValidationError(
                    "proposed checkpoint contains confirmed basis metadata"
                )
        else:
            if record.provenance not in _TRUSTED_PROVENANCE or confirmed_by != "user":
                raise CheckpointValidationError(
                    "confirmed checkpoint requires trusted user provenance"
                )
            if set(revisions) != expected_basis:
                raise CheckpointValidationError(
                    "checkpoint basis revisions do not match declared basis"
                )
            _fingerprint(fingerprint)
        base = ProjectCheckpointInfo(
            checkpoint_id=record.id,
            project_id=project_id,
            as_of=as_of,
            summary=summary,
            current_phase=current_phase,
            current_goal=current_goal,
            active_work_item_ids=active_ids,
            next_work_item_ids=next_ids,
            blocked_work_item_ids=blocked_ids,
            completed_milestone_ids=milestone_ids,
            required_validation_ids=validation_ids,
            basis_record_ids=additional_basis_ids,
            basis_record_revisions=tuple(sorted(revisions.items())),
            basis_fingerprint=fingerprint,
            confirmation_state=confirmation_state,
            confirmed_by=confirmed_by,
            freshness=None,
            revision=record.revision,
            lifecycle_status=record.status,
            provenance=record.provenance,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        if confirmation_state != "proposed":
            expected_fingerprint = _basis_fingerprint(base, revisions)
            if fingerprint != expected_fingerprint:
                raise CheckpointValidationError("checkpoint basis fingerprint is inconsistent")
        freshness = _derive_freshness(repository, base) if repository is not None else None
    except (KeyError, TypeError, ValueError, CheckpointValidationError) as exc:
        raise CheckpointCorruptError("project checkpoint record is malformed") from exc
    return replace(base, freshness=freshness)


def _derive_freshness(
    repository: StateRepository,
    checkpoint: ProjectCheckpointInfo,
) -> CheckpointFreshness | None:
    if checkpoint.confirmation_state == "proposed":
        return None
    if checkpoint.confirmation_state == "superseded":
        return "superseded"
    try:
        for record_id, expected_revision in checkpoint.basis_record_revisions:
            if repository.get_record(record_id).revision != expected_revision:
                return "stale"
        _validate_live_links(repository, checkpoint)
    except (KeyError, CheckpointValidationError):
        return "stale"
    return "current"


def _capture_basis_revisions(
    repository: StateRepository,
    checkpoint: ProjectCheckpointInfo,
) -> dict[str, int]:
    record_ids = {
        checkpoint.project_id,
        *checkpoint.active_work_item_ids,
        *checkpoint.next_work_item_ids,
        *checkpoint.blocked_work_item_ids,
        *checkpoint.completed_milestone_ids,
        *checkpoint.required_validation_ids,
        *checkpoint.basis_record_ids,
    }
    result: dict[str, int] = {}
    for record_id in sorted(record_ids):
        try:
            result[record_id] = repository.get_record(record_id).revision
        except KeyError as exc:
            raise CheckpointValidationError("checkpoint basis record is missing") from exc
    return result


def _basis_fingerprint(
    checkpoint: ProjectCheckpointInfo,
    basis_revisions: Mapping[str, int],
) -> str:
    payload = {
        "fingerprint_format_version": FINGERPRINT_FORMAT_VERSION,
        "checkpoint_id": checkpoint.checkpoint_id,
        "project_id": checkpoint.project_id,
        "as_of": checkpoint.as_of,
        "summary": checkpoint.summary,
        "current_phase": checkpoint.current_phase,
        "current_goal": checkpoint.current_goal,
        "active_work_item_ids": list(checkpoint.active_work_item_ids),
        "next_work_item_ids": list(checkpoint.next_work_item_ids),
        "blocked_work_item_ids": list(checkpoint.blocked_work_item_ids),
        "completed_milestone_ids": list(checkpoint.completed_milestone_ids),
        "required_validation_ids": list(checkpoint.required_validation_ids),
        "basis_record_ids": list(checkpoint.basis_record_ids),
        "basis_record_revisions": {
            record_id: basis_revisions[record_id]
            for record_id in sorted(basis_revisions)
        },
    }
    encoded = _canonical_json(payload).encode("utf-8")
    return _FINGERPRINT_PREFIX + hashlib.sha256(encoded).hexdigest()


def _validate_live_links(
    repository: StateRepository,
    checkpoint: ProjectCheckpointInfo,
) -> None:
    _validate_project_link(repository, checkpoint.project_id)
    _validate_work_item_lists(
        repository,
        project_id=checkpoint.project_id,
        active_ids=checkpoint.active_work_item_ids,
        next_ids=checkpoint.next_work_item_ids,
        blocked_ids=checkpoint.blocked_work_item_ids,
        milestone_ids=checkpoint.completed_milestone_ids,
    )
    _validate_generic_basis_links(
        repository,
        checkpoint.required_validation_ids,
        checkpoint.basis_record_ids,
    )


def _validate_project_link(repository: StateRepository, project_id: str) -> None:
    try:
        record = repository.get_record(project_id)
        if record.record_type != "project" or record.status != "active":
            raise CheckpointValidationError("checkpoint project link is invalid")
        _project_from_record(record, repository)
    except (KeyError, ProjectDecisionCorruptError, CheckpointValidationError) as exc:
        raise CheckpointValidationError("checkpoint requires a valid active project") from exc


def _validate_work_item_lists(
    repository: StateRepository,
    *,
    project_id: str,
    active_ids: tuple[str, ...],
    next_ids: tuple[str, ...],
    blocked_ids: tuple[str, ...],
    milestone_ids: tuple[str, ...],
) -> None:
    expected = (
        (active_ids, frozenset({"in_progress"}), None),
        (next_ids, frozenset({"ready"}), None),
        (blocked_ids, frozenset({"blocked"}), None),
        (milestone_ids, frozenset({"completed"}), "milestone"),
    )
    for record_ids, statuses, expected_kind in expected:
        for record_id in record_ids:
            item = _active_work_item(repository, record_id)
            if item.project_id != project_id:
                raise CheckpointValidationError(
                    "checkpoint work-item link crosses project scope"
                )
            if item.work_status not in statuses:
                raise CheckpointValidationError(
                    "checkpoint work-item link has the wrong domain state"
                )
            if expected_kind is not None and item.kind != expected_kind:
                raise CheckpointValidationError(
                    "completed milestone link is not a milestone"
                )


def _active_work_item(repository: StateRepository, record_id: str) -> WorkItemInfo:
    try:
        record = repository.get_record(record_id)
        if record.record_type != "work_item" or record.status != "active":
            raise CheckpointValidationError("checkpoint work-item link is invalid")
        return _work_item_from_record(record)
    except (KeyError, WorkItemCorruptError, CheckpointValidationError) as exc:
        raise CheckpointValidationError("checkpoint work-item link is invalid") from exc


def _validate_generic_basis_links(
    repository: StateRepository,
    validation_ids: tuple[str, ...],
    basis_ids: tuple[str, ...],
) -> None:
    for record_id in (*validation_ids, *basis_ids):
        try:
            record = repository.get_record(record_id)
        except KeyError as exc:
            raise CheckpointValidationError("checkpoint basis link is missing") from exc
        if record.status != "active" or record.sensitivity == "secret":
            raise CheckpointValidationError("checkpoint basis link is not portable")


def _create_checkpoint(
    repository: StateRepository,
    *,
    record_id: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    action: str,
    actor_type: CheckpointActor,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type="project_checkpoint",
        schema_version=CHECKPOINT_SCHEMA_VERSION,
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
            ) VALUES (?, 'project_checkpoint', 1, ?, ?, 1, 'active', ?, ?, NULL, ?)
            """,
            (
                record_id,
                now,
                now,
                provenance,
                sensitivity,
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
        raise StateCorruptError("project checkpoint could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _update_checkpoint(
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
            raise CheckpointValidationError("archived checkpoint cannot be changed")
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = ?,
                provenance = ?, metadata_json = ?
            WHERE id = ? AND revision = ? AND status = 'active'
            """,
            (
                now,
                lifecycle_status,
                provenance,
                _serialize_record_metadata(metadata),
                current_record.id,
                expected_revision,
            ),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("checkpoint revision changed during update")
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
        raise StateCorruptError("project checkpoint could not be updated") from exc
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
    actor_type: CheckpointActor,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
) -> None:
    audit_metadata = {
        "record_type": "project_checkpoint",
        "confirmation_state": _required_string(metadata, "confirmation_state"),
        "sensitivity": sensitivity,
        "active_work_count": len(_metadata_list(metadata, "active_work_item_ids")),
        "blocked_work_count": len(_metadata_list(metadata, "blocked_work_item_ids")),
        "basis_count": len(cast(dict[str, object], metadata["basis_record_revisions"])),
    }
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'project_checkpoint', ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
            target_id,
            "Changed authoritative project-checkpoint record",
            _serialize_audit_metadata(audit_metadata),
        ),
    )


def _require_record(repository: StateRepository, checkpoint_id: str) -> RecordEnvelope:
    safe_id = _uuid("checkpoint ID", checkpoint_id)
    try:
        record = repository.get_record(safe_id)
    except KeyError as exc:
        raise CheckpointValidationError("checkpoint does not exist") from exc
    if record.record_type != "project_checkpoint":
        raise CheckpointValidationError("record is not a project checkpoint")
    return record


def _require_active(checkpoint: ProjectCheckpointInfo) -> None:
    if checkpoint.lifecycle_status != "active":
        raise CheckpointValidationError("archived checkpoint cannot be changed")


def _require_user(actor_type: CheckpointActor) -> None:
    if actor_type != "user":
        raise CheckpointValidationError("checkpoint confirmation requires the user path")


def _proposal_provenance(actor_type: CheckpointActor) -> RecordProvenance:
    if actor_type == "user":
        return "user-created"
    if actor_type == "model":
        return "model-proposed"
    if actor_type == "importer":
        return "imported"
    return "system-generated"


def _audit_actor(actor_type: CheckpointActor) -> str:
    return "system" if actor_type == "importer" else actor_type


def _confirmation_state(value: object) -> CheckpointConfirmationState:
    if not isinstance(value, str) or value not in _CONFIRMATION_STATES:
        raise CheckpointValidationError("checkpoint confirmation state is invalid")
    return cast(CheckpointConfirmationState, value)


def _confirmed_by(value: object) -> Literal["user"] | None:
    if value is None:
        return None
    if value != "user":
        raise CheckpointValidationError("checkpoint confirmer is invalid")
    return "user"


def _basis_revisions(value: Mapping[str, int]) -> dict[str, int]:
    if len(value) > MAX_LINKS:
        raise CheckpointValidationError("checkpoint basis has too many records")
    result: dict[str, int] = {}
    for raw_id, raw_revision in value.items():
        record_id = _uuid("checkpoint basis record ID", raw_id)
        if (
            not isinstance(raw_revision, int)
            or isinstance(raw_revision, bool)
            or raw_revision < 1
        ):
            raise CheckpointValidationError("checkpoint basis revision is invalid")
        if record_id in result:
            raise CheckpointValidationError("checkpoint basis contains duplicate IDs")
        result[record_id] = raw_revision
    return dict(sorted(result.items()))


def _metadata_basis_revisions(metadata: dict[str, object]) -> dict[str, int]:
    value = metadata.get("basis_record_revisions")
    if not isinstance(value, dict):
        raise CheckpointValidationError("checkpoint basis revisions must be an object")
    if any(not isinstance(key, str) for key in value):
        raise CheckpointValidationError("checkpoint basis revision keys are invalid")
    typed: dict[str, int] = {}
    for key, revision in value.items():
        if not isinstance(key, str):
            raise CheckpointValidationError("checkpoint basis revision key is invalid")
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise CheckpointValidationError("checkpoint basis revision is invalid")
        typed[key] = revision
    return _basis_revisions(typed)


def _fingerprint(value: object) -> str:
    if not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value):
        raise CheckpointValidationError("checkpoint basis fingerprint is invalid")
    return value


def _require_disjoint_work_lists(*groups: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for group in groups:
        overlap = seen.intersection(group)
        if overlap:
            raise CheckpointValidationError(
                "checkpoint work-item roles must be disjoint"
            )
        seen.update(group)


def _reference_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_LINKS:
        raise CheckpointValidationError(f"{name} are invalid")
    result: list[str] = []
    for value in values:
        record_id = _uuid(name, value)
        if record_id in result:
            raise CheckpointValidationError(f"{name} contain duplicates")
        result.append(record_id)
    return tuple(result)


def _metadata_ids(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CheckpointValidationError(f"{key} must be an ID list")
    return _reference_ids(key, cast(list[str], value))


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise CheckpointValidationError(f"{key} must be a list")
    return value


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CheckpointValidationError(f"{key} is missing or invalid")
    return value


def _text(name: str, value: object, max_length: int) -> str:
    if not isinstance(value, str):
        raise CheckpointValidationError(f"{name} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        raise CheckpointValidationError(f"{name} length is invalid")
    if _POSIX_PATH.search(normalized) or _WINDOWS_PATH.search(normalized):
        raise CheckpointValidationError(f"{name} must not contain a local absolute path")
    return normalized


def _uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise CheckpointValidationError(f"{name} is invalid")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise CheckpointValidationError(f"{name} is invalid") from exc


def _optional_uuid(name: str, value: object) -> str | None:
    return None if value is None else _uuid(name, value)


def _utc(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CheckpointValidationError(f"{name} must use UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CheckpointValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise CheckpointValidationError(f"{name} must be UTC")
    return value


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
        raise CheckpointValidationError("checkpoint data is not strict JSON") from exc
