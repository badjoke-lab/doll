"""Durable project work items with trusted lifecycle transitions."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.artifact import ArtifactCorruptError, _artifact_from_record
from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.project_state import (
    ProjectDecisionCorruptError,
    _decision_from_record,
    _project_from_record,
)
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

WorkItemKind = Literal["task", "milestone", "investigation", "maintenance", "review"]
WorkItemStatus = Literal[
    "proposed",
    "ready",
    "in_progress",
    "blocked",
    "completed",
    "cancelled",
]
VerificationState = Literal[
    "not_verified",
    "pending",
    "passed",
    "failed",
    "not_applicable",
]
WorkItemActor = Literal["user", "model", "runtime", "capability", "system"]

WORK_ITEM_SCHEMA_VERSION = 1
_WORK_ITEM_KINDS = frozenset({"task", "milestone", "investigation", "maintenance", "review"})
_WORK_ITEM_STATUSES = frozenset(
    {"proposed", "ready", "in_progress", "blocked", "completed", "cancelled"}
)
_VERIFICATION_STATES = frozenset({"not_verified", "pending", "passed", "failed", "not_applicable"})
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"in_progress", "blocked", "cancelled"}),
    "in_progress": frozenset({"blocked", "completed", "cancelled"}),
    "blocked": frozenset({"ready", "in_progress", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_POSIX_PATH = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]")

MAX_TITLE_LENGTH = 240
MAX_DESCRIPTION_LENGTH = 6000
MAX_CRITERION_LENGTH = 2000
MAX_LIST_ITEM_LENGTH = 1000
MAX_LIST_ITEMS = 100
MAX_LINKS = 100
MAX_LIST_LIMIT = 500


class WorkItemError(StateError):
    """Base class for WorkItemRecord failures."""


class WorkItemValidationError(WorkItemError):
    """Raised when a requested work-item value or transition is invalid."""


class WorkItemCorruptError(WorkItemError):
    """Raised when a persisted WorkItemRecord is malformed."""


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    criterion_id: str
    description: str
    required_evidence_kind: str | None
    blocking: bool


@dataclass(frozen=True, slots=True)
class WorkItemInfo:
    work_item_id: str
    project_id: str
    kind: WorkItemKind
    title: str
    description: str
    work_status: WorkItemStatus
    priority: int
    started_at: str | None
    completed_at: str | None
    depends_on_ids: tuple[str, ...]
    blocked_by_ids: tuple[str, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    verification_state: VerificationState
    verification_evidence_ids: tuple[str, ...]
    source_decision_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class WorkItemService:
    repository: StateRepository

    def propose(
        self,
        *,
        project_id: str,
        kind: WorkItemKind,
        title: str,
        description: str,
        priority: int = 50,
        depends_on_ids: Sequence[str] = (),
        acceptance_criteria: Sequence[AcceptanceCriterion] = (),
        source_decision_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: WorkItemActor = "model",
    ) -> WorkItemInfo:
        """Create an unaccepted proposal; no actor can propose completed work."""

        provenance = _proposal_provenance(actor_type)
        record_id = str(uuid4())
        metadata = _validated_work_item_values(
            self.repository,
            self_id=record_id,
            project_id=project_id,
            kind=kind,
            title=title,
            description=description,
            work_status="proposed",
            priority=priority,
            started_at=None,
            completed_at=None,
            depends_on_ids=depends_on_ids,
            blocked_by_ids=(),
            acceptance_criteria=acceptance_criteria,
            verification_state="not_verified",
            verification_evidence_ids=(),
            source_decision_ids=source_decision_ids,
            artifact_ids=artifact_ids,
            source_ids=source_ids,
        )
        _create_work_item(
            self.repository,
            record_id=record_id,
            metadata=metadata,
            provenance=provenance,
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="work-item.propose",
            actor_type=actor_type,
        )
        return self.get(record_id)

    def create(
        self,
        *,
        project_id: str,
        kind: WorkItemKind,
        title: str,
        description: str,
        priority: int = 50,
        depends_on_ids: Sequence[str] = (),
        acceptance_criteria: Sequence[AcceptanceCriterion] = (),
        source_decision_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: WorkItemActor = "user",
    ) -> WorkItemInfo:
        """Create accepted ready work through the trusted user path."""

        _require_user(actor_type)
        record_id = str(uuid4())
        metadata = _validated_work_item_values(
            self.repository,
            self_id=record_id,
            project_id=project_id,
            kind=kind,
            title=title,
            description=description,
            work_status="ready",
            priority=priority,
            started_at=None,
            completed_at=None,
            depends_on_ids=depends_on_ids,
            blocked_by_ids=(),
            acceptance_criteria=acceptance_criteria,
            verification_state="not_verified",
            verification_evidence_ids=(),
            source_decision_ids=source_decision_ids,
            artifact_ids=artifact_ids,
            source_ids=source_ids,
        )
        _create_work_item(
            self.repository,
            record_id=record_id,
            metadata=metadata,
            provenance="user-created",
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="work-item.create",
            actor_type="user",
        )
        return self.get(record_id)

    def get(self, work_item_id: str) -> WorkItemInfo:
        return _work_item_from_record(
            _require_record(self.repository, work_item_id),
            self.repository,
        )

    def list(
        self,
        *,
        project_id: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> tuple[WorkItemInfo, ...]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise WorkItemValidationError("work-item list limit is invalid")
        safe_project_id = _optional_uuid("project ID", project_id)
        rows = self.repository.connection.execute(
            "SELECT id FROM records WHERE record_type = 'work_item' ORDER BY created_at, id"
        ).fetchall()
        result: list[WorkItemInfo] = []
        for row in rows:
            item = self.get(cast(str, row[0]))
            if not include_archived and item.lifecycle_status != "active":
                continue
            if safe_project_id is not None and item.project_id != safe_project_id:
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return tuple(result)

    def update_definition(
        self,
        work_item_id: str,
        *,
        expected_revision: int,
        title: str,
        description: str,
        priority: int,
        depends_on_ids: Sequence[str],
        acceptance_criteria: Sequence[AcceptanceCriterion],
        source_decision_ids: Sequence[str],
        artifact_ids: Sequence[str],
        source_ids: Sequence[str],
        operation_id: str | None = None,
        actor_type: WorkItemActor = "user",
    ) -> WorkItemInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, work_item_id)
        current = _work_item_from_record(current_record, self.repository)
        _require_active(current)
        metadata = _validated_work_item_values(
            self.repository,
            self_id=current.work_item_id,
            project_id=current.project_id,
            kind=current.kind,
            title=title,
            description=description,
            work_status=current.work_status,
            priority=priority,
            started_at=current.started_at,
            completed_at=current.completed_at,
            depends_on_ids=depends_on_ids,
            blocked_by_ids=current.blocked_by_ids,
            acceptance_criteria=acceptance_criteria,
            verification_state=current.verification_state,
            verification_evidence_ids=current.verification_evidence_ids,
            source_decision_ids=source_decision_ids,
            artifact_ids=artifact_ids,
            source_ids=source_ids,
        )
        _update_work_item(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="work-item.update",
            actor_type="user",
        )
        return self.get(work_item_id)

    def transition(
        self,
        work_item_id: str,
        *,
        expected_revision: int,
        to_status: WorkItemStatus,
        occurred_at: str | None = None,
        blocked_by_ids: Sequence[str] | None = None,
        operation_id: str | None = None,
        actor_type: WorkItemActor = "user",
    ) -> WorkItemInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, work_item_id)
        current = _work_item_from_record(current_record, self.repository)
        _require_active(current)
        safe_status = _work_status(to_status)
        if safe_status not in _ALLOWED_TRANSITIONS[current.work_status]:
            raise WorkItemValidationError("work-item lifecycle transition is not allowed")
        timestamp = _optional_utc("work-item transition time", occurred_at) or _utc_now()
        started_at = current.started_at
        completed_at = current.completed_at
        if safe_status == "in_progress" and started_at is None:
            started_at = timestamp
        if safe_status == "completed":
            started_at = started_at or timestamp
            completed_at = timestamp
        else:
            completed_at = None
        if safe_status == "blocked":
            blockers = current.blocked_by_ids if blocked_by_ids is None else tuple(blocked_by_ids)
        else:
            if blocked_by_ids is not None and tuple(blocked_by_ids):
                raise WorkItemValidationError("only blocked work may declare current blockers")
            blockers = ()
        metadata = _validated_work_item_values(
            self.repository,
            self_id=current.work_item_id,
            project_id=current.project_id,
            kind=current.kind,
            title=current.title,
            description=current.description,
            work_status=safe_status,
            priority=current.priority,
            started_at=started_at,
            completed_at=completed_at,
            depends_on_ids=current.depends_on_ids,
            blocked_by_ids=blockers,
            acceptance_criteria=current.acceptance_criteria,
            verification_state=current.verification_state,
            verification_evidence_ids=current.verification_evidence_ids,
            source_decision_ids=current.source_decision_ids,
            artifact_ids=current.artifact_ids,
            source_ids=current.source_ids,
        )
        _update_work_item(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action=f"work-item.{safe_status}",
            actor_type="user",
        )
        return self.get(work_item_id)

    def set_verification(
        self,
        work_item_id: str,
        *,
        expected_revision: int,
        verification_state: VerificationState,
        evidence_ids: Sequence[str] = (),
        operation_id: str | None = None,
        actor_type: WorkItemActor = "user",
    ) -> WorkItemInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, work_item_id)
        current = _work_item_from_record(current_record, self.repository)
        _require_active(current)
        metadata = _validated_work_item_values(
            self.repository,
            self_id=current.work_item_id,
            project_id=current.project_id,
            kind=current.kind,
            title=current.title,
            description=current.description,
            work_status=current.work_status,
            priority=current.priority,
            started_at=current.started_at,
            completed_at=current.completed_at,
            depends_on_ids=current.depends_on_ids,
            blocked_by_ids=current.blocked_by_ids,
            acceptance_criteria=current.acceptance_criteria,
            verification_state=verification_state,
            verification_evidence_ids=evidence_ids,
            source_decision_ids=current.source_decision_ids,
            artifact_ids=current.artifact_ids,
            source_ids=current.source_ids,
        )
        _update_work_item(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="work-item.verify",
            actor_type="user",
        )
        return self.get(work_item_id)

    def archive(
        self,
        work_item_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: WorkItemActor = "user",
    ) -> WorkItemInfo:
        _require_user(actor_type)
        current_record = _require_record(self.repository, work_item_id)
        current = _work_item_from_record(current_record, self.repository)
        _require_active(current)
        _update_work_item(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            metadata=current_record.metadata,
            lifecycle_status="archived",
            provenance="user-confirmed",
            operation_id=operation_id,
            action="work-item.archive",
            actor_type="user",
        )
        return self.get(work_item_id)

    def export_json(self, work_item_id: str) -> str:
        item = self.get(work_item_id)
        if item.sensitivity == "secret":
            raise WorkItemValidationError("secret work items cannot use normal export")
        return _canonical_json(
            {
                "export_schema": "doll.work-item.v1",
                "record": _record_payload(_require_record(self.repository, work_item_id)),
            }
        )


def _validated_work_item_values(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    kind: str,
    title: str,
    description: str,
    work_status: str,
    priority: int,
    started_at: str | None,
    completed_at: str | None,
    depends_on_ids: Sequence[str],
    blocked_by_ids: Sequence[str],
    acceptance_criteria: Sequence[AcceptanceCriterion],
    verification_state: str,
    verification_evidence_ids: Sequence[str],
    source_decision_ids: Sequence[str],
    artifact_ids: Sequence[str],
    source_ids: Sequence[str],
) -> dict[str, object]:
    safe_self_id = _uuid("work-item ID", self_id)
    safe_project_id = _uuid("work-item project ID", project_id)
    safe_kind = _kind(kind)
    safe_title = _text("work-item title", title, MAX_TITLE_LENGTH)
    safe_description = _text("work-item description", description, MAX_DESCRIPTION_LENGTH)
    safe_status = _work_status(work_status)
    safe_priority = _priority(priority)
    safe_started_at = _optional_utc("work-item started-at", started_at)
    safe_completed_at = _optional_utc("work-item completed-at", completed_at)
    if safe_completed_at is not None:
        if safe_started_at is None or _parse_utc(safe_completed_at) < _parse_utc(safe_started_at):
            raise WorkItemValidationError("work-item completion precedes start")
    if safe_status == "completed" and safe_completed_at is None:
        raise WorkItemValidationError("completed work requires completed-at")
    if safe_status != "completed" and safe_completed_at is not None:
        raise WorkItemValidationError("non-completed work cannot have completed-at")
    safe_dependencies = _reference_ids("work-item dependency IDs", depends_on_ids)
    safe_blockers = _reference_ids("work-item blocker IDs", blocked_by_ids)
    if safe_status == "blocked" and not safe_blockers:
        raise WorkItemValidationError("blocked work requires at least one blocker")
    if safe_status != "blocked" and safe_blockers:
        raise WorkItemValidationError("only blocked work may declare current blockers")
    if safe_self_id in safe_dependencies or safe_self_id in safe_blockers:
        raise WorkItemValidationError("work item cannot depend on or be blocked by itself")
    if set(safe_dependencies).intersection(safe_blockers):
        raise WorkItemValidationError("dependency and blocker relations must remain distinct")
    safe_criteria = _criteria(acceptance_criteria)
    safe_verification = _verification_state(verification_state)
    safe_evidence = _reference_ids("verification evidence IDs", verification_evidence_ids)
    if safe_verification in {"passed", "failed"} and not safe_evidence:
        raise WorkItemValidationError("passed or failed verification requires evidence")
    if safe_verification in {"not_verified", "not_applicable"} and safe_evidence:
        raise WorkItemValidationError("verification state cannot carry evidence")
    safe_decisions = _reference_ids("source decision IDs", source_decision_ids)
    safe_artifacts = _reference_ids("work-item artifact IDs", artifact_ids)
    safe_sources = _reference_ids("work-item source IDs", source_ids)
    if safe_self_id in safe_sources:
        raise WorkItemValidationError("work item cannot cite itself as a source")
    _validate_project_link(repository, safe_project_id)
    _validate_work_item_relations(
        repository,
        self_id=safe_self_id,
        project_id=safe_project_id,
        depends_on_ids=safe_dependencies,
        blocked_by_ids=safe_blockers,
    )
    _validate_typed_links(
        repository,
        decision_ids=safe_decisions,
        evidence_ids=safe_evidence,
        artifact_ids=safe_artifacts,
        source_ids=safe_sources,
    )
    return {
        "project_id": safe_project_id,
        "kind": safe_kind,
        "title": safe_title,
        "description": safe_description,
        "status": safe_status,
        "priority": safe_priority,
        "started_at": safe_started_at,
        "completed_at": safe_completed_at,
        "depends_on_ids": list(safe_dependencies),
        "blocked_by_ids": list(safe_blockers),
        "acceptance_criteria": [_criterion_payload(item) for item in safe_criteria],
        "verification_state": safe_verification,
        "verification_evidence_ids": list(safe_evidence),
        "source_decision_ids": list(safe_decisions),
        "artifact_ids": list(safe_artifacts),
        "source_ids": list(safe_sources),
    }


def _work_item_from_record(
    record: RecordEnvelope,
    repository: StateRepository | None = None,
) -> WorkItemInfo:
    try:
        if record.record_type != "work_item" or record.schema_version != WORK_ITEM_SCHEMA_VERSION:
            raise WorkItemValidationError("work-item envelope is unsupported")
        if record.status not in {"active", "archived"}:
            raise WorkItemValidationError("work-item envelope status is unsupported")
        if record.revision < 1:
            raise WorkItemValidationError("work-item revision must be positive")
        project_id = _uuid("work-item project ID", _required_string(record.metadata, "project_id"))
        kind = _kind(_required_string(record.metadata, "kind"))
        title = _text(
            "work-item title", _required_string(record.metadata, "title"), MAX_TITLE_LENGTH
        )
        if record.title != title:
            raise WorkItemValidationError("work-item title is inconsistent")
        description = _text(
            "work-item description",
            _required_string(record.metadata, "description"),
            MAX_DESCRIPTION_LENGTH,
        )
        work_status = _work_status(_required_string(record.metadata, "status"))
        if work_status != "proposed" and record.provenance not in {
            "user-created",
            "user-confirmed",
        }:
            raise WorkItemValidationError("accepted work requires trusted provenance")
        priority = _priority(record.metadata.get("priority"))
        started_at = _optional_utc("work-item started-at", record.metadata.get("started_at"))
        completed_at = _optional_utc("work-item completed-at", record.metadata.get("completed_at"))
        depends_on_ids = _metadata_ids(record.metadata, "depends_on_ids")
        blocked_by_ids = _metadata_ids(record.metadata, "blocked_by_ids")
        criteria = _metadata_criteria(record.metadata, "acceptance_criteria")
        verification_state = _verification_state(
            _required_string(record.metadata, "verification_state")
        )
        verification_evidence_ids = _metadata_ids(
            record.metadata,
            "verification_evidence_ids",
        )
        source_decision_ids = _metadata_ids(record.metadata, "source_decision_ids")
        artifact_ids = _metadata_ids(record.metadata, "artifact_ids")
        source_ids = _metadata_ids(record.metadata, "source_ids")
        _validate_persisted_semantics(
            record.id,
            work_status,
            started_at,
            completed_at,
            depends_on_ids,
            blocked_by_ids,
            verification_state,
            verification_evidence_ids,
            source_ids,
        )
        if repository is not None:
            _validate_project_link(repository, project_id)
            _validate_work_item_relations(
                repository,
                self_id=record.id,
                project_id=project_id,
                depends_on_ids=depends_on_ids,
                blocked_by_ids=blocked_by_ids,
            )
            _validate_typed_links(
                repository,
                decision_ids=source_decision_ids,
                evidence_ids=verification_evidence_ids,
                artifact_ids=artifact_ids,
                source_ids=source_ids,
            )
    except (KeyError, TypeError, ValueError, WorkItemValidationError) as exc:
        raise WorkItemCorruptError("work-item record is malformed") from exc
    return WorkItemInfo(
        work_item_id=record.id,
        project_id=project_id,
        kind=kind,
        title=title,
        description=description,
        work_status=work_status,
        priority=priority,
        started_at=started_at,
        completed_at=completed_at,
        depends_on_ids=depends_on_ids,
        blocked_by_ids=blocked_by_ids,
        acceptance_criteria=criteria,
        verification_state=verification_state,
        verification_evidence_ids=verification_evidence_ids,
        source_decision_ids=source_decision_ids,
        artifact_ids=artifact_ids,
        source_ids=source_ids,
        revision=record.revision,
        lifecycle_status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_persisted_semantics(
    self_id: str,
    status: str,
    started_at: str | None,
    completed_at: str | None,
    dependencies: tuple[str, ...],
    blockers: tuple[str, ...],
    verification: str,
    evidence: tuple[str, ...],
    source_ids: tuple[str, ...],
) -> None:
    if status == "completed" and completed_at is None:
        raise WorkItemValidationError("completed work requires completed-at")
    if status != "completed" and completed_at is not None:
        raise WorkItemValidationError("non-completed work cannot have completed-at")
    if completed_at is not None and (
        started_at is None or _parse_utc(completed_at) < _parse_utc(started_at)
    ):
        raise WorkItemValidationError("work-item completion precedes start")
    if status == "blocked" and not blockers:
        raise WorkItemValidationError("blocked work requires a blocker")
    if status != "blocked" and blockers:
        raise WorkItemValidationError("only blocked work may declare blockers")
    if self_id in dependencies or self_id in blockers or self_id in source_ids:
        raise WorkItemValidationError("work-item relation contains self")
    if set(dependencies).intersection(blockers):
        raise WorkItemValidationError("dependency and blocker relations overlap")
    if verification in {"passed", "failed"} and not evidence:
        raise WorkItemValidationError("verification evidence is missing")
    if verification in {"not_verified", "not_applicable"} and evidence:
        raise WorkItemValidationError("verification evidence is not allowed")


def _validate_project_link(repository: StateRepository, project_id: str) -> None:
    try:
        record = repository.get_record(project_id)
        if record.record_type != "project" or record.status != "active":
            raise WorkItemValidationError("work-item project link is invalid")
        _project_from_record(record, repository)
    except (KeyError, ProjectDecisionCorruptError, WorkItemValidationError) as exc:
        raise WorkItemValidationError("work item requires a valid active project") from exc


def _validate_work_item_relations(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    depends_on_ids: tuple[str, ...],
    blocked_by_ids: tuple[str, ...],
) -> None:
    linked: dict[str, WorkItemInfo] = {}
    for linked_id in (*depends_on_ids, *blocked_by_ids):
        try:
            linked_record = repository.get_record(linked_id)
            if linked_record.status != "active":
                raise WorkItemValidationError("linked work item is not active")
            item = _work_item_from_record(linked_record)
        except (KeyError, WorkItemCorruptError, WorkItemValidationError) as exc:
            raise WorkItemValidationError("work-item relation target is invalid") from exc
        if item.project_id != project_id:
            raise WorkItemValidationError("work-item relation crosses project scope")
        linked[linked_id] = item
    for blocker_id in blocked_by_ids:
        if linked[blocker_id].work_status in {"completed", "cancelled"}:
            raise WorkItemValidationError("terminal work cannot be a current blocker")
    _validate_dependency_graph(
        repository,
        project_id=project_id,
        candidate_id=self_id,
        candidate_dependencies=depends_on_ids,
    )


def _validate_dependency_graph(
    repository: StateRepository,
    *,
    project_id: str,
    candidate_id: str,
    candidate_dependencies: tuple[str, ...],
) -> None:
    graph: dict[str, tuple[str, ...]] = {candidate_id: candidate_dependencies}
    rows = repository.connection.execute(
        "SELECT id FROM records WHERE record_type = 'work_item' AND status = 'active'"
    ).fetchall()
    for row in rows:
        record_id = cast(str, row[0])
        if record_id == candidate_id:
            continue
        item = _work_item_from_record(repository.get_record(record_id))
        if item.project_id == project_id:
            graph[record_id] = item.depends_on_ids
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise WorkItemValidationError("work-item dependency cycle is not allowed")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, ()):
            if dependency in graph:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in tuple(graph):
        visit(node)


def _validate_typed_links(
    repository: StateRepository,
    *,
    decision_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    artifact_ids: tuple[str, ...],
    source_ids: tuple[str, ...],
) -> None:
    for record_id in decision_ids:
        try:
            record = repository.get_record(record_id)
            if record.record_type != "decision" or record.status != "active":
                raise WorkItemValidationError("source decision link is invalid")
            _decision_from_record(record, repository)
        except (KeyError, ProjectDecisionCorruptError, WorkItemValidationError) as exc:
            raise WorkItemValidationError("source decision link is invalid") from exc
    for record_id in evidence_ids:
        try:
            record = repository.get_record(record_id)
            if record.record_type != "evidence" or record.status != "active":
                raise WorkItemValidationError("verification evidence link is invalid")
            _evidence_from_record(record)
        except (KeyError, TruthCorruptError, WorkItemValidationError) as exc:
            raise WorkItemValidationError("verification evidence link is invalid") from exc
    for record_id in artifact_ids:
        try:
            record = repository.get_record(record_id)
            if record.record_type != "artifact" or record.status != "active":
                raise WorkItemValidationError("work-item artifact link is invalid")
            _artifact_from_record(record)
        except (KeyError, ArtifactCorruptError, WorkItemValidationError) as exc:
            raise WorkItemValidationError("work-item artifact link is invalid") from exc
    for record_id in source_ids:
        try:
            record = repository.get_record(record_id)
        except KeyError as exc:
            raise WorkItemValidationError("work-item source link is missing") from exc
        if record.status != "active" or record.sensitivity == "secret":
            raise WorkItemValidationError("work-item source link is not portable")


def _create_work_item(
    repository: StateRepository,
    *,
    record_id: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    action: str,
    actor_type: WorkItemActor,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type="work_item",
        schema_version=WORK_ITEM_SCHEMA_VERSION,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    safe_operation_id = _operation_id(operation_id)
    now = _utc_now()
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at,
                revision, status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, 'work_item', 1, ?, ?, 1, 'active', ?, ?, ?, ?)
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
            operation_id=safe_operation_id,
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
        raise StateCorruptError("work-item record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _update_work_item(
    repository: StateRepository,
    *,
    current_record: RecordEnvelope,
    expected_revision: int,
    metadata: dict[str, object],
    lifecycle_status: RecordStatus,
    provenance: RecordProvenance,
    operation_id: str | None,
    action: str,
    actor_type: WorkItemActor,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    safe_operation_id = _operation_id(operation_id)
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
            raise WorkItemValidationError("archived work item cannot be changed")
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
            operation_id=safe_operation_id,
            action=action,
            target_id=current_record.id,
            actor_type=actor_type,
            metadata=metadata,
            sensitivity=current_record.sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("work-item record could not be updated") from exc
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
    actor_type: WorkItemActor,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
) -> None:
    audit_metadata: dict[str, object] = {
        "record_type": "work_item",
        "domain_status": _required_string(metadata, "status"),
        "kind": _required_string(metadata, "kind"),
        "sensitivity": sensitivity,
        "dependency_count": len(_metadata_list(metadata, "depends_on_ids")),
        "blocker_count": len(_metadata_list(metadata, "blocked_by_ids")),
        "criterion_count": len(_metadata_list(metadata, "acceptance_criteria")),
    }
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'work_item', ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            actor_type,
            _validate_audit_token("action", action, 120),
            target_id,
            "Changed authoritative work-item record",
            _serialize_audit_metadata(audit_metadata),
        ),
    )


def _require_record(repository: StateRepository, work_item_id: str) -> RecordEnvelope:
    safe_id = _uuid("work-item ID", work_item_id)
    try:
        record = repository.get_record(safe_id)
    except KeyError as exc:
        raise WorkItemValidationError("work item does not exist") from exc
    if record.record_type != "work_item":
        raise WorkItemValidationError("record is not a work item")
    return record


def _require_active(item: WorkItemInfo) -> None:
    if item.lifecycle_status != "active":
        raise WorkItemValidationError("archived work item cannot be changed")


def _require_user(actor_type: WorkItemActor) -> None:
    if actor_type != "user":
        raise WorkItemValidationError("accepted work-item mutation requires the user path")


def _proposal_provenance(actor_type: WorkItemActor) -> RecordProvenance:
    if actor_type == "user":
        return "user-created"
    if actor_type == "model":
        return "model-proposed"
    return "system-generated"


def _kind(value: object) -> WorkItemKind:
    if not isinstance(value, str) or value not in _WORK_ITEM_KINDS:
        raise WorkItemValidationError("work-item kind is invalid")
    return cast(WorkItemKind, value)


def _work_status(value: object) -> WorkItemStatus:
    if not isinstance(value, str) or value not in _WORK_ITEM_STATUSES:
        raise WorkItemValidationError("work-item status is invalid")
    return cast(WorkItemStatus, value)


def _verification_state(value: object) -> VerificationState:
    if not isinstance(value, str) or value not in _VERIFICATION_STATES:
        raise WorkItemValidationError("verification state is invalid")
    return cast(VerificationState, value)


def _priority(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
        raise WorkItemValidationError("work-item priority must be an integer from 0 to 100")
    return value


def _criteria(values: Sequence[AcceptanceCriterion]) -> tuple[AcceptanceCriterion, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_LIST_ITEMS:
        raise WorkItemValidationError("acceptance criteria are invalid")
    result: list[AcceptanceCriterion] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, AcceptanceCriterion):
            raise WorkItemValidationError("acceptance criterion is invalid")
        criterion_id = _token("criterion ID", value.criterion_id)
        if criterion_id in seen:
            raise WorkItemValidationError("acceptance criterion IDs must be unique")
        seen.add(criterion_id)
        description = _text("criterion description", value.description, MAX_CRITERION_LENGTH)
        evidence_kind = (
            _token("required evidence kind", value.required_evidence_kind)
            if value.required_evidence_kind is not None
            else None
        )
        if not isinstance(value.blocking, bool):
            raise WorkItemValidationError("criterion blocking flag is invalid")
        result.append(AcceptanceCriterion(criterion_id, description, evidence_kind, value.blocking))
    return tuple(result)


def _metadata_criteria(
    metadata: dict[str, object],
    key: str,
) -> tuple[AcceptanceCriterion, ...]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise WorkItemValidationError(f"{key} must be a list")
    result: list[AcceptanceCriterion] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise WorkItemValidationError("acceptance criterion must be an object")
        evidence_kind = raw.get("required_evidence_kind")
        if evidence_kind is not None and not isinstance(evidence_kind, str):
            raise WorkItemValidationError("required evidence kind is invalid")
        blocking = raw.get("blocking")
        if not isinstance(blocking, bool):
            raise WorkItemValidationError("criterion blocking flag is invalid")
        result.append(
            AcceptanceCriterion(
                _required_string(cast(dict[str, object], raw), "criterion_id"),
                _required_string(cast(dict[str, object], raw), "description"),
                evidence_kind,
                blocking,
            )
        )
    return _criteria(result)


def _criterion_payload(value: AcceptanceCriterion) -> dict[str, object]:
    return {
        "criterion_id": value.criterion_id,
        "description": value.description,
        "required_evidence_kind": value.required_evidence_kind,
        "blocking": value.blocking,
    }


def _reference_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > MAX_LINKS:
        raise WorkItemValidationError(f"{name} are invalid")
    result: list[str] = []
    for value in values:
        record_id = _uuid(name, value)
        if record_id in result:
            raise WorkItemValidationError(f"{name} contain duplicates")
        result.append(record_id)
    return tuple(result)


def _metadata_ids(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WorkItemValidationError(f"{key} must be an ID list")
    return _reference_ids(key, cast(list[str], value))


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise WorkItemValidationError(f"{key} must be a list")
    return value


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise WorkItemValidationError(f"{key} is missing or invalid")
    return value


def _text(name: str, value: object, max_length: int) -> str:
    if not isinstance(value, str):
        raise WorkItemValidationError(f"{name} must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        raise WorkItemValidationError(f"{name} length is invalid")
    if _POSIX_PATH.search(normalized) or _WINDOWS_PATH.search(normalized):
        raise WorkItemValidationError(f"{name} must not contain a local absolute path")
    return normalized


def _token(name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise WorkItemValidationError(f"{name} is invalid")
    return value


def _uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise WorkItemValidationError(f"{name} is invalid")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise WorkItemValidationError(f"{name} is invalid") from exc


def _optional_uuid(name: str, value: object) -> str | None:
    return None if value is None else _uuid(name, value)


def _optional_utc(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise WorkItemValidationError(f"{name} must use UTC Z notation")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise WorkItemValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise WorkItemValidationError(f"{name} must be UTC")
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
        raise WorkItemValidationError("work-item export is not strict JSON") from exc
