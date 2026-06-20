"""Immutable instruction-origin and untrusted-content boundary records."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import AuditActorType, _reject_local_path, _reject_secret_text
from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.settings import SettingsCorruptError, _policy_from_record
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
    _validate_secret_boundary,
)
from doll.state_repository import _serialize_metadata as _serialize_record_metadata

InstructionOriginClass = Literal[
    "system_policy",
    "current_user_instruction",
    "durable_user_policy",
    "user_management_action",
    "external_content",
    "imported_data",
    "tool_result",
    "runtime_output",
    "model_proposal",
    "unknown",
]
InstructionAuthorityClass = Literal[
    "system_policy",
    "current_user_instruction",
    "durable_user_policy",
    "user_management_action",
    "untrusted_data",
    "model_proposal",
    "unknown_data",
]
InstructionActorType = Literal[
    "system",
    "user",
    "retriever",
    "extractor",
    "importer",
    "tool",
    "runtime",
    "model",
    "unknown",
]
InstructionAcquisitionMethod = Literal[
    "system_defined",
    "user_entry",
    "policy_reference",
    "management_action",
    "retrieval",
    "import",
    "extraction",
    "ocr",
    "transcription",
    "tool_execution",
    "runtime_execution",
    "model_generation",
    "unknown",
]
InstructionTransformation = Literal[
    "normalization",
    "extraction",
    "ocr",
    "transcription",
    "summarization",
    "translation",
    "format_conversion",
]
InstructionAuthorityPurpose = Literal[
    "task_instruction",
    "system_policy",
    "durable_user_policy",
    "user_management_action",
    "permission_state",
    "confirmation_state",
    "capability_definition",
    "risk_tier",
    "workspace_boundary",
    "network_policy",
    "secret_policy",
    "security_instruction",
]
InstructionArchiveActor = Literal["user"]

_ALLOWED_ORIGINS = frozenset(
    {
        "system_policy",
        "current_user_instruction",
        "durable_user_policy",
        "user_management_action",
        "external_content",
        "imported_data",
        "tool_result",
        "runtime_output",
        "model_proposal",
        "unknown",
    }
)
_ALLOWED_AUTHORITIES = frozenset(
    {
        "system_policy",
        "current_user_instruction",
        "durable_user_policy",
        "user_management_action",
        "untrusted_data",
        "model_proposal",
        "unknown_data",
    }
)
_ALLOWED_ACTORS = frozenset(
    {"system", "user", "retriever", "extractor", "importer", "tool", "runtime", "model", "unknown"}
)
_ALLOWED_ACQUISITION = frozenset(
    {
        "system_defined",
        "user_entry",
        "policy_reference",
        "management_action",
        "retrieval",
        "import",
        "extraction",
        "ocr",
        "transcription",
        "tool_execution",
        "runtime_execution",
        "model_generation",
        "unknown",
    }
)
_ALLOWED_TRANSFORMATIONS = frozenset(
    {
        "normalization",
        "extraction",
        "ocr",
        "transcription",
        "summarization",
        "translation",
        "format_conversion",
    }
)
_ALLOWED_PURPOSES = frozenset(
    {
        "task_instruction",
        "system_policy",
        "durable_user_policy",
        "user_management_action",
        "permission_state",
        "confirmation_state",
        "capability_definition",
        "risk_tier",
        "workspace_boundary",
        "network_policy",
        "secret_policy",
        "security_instruction",
    }
)
_ORIGIN_AUTHORITY: dict[str, InstructionAuthorityClass] = {
    "system_policy": "system_policy",
    "current_user_instruction": "current_user_instruction",
    "durable_user_policy": "durable_user_policy",
    "user_management_action": "user_management_action",
    "external_content": "untrusted_data",
    "imported_data": "untrusted_data",
    "tool_result": "untrusted_data",
    "runtime_output": "untrusted_data",
    "model_proposal": "model_proposal",
    "unknown": "unknown_data",
}
_DATA_ONLY_ORIGINS = frozenset(
    {
        "external_content",
        "imported_data",
        "tool_result",
        "runtime_output",
        "model_proposal",
        "unknown",
    }
)
_AUTHORITY_RANK: dict[str, int] = {
    "unknown_data": 0,
    "untrusted_data": 0,
    "model_proposal": 0,
    "durable_user_policy": 2,
    "current_user_instruction": 3,
    "user_management_action": 3,
    "system_policy": 4,
}
_AUTHORITY_PURPOSES: dict[str, frozenset[str]] = {
    "system_policy": _ALLOWED_PURPOSES,
    "current_user_instruction": frozenset({"task_instruction"}),
    "durable_user_policy": frozenset({"task_instruction", "durable_user_policy"}),
    "user_management_action": frozenset(
        {"task_instruction", "user_management_action", "permission_state", "confirmation_state"}
    ),
    "untrusted_data": frozenset(),
    "model_proposal": frozenset(),
    "unknown_data": frozenset(),
}
_ALLOWED_RECORD_PROVENANCE = frozenset(
    {"user-created", "imported", "model-proposed", "system-generated", "migrated", "restored"}
)
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MAX_TITLE_LENGTH = 240
MAX_CONTENT_LENGTH = 16000
MAX_IDENTIFIER_LENGTH = 300
MAX_TRANSFORMATIONS = 12
MAX_LIST_LIMIT = 200


class InstructionOriginError(StateError):
    """Base class for instruction-origin failures."""


class InstructionOriginValidationError(InstructionOriginError):
    """Raised when instruction-origin input is invalid."""


class InstructionOriginCorruptError(InstructionOriginError):
    """Raised when a stored instruction-origin record is malformed."""


class ForbiddenInstructionMutationError(InstructionOriginError):
    """Raised when a non-user path attempts lifecycle mutation."""


@dataclass(frozen=True, slots=True)
class InstructionSource:
    """Immutable source metadata supplied by an accepted ingestion boundary."""

    origin_class: InstructionOriginClass
    actor_type: InstructionActorType
    acquisition_method: InstructionAcquisitionMethod
    source_identifier: str | None = None
    parent_operation_id: str | None = None
    session_id: str | None = None
    content_hash: str | None = None
    observed_at: str | None = None
    transformations: tuple[InstructionTransformation, ...] = ()
    derived_from_instruction_id: str | None = None
    authority_reference_id: str | None = None
    authority_reference_revision: int | None = None
    model_manifest_id: str | None = None
    runtime_adapter_id: str | None = None

    def __post_init__(self) -> None:
        values = _validate_source_values(
            origin_class=self.origin_class,
            actor_type=self.actor_type,
            acquisition_method=self.acquisition_method,
            source_identifier=self.source_identifier,
            parent_operation_id=self.parent_operation_id,
            session_id=self.session_id,
            content_hash=self.content_hash,
            observed_at=self.observed_at,
            transformations=self.transformations,
            derived_from_instruction_id=self.derived_from_instruction_id,
            authority_reference_id=self.authority_reference_id,
            authority_reference_revision=self.authority_reference_revision,
            model_manifest_id=self.model_manifest_id,
            runtime_adapter_id=self.runtime_adapter_id,
        )
        for name, value in values.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class InstructionOriginInfo:
    record_id: str
    title: str
    content: str
    origin_class: InstructionOriginClass
    authority_class: InstructionAuthorityClass
    data_only: bool
    source: InstructionSource
    revision: int
    status: RecordStatus
    record_provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class InstructionContextItem:
    record_id: str
    title: str
    content: str
    origin_class: InstructionOriginClass
    declared_authority_class: InstructionAuthorityClass
    effective_authority_class: InstructionAuthorityClass
    data_only: bool
    authority_active: bool
    authority_failure: str | None
    source_identifier: str | None
    transformations: tuple[InstructionTransformation, ...]


@dataclass(frozen=True, slots=True)
class InstructionContextBundle:
    system_policy: tuple[InstructionContextItem, ...]
    current_user_instruction: tuple[InstructionContextItem, ...]
    durable_user_policy: tuple[InstructionContextItem, ...]
    user_management_action: tuple[InstructionContextItem, ...]
    untrusted_content: tuple[InstructionContextItem, ...]
    model_proposals: tuple[InstructionContextItem, ...]
    unknown_origin: tuple[InstructionContextItem, ...]


@dataclass(frozen=True, slots=True)
class InstructionAuthorityDecision:
    allowed: bool
    purpose: InstructionAuthorityPurpose
    origin_class: InstructionOriginClass
    declared_authority_class: InstructionAuthorityClass
    effective_authority_class: InstructionAuthorityClass
    reason: str


@dataclass(slots=True)
class InstructionOriginService:
    """Persist immutable instruction provenance and enforce authority classification."""

    repository: StateRepository

    def create(
        self,
        *,
        title: str,
        content: str,
        source: InstructionSource,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> InstructionOriginInfo:
        safe_title = _validate_text("instruction title", title, MAX_TITLE_LENGTH)
        safe_content = _validate_content(content)
        safe_source = _require_source(source)
        authority = _authority_for_origin(safe_source.origin_class)
        data_only = safe_source.origin_class in _DATA_ONLY_ORIGINS
        _validate_source_references(self.repository, safe_source, safe_content, authority)
        metadata = {
            "instruction_kind": "instruction_origin",
            "title": safe_title,
            "content": safe_content,
            "origin_class": safe_source.origin_class,
            "authority_class": authority,
            "data_only": data_only,
            **_source_metadata(safe_source),
        }
        record_id = _create_instruction_record(
            self.repository,
            title=safe_title,
            metadata=metadata,
            provenance=_record_provenance(safe_source),
            sensitivity=sensitivity,
            operation_id=operation_id,
            actor_type=safe_source.actor_type,
        )
        return self.get(record_id)

    def get(self, record_id: str) -> InstructionOriginInfo:
        safe_id = _validate_uuid("instruction record ID", record_id)
        try:
            record = self.repository.get_record(safe_id)
        except KeyError:
            raise
        if record.record_type != "instruction_origin":
            raise KeyError(record_id)
        return _instruction_origin_from_record(record)

    def list(
        self, *, include_archived: bool = False, limit: int = 50
    ) -> tuple[InstructionOriginInfo, ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise InstructionOriginValidationError(
                f"instruction-origin limit must be between 1 and {MAX_LIST_LIMIT}"
            )
        status_clause = "" if include_archived else "AND status = 'active'"
        try:
            rows = self.repository.connection.execute(
                f"""
                SELECT id
                FROM records
                WHERE record_type = 'instruction_origin' {status_clause}
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("instruction-origin records are unreadable") from exc
        return tuple(self.get(cast(str, row[0])) for row in rows)

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: InstructionArchiveActor = "user",
    ) -> InstructionOriginInfo:
        if actor_type != "user":
            raise ForbiddenInstructionMutationError(
                "instruction-origin lifecycle mutation requires a user-controlled actor"
            )
        current = self.get(record_id)
        if current.status != "active":
            raise InstructionOriginValidationError("instruction-origin record is already archived")
        _archive_instruction_record(
            self.repository,
            current=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            operation_id=operation_id,
        )
        return self.get(record_id)

    def assemble_context(self, record_ids: Sequence[str]) -> InstructionContextBundle:
        ids = _validate_record_ids(record_ids)
        items = tuple(self._context_item(self.get(record_id)) for record_id in ids)
        return InstructionContextBundle(
            system_policy=tuple(
                item for item in items if item.effective_authority_class == "system_policy"
            ),
            current_user_instruction=tuple(
                item
                for item in items
                if item.effective_authority_class == "current_user_instruction"
            ),
            durable_user_policy=tuple(
                item for item in items if item.effective_authority_class == "durable_user_policy"
            ),
            user_management_action=tuple(
                item for item in items if item.effective_authority_class == "user_management_action"
            ),
            untrusted_content=tuple(
                item for item in items if item.effective_authority_class == "untrusted_data"
            ),
            model_proposals=tuple(
                item for item in items if item.effective_authority_class == "model_proposal"
            ),
            unknown_origin=tuple(
                item for item in items if item.effective_authority_class == "unknown_data"
            ),
        )

    def authority_decision(
        self, record_id: str, *, purpose: InstructionAuthorityPurpose
    ) -> InstructionAuthorityDecision:
        safe_purpose = _validate_purpose(purpose)
        item = self._context_item(self.get(record_id))
        allowed = safe_purpose in _AUTHORITY_PURPOSES[item.effective_authority_class]
        if not item.authority_active:
            reason = item.authority_failure or "authority is inactive"
        elif allowed:
            reason = "origin class is authorized for the requested purpose"
        else:
            reason = "origin class is not authorized for the requested purpose"
        return InstructionAuthorityDecision(
            allowed=allowed,
            purpose=safe_purpose,
            origin_class=item.origin_class,
            declared_authority_class=item.declared_authority_class,
            effective_authority_class=item.effective_authority_class,
            reason=reason,
        )

    def _context_item(self, info: InstructionOriginInfo) -> InstructionContextItem:
        authority_active = info.status == "active"
        authority_failure: str | None = None
        effective = info.authority_class
        if not authority_active:
            effective = "unknown_data"
            authority_failure = "instruction-origin record is archived"
        elif info.origin_class == "durable_user_policy":
            authority_active, authority_failure = _durable_policy_reference_is_current(
                self.repository, info
            )
            if not authority_active:
                effective = "untrusted_data"
        return InstructionContextItem(
            record_id=info.record_id,
            title=info.title,
            content=info.content,
            origin_class=info.origin_class,
            declared_authority_class=info.authority_class,
            effective_authority_class=effective,
            data_only=info.data_only or not authority_active,
            authority_active=authority_active,
            authority_failure=authority_failure,
            source_identifier=info.source.source_identifier,
            transformations=info.source.transformations,
        )


def _validate_instruction_origin_graph(records: dict[str, RecordEnvelope]) -> None:
    """Validate persisted derivation links without granting authority."""

    parents: dict[str, str] = {}
    infos: dict[str, InstructionOriginInfo] = {}
    for record in records.values():
        if record.record_type != "instruction_origin":
            continue
        info = _instruction_origin_from_record(record)
        infos[record.id] = info
        parent_id = info.source.derived_from_instruction_id
        if parent_id is None:
            continue
        if parent_id == record.id:
            raise InstructionOriginCorruptError(
                "instruction-origin record cannot derive from itself"
            )
        parent_record = records.get(parent_id)
        if parent_record is None or parent_record.record_type != "instruction_origin":
            raise InstructionOriginCorruptError(
                "derived instruction reference is missing or has the wrong type"
            )
        parent = _instruction_origin_from_record(parent_record)
        if _AUTHORITY_RANK[info.authority_class] > _AUTHORITY_RANK[parent.authority_class]:
            raise InstructionOriginCorruptError("derived instruction record raises authority")
        parents[record.id] = parent_id

    for start in parents:
        seen: set[str] = set()
        current = start
        while current in parents:
            if current in seen:
                raise InstructionOriginCorruptError(
                    "instruction-origin derivation graph contains a cycle"
                )
            seen.add(current)
            current = parents[current]

    for info in infos.values():
        if info.origin_class != "durable_user_policy":
            continue
        reference_id = info.source.authority_reference_id
        if reference_id is None:
            raise InstructionOriginCorruptError(
                "durable policy instruction is missing its policy reference"
            )
        referenced = records.get(reference_id)
        if referenced is None or referenced.record_type != "policy":
            raise InstructionOriginCorruptError(
                "durable policy instruction references a missing or wrong-type policy"
            )


def _validate_source_values(
    *,
    origin_class: object,
    actor_type: object,
    acquisition_method: object,
    source_identifier: object,
    parent_operation_id: object,
    session_id: object,
    content_hash: object,
    observed_at: object,
    transformations: object,
    derived_from_instruction_id: object,
    authority_reference_id: object,
    authority_reference_revision: object,
    model_manifest_id: object,
    runtime_adapter_id: object,
) -> dict[str, object]:
    if not isinstance(origin_class, str) or origin_class not in _ALLOWED_ORIGINS:
        raise InstructionOriginValidationError("invalid instruction origin class")
    if not isinstance(actor_type, str) or actor_type not in _ALLOWED_ACTORS:
        raise InstructionOriginValidationError("invalid instruction actor type")
    if not isinstance(acquisition_method, str) or acquisition_method not in _ALLOWED_ACQUISITION:
        raise InstructionOriginValidationError("invalid instruction acquisition method")
    safe_transformations = _validate_transformations(transformations)
    values: dict[str, object] = {
        "origin_class": cast(InstructionOriginClass, origin_class),
        "actor_type": cast(InstructionActorType, actor_type),
        "acquisition_method": cast(InstructionAcquisitionMethod, acquisition_method),
        "source_identifier": _validate_optional_identifier("source identifier", source_identifier),
        "parent_operation_id": _validate_optional_identifier(
            "parent operation ID", parent_operation_id
        ),
        "session_id": _validate_optional_identifier("session ID", session_id),
        "content_hash": _validate_optional_hash(content_hash),
        "observed_at": _validate_optional_utc("observed at", observed_at),
        "transformations": safe_transformations,
        "derived_from_instruction_id": _validate_optional_uuid(
            "derived instruction ID", derived_from_instruction_id
        ),
        "authority_reference_id": _validate_optional_identifier(
            "authority reference ID", authority_reference_id
        ),
        "authority_reference_revision": _validate_optional_positive_int(
            "authority reference revision", authority_reference_revision
        ),
        "model_manifest_id": _validate_optional_identifier("model manifest ID", model_manifest_id),
        "runtime_adapter_id": _validate_optional_identifier(
            "runtime adapter ID", runtime_adapter_id
        ),
    }
    _validate_origin_combination(values)
    return values


def _validate_origin_combination(values: dict[str, object]) -> None:
    origin = cast(str, values["origin_class"])
    actor = cast(str, values["actor_type"])
    method = cast(str, values["acquisition_method"])
    source_id = values["source_identifier"]
    operation_id = values["parent_operation_id"]
    session_id = values["session_id"]
    authority_id = values["authority_reference_id"]
    authority_revision = values["authority_reference_revision"]
    model_id = values["model_manifest_id"]
    runtime_id = values["runtime_adapter_id"]

    expected: dict[str, tuple[set[str], set[str]]] = {
        "system_policy": ({"system"}, {"system_defined"}),
        "current_user_instruction": ({"user"}, {"user_entry"}),
        "durable_user_policy": ({"user"}, {"policy_reference"}),
        "user_management_action": ({"user"}, {"management_action"}),
        "external_content": (
            {"retriever", "extractor"},
            {"retrieval", "extraction", "ocr", "transcription"},
        ),
        "imported_data": ({"importer"}, {"import"}),
        "tool_result": ({"tool"}, {"tool_execution"}),
        "runtime_output": ({"runtime"}, {"runtime_execution"}),
        "model_proposal": ({"model"}, {"model_generation"}),
        "unknown": ({"unknown"}, {"unknown"}),
    }
    actors, methods = expected[origin]
    if actor not in actors or method not in methods:
        raise InstructionOriginValidationError("origin, actor, and acquisition method disagree")

    if origin == "system_policy":
        _require_present(authority_id, "system policy requires an authority reference")
        _require_present(authority_revision, "system policy requires a reference revision")
    elif origin == "current_user_instruction":
        _require_present(session_id, "current user instruction requires a session ID")
        _forbid_authority_reference(authority_id, authority_revision)
    elif origin == "durable_user_policy":
        _require_present(authority_id, "durable user policy requires a policy record reference")
        _require_present(authority_revision, "durable user policy requires a policy revision")
    elif origin == "user_management_action":
        _require_present(operation_id, "user management action requires a parent operation")
        _require_present(authority_id, "user management action requires an action reference")
        _require_present(authority_revision, "user management action requires a reference revision")
    elif origin in {"external_content", "imported_data", "tool_result"}:
        _require_present(source_id, f"{origin} requires a source identifier")
        _require_present(operation_id, f"{origin} requires a parent operation")
        _forbid_authority_reference(authority_id, authority_revision)
    elif origin == "runtime_output":
        _require_present(runtime_id, "runtime output requires a runtime adapter ID")
        _require_present(operation_id, "runtime output requires a parent operation")
        _forbid_authority_reference(authority_id, authority_revision)
    elif origin == "model_proposal":
        _require_present(model_id, "model proposal requires a model manifest ID")
        _require_present(runtime_id, "model proposal requires a runtime adapter ID")
        _require_present(session_id, "model proposal requires a session ID")
        _require_present(operation_id, "model proposal requires a parent operation")
        _forbid_authority_reference(authority_id, authority_revision)
    else:
        _forbid_authority_reference(authority_id, authority_revision)
        if any(
            value is not None
            for value in (source_id, operation_id, session_id, model_id, runtime_id)
        ):
            raise InstructionOriginValidationError(
                "unknown origin cannot assert source, actor, operation, session, "
                "model, or runtime identity"
            )


def _validate_source_references(
    repository: StateRepository,
    source: InstructionSource,
    content: str,
    authority: InstructionAuthorityClass,
) -> None:
    if source.origin_class == "durable_user_policy":
        policy_id = _validate_uuid("policy record ID", source.authority_reference_id)
        try:
            record = repository.get_record(policy_id)
        except KeyError as exc:
            raise InstructionOriginValidationError(
                "referenced durable policy does not exist"
            ) from exc
        if record.record_type != "policy":
            raise InstructionOriginValidationError(
                "durable policy reference is not a policy record"
            )
        try:
            policy = _policy_from_record(record)
        except SettingsCorruptError as exc:
            raise InstructionOriginValidationError(
                "referenced durable policy is malformed"
            ) from exc
        if policy.status != "active" or not policy.enabled:
            raise InstructionOriginValidationError("referenced durable policy is not active")
        if policy.revision != source.authority_reference_revision:
            raise InstructionOriginValidationError("durable policy reference revision is stale")
        if policy.rule != content:
            raise InstructionOriginValidationError(
                "durable policy content must match the referenced rule"
            )
    if source.derived_from_instruction_id is not None:
        try:
            parent_record = repository.get_record(source.derived_from_instruction_id)
        except KeyError as exc:
            raise InstructionOriginValidationError(
                "derived instruction record does not exist"
            ) from exc
        if parent_record.record_type != "instruction_origin":
            raise InstructionOriginValidationError(
                "derived instruction reference has the wrong type"
            )
        parent = _instruction_origin_from_record(parent_record)
        if _AUTHORITY_RANK[authority] > _AUTHORITY_RANK[parent.authority_class]:
            raise InstructionOriginValidationError(
                "derived content cannot raise instruction authority"
            )


def _durable_policy_reference_is_current(
    repository: StateRepository, info: InstructionOriginInfo
) -> tuple[bool, str | None]:
    reference_id = info.source.authority_reference_id
    reference_revision = info.source.authority_reference_revision
    if reference_id is None or reference_revision is None:
        return False, "durable policy reference metadata is missing"
    try:
        record = repository.get_record(reference_id)
    except KeyError:
        return False, "durable policy reference no longer exists"
    if record.record_type != "policy":
        return False, "durable policy reference has the wrong record type"
    try:
        policy = _policy_from_record(record)
    except SettingsCorruptError:
        return False, "durable policy reference is malformed"
    if policy.status != "active" or not policy.enabled:
        return False, "durable policy reference is inactive"
    if policy.revision != reference_revision:
        return False, "durable policy reference revision changed"
    if policy.rule != info.content:
        return False, "durable policy content no longer matches"
    return True, None


def _create_instruction_record(
    repository: StateRepository,
    *,
    title: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    actor_type: InstructionActorType,
) -> str:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type="instruction_origin",
        schema_version=1,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    _validate_secret_boundary(
        record_type="instruction_origin", sensitivity=sensitivity, metadata=metadata
    )
    safe_operation_id = _validate_operation_id(operation_id)
    record_id = str(uuid4())
    now = _utc_now()
    metadata_json = _serialize_record_metadata(metadata)
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at, revision,
                status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, 'instruction_origin', 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (record_id, now, now, provenance, sensitivity, title, metadata_json),
        )
        _insert_instruction_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type=actor_type,
            action="instruction_origin.create",
            target_id=record_id,
            metadata=_instruction_audit_metadata(metadata),
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("instruction-origin record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)
    return record_id


def _archive_instruction_record(
    repository: StateRepository,
    *,
    current: RecordEnvelope,
    expected_revision: int,
    operation_id: str | None,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise InstructionOriginValidationError("expected revision must be an integer")
    safe_operation_id = _validate_operation_id(operation_id)
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        refreshed = repository.get_record(current.id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        if refreshed.status != "active":
            raise InstructionOriginValidationError("instruction-origin record is already archived")
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = 'archived'
            WHERE id = ? AND revision = ? AND status = 'active'
            """,
            (_utc_now(), current.id, expected_revision),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("record revision changed during archive")
        _insert_instruction_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type="user",
            action="instruction_origin.archive",
            target_id=current.id,
            metadata={"origin_class": _required_string(current.metadata, "origin_class")},
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("instruction-origin record could not be archived") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _insert_instruction_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    actor_type: InstructionActorType,
    action: str,
    target_id: str,
    metadata: dict[str, object],
) -> None:
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'instruction_origin', ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
            target_id,
            "Changed instruction-origin record",
            _serialize_audit_metadata(metadata),
        ),
    )


def _instruction_audit_metadata(metadata: dict[str, object]) -> dict[str, object]:
    transformations = _metadata_list(metadata, "transformations")
    return {
        "origin_class": _required_string(metadata, "origin_class"),
        "authority_class": _required_string(metadata, "authority_class"),
        "data_only": metadata.get("data_only") is True,
        "acquisition_method": _required_string(metadata, "acquisition_method"),
        "source_identifier_present": metadata.get("source_identifier") is not None,
        "content_hash_present": metadata.get("content_hash") is not None,
        "parent_operation_present": metadata.get("parent_operation_id") is not None,
        "derived_instruction_present": metadata.get("derived_from_instruction_id") is not None,
        "authority_reference_present": metadata.get("authority_reference_id") is not None,
        "transformation_count": len(transformations),
    }


def _instruction_origin_from_record(record: RecordEnvelope) -> InstructionOriginInfo:
    try:
        _validate_instruction_envelope(record)
        metadata = record.metadata
        if _required_string(metadata, "instruction_kind") != "instruction_origin":
            raise InstructionOriginValidationError("instruction kind is invalid")
        title = _validate_text(
            "instruction title", _required_string(metadata, "title"), MAX_TITLE_LENGTH
        )
        if record.title != title:
            raise InstructionOriginValidationError("instruction title is inconsistent")
        content = _validate_content(_required_string(metadata, "content"))
        origin = _validate_origin(_required_string(metadata, "origin_class"))
        authority = _validate_authority(_required_string(metadata, "authority_class"))
        if authority != _authority_for_origin(origin):
            raise InstructionOriginValidationError("instruction authority does not match origin")
        data_only = metadata.get("data_only")
        if not isinstance(data_only, bool) or data_only != (origin in _DATA_ONLY_ORIGINS):
            raise InstructionOriginValidationError(
                "instruction data-only flag does not match origin"
            )
        source = InstructionSource(
            origin_class=origin,
            actor_type=_validate_actor(_required_string(metadata, "actor_type")),
            acquisition_method=_validate_acquisition(
                _required_string(metadata, "acquisition_method")
            ),
            source_identifier=_optional_string(metadata, "source_identifier"),
            parent_operation_id=_optional_string(metadata, "parent_operation_id"),
            session_id=_optional_string(metadata, "session_id"),
            content_hash=_optional_string(metadata, "content_hash"),
            observed_at=_optional_string(metadata, "observed_at"),
            transformations=cast(
                tuple[InstructionTransformation, ...],
                tuple(_metadata_list(metadata, "transformations")),
            ),
            derived_from_instruction_id=_optional_string(metadata, "derived_from_instruction_id"),
            authority_reference_id=_optional_string(metadata, "authority_reference_id"),
            authority_reference_revision=_optional_int(metadata, "authority_reference_revision"),
            model_manifest_id=_optional_string(metadata, "model_manifest_id"),
            runtime_adapter_id=_optional_string(metadata, "runtime_adapter_id"),
        )
        if record.provenance != _record_provenance(source):
            raise InstructionOriginValidationError("record provenance does not match origin")
        return InstructionOriginInfo(
            record_id=record.id,
            title=title,
            content=content,
            origin_class=origin,
            authority_class=authority,
            data_only=data_only,
            source=source,
            revision=record.revision,
            status=record.status,
            record_provenance=record.provenance,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        InstructionOriginValidationError,
    ) as exc:
        raise InstructionOriginCorruptError("instruction-origin record is malformed") from exc


def _validate_instruction_envelope(record: RecordEnvelope) -> None:
    if record.record_type != "instruction_origin":
        raise InstructionOriginValidationError("record is not instruction_origin")
    if record.schema_version != 1:
        raise InstructionOriginValidationError("unsupported instruction-origin schema version")
    if record.revision < 1:
        raise InstructionOriginValidationError("instruction-origin revision is invalid")
    if record.status not in {"active", "archived"}:
        raise InstructionOriginValidationError("instruction-origin status is invalid")
    if record.provenance not in _ALLOWED_RECORD_PROVENANCE:
        raise InstructionOriginValidationError("instruction-origin provenance is invalid")
    _validate_record_fields(
        record_type=record.record_type,
        schema_version=record.schema_version,
        status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
    )


def _source_metadata(source: InstructionSource) -> dict[str, object]:
    return {
        "actor_type": source.actor_type,
        "acquisition_method": source.acquisition_method,
        "source_identifier": source.source_identifier,
        "parent_operation_id": source.parent_operation_id,
        "session_id": source.session_id,
        "content_hash": source.content_hash,
        "observed_at": source.observed_at,
        "transformations": list(source.transformations),
        "derived_from_instruction_id": source.derived_from_instruction_id,
        "authority_reference_id": source.authority_reference_id,
        "authority_reference_revision": source.authority_reference_revision,
        "model_manifest_id": source.model_manifest_id,
        "runtime_adapter_id": source.runtime_adapter_id,
    }


def _record_provenance(source: InstructionSource) -> RecordProvenance:
    if source.origin_class == "imported_data":
        return "imported"
    if source.origin_class == "model_proposal":
        return "model-proposed"
    if source.actor_type == "user":
        return "user-created"
    return "system-generated"


def _authority_for_origin(origin: InstructionOriginClass) -> InstructionAuthorityClass:
    return _ORIGIN_AUTHORITY[origin]


def _require_source(source: object) -> InstructionSource:
    if not isinstance(source, InstructionSource):
        raise InstructionOriginValidationError("source must be a validated InstructionSource")
    return source


def _validate_record_ids(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str | bytes):
        raise InstructionOriginValidationError("record IDs must be a sequence")
    if len(values) > MAX_LIST_LIMIT:
        raise InstructionOriginValidationError(f"record ID list exceeds {MAX_LIST_LIMIT} entries")
    result = tuple(_validate_uuid("instruction record ID", value) for value in values)
    if len(set(result)) != len(result):
        raise InstructionOriginValidationError("record ID list contains duplicates")
    return result


def _validate_transformations(value: object) -> tuple[InstructionTransformation, ...]:
    if not isinstance(value, tuple | list):
        raise InstructionOriginValidationError("transformations must be a sequence")
    if len(value) > MAX_TRANSFORMATIONS:
        raise InstructionOriginValidationError(
            f"transformations exceed {MAX_TRANSFORMATIONS} entries"
        )
    result: list[InstructionTransformation] = []
    for item in value:
        if not isinstance(item, str) or item not in _ALLOWED_TRANSFORMATIONS:
            raise InstructionOriginValidationError("invalid instruction transformation")
        result.append(cast(InstructionTransformation, item))
    if len(set(result)) != len(result):
        raise InstructionOriginValidationError("transformations contain duplicates")
    return tuple(result)


def _validate_origin(value: object) -> InstructionOriginClass:
    if not isinstance(value, str) or value not in _ALLOWED_ORIGINS:
        raise InstructionOriginValidationError("invalid instruction origin class")
    return cast(InstructionOriginClass, value)


def _validate_authority(value: object) -> InstructionAuthorityClass:
    if not isinstance(value, str) or value not in _ALLOWED_AUTHORITIES:
        raise InstructionOriginValidationError("invalid instruction authority class")
    return cast(InstructionAuthorityClass, value)


def _validate_actor(value: object) -> InstructionActorType:
    if not isinstance(value, str) or value not in _ALLOWED_ACTORS:
        raise InstructionOriginValidationError("invalid instruction actor type")
    return cast(InstructionActorType, value)


def _validate_acquisition(value: object) -> InstructionAcquisitionMethod:
    if not isinstance(value, str) or value not in _ALLOWED_ACQUISITION:
        raise InstructionOriginValidationError("invalid instruction acquisition method")
    return cast(InstructionAcquisitionMethod, value)


def _validate_purpose(value: object) -> InstructionAuthorityPurpose:
    if not isinstance(value, str) or value not in _ALLOWED_PURPOSES:
        raise InstructionOriginValidationError("invalid instruction authority purpose")
    return cast(InstructionAuthorityPurpose, value)


def _validate_content(value: object) -> str:
    if not isinstance(value, str):
        raise InstructionOriginValidationError("instruction content must be a string")
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if not normalized:
        raise InstructionOriginValidationError("instruction content must not be blank")
    if len(normalized) > MAX_CONTENT_LENGTH:
        raise InstructionOriginValidationError(
            f"instruction content exceeds {MAX_CONTENT_LENGTH} characters"
        )
    if _CONTROL_PATTERN.search(normalized):
        raise InstructionOriginValidationError("instruction content contains control characters")
    try:
        _reject_secret_text(normalized)
        _reject_local_path(normalized)
    except Exception as exc:
        raise InstructionOriginValidationError("instruction content contains unsafe data") from exc
    return normalized


def _validate_text(name: str, value: object, maximum: int) -> str:
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise InstructionOriginValidationError(f"{name} must not be blank")
    if len(normalized) > maximum:
        raise InstructionOriginValidationError(f"{name} exceeds {maximum} characters")
    if _CONTROL_PATTERN.search(normalized):
        raise InstructionOriginValidationError(f"{name} contains control characters")
    try:
        _reject_secret_text(normalized)
        _reject_local_path(normalized)
    except Exception as exc:
        raise InstructionOriginValidationError(f"{name} contains unsafe data") from exc
    return normalized


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise InstructionOriginValidationError(f"{name} must not be blank")
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise InstructionOriginValidationError(f"{name} exceeds {MAX_IDENTIFIER_LENGTH} characters")
    if _CONTROL_PATTERN.search(normalized):
        raise InstructionOriginValidationError(f"{name} contains control characters")
    try:
        _reject_secret_text(normalized)
        _reject_local_path(normalized)
    except Exception as exc:
        raise InstructionOriginValidationError(f"{name} contains unsafe data") from exc
    return normalized


def _validate_optional_identifier(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _validate_identifier(name, value)


def _validate_optional_hash(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InstructionOriginValidationError("content hash must be a string")
    normalized = value.strip().lower()
    if _SHA256_PATTERN.fullmatch(normalized) is None:
        raise InstructionOriginValidationError("content hash must be a sha256 digest")
    return normalized


def _validate_optional_utc(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{name} must be a string or null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InstructionOriginValidationError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise InstructionOriginValidationError(f"{name} must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_optional_positive_int(name: str, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InstructionOriginValidationError(f"{name} must be a positive integer or null")
    return value


def _validate_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{name} must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise InstructionOriginValidationError(f"{name} must be a UUID string") from exc
    normalized = str(parsed)
    if normalized != value.lower():
        raise InstructionOriginValidationError(f"{name} must use canonical UUID form")
    return normalized


def _validate_optional_uuid(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _validate_uuid(name, value)


def _validate_operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _require_present(value: object, message: str) -> None:
    if value is None:
        raise InstructionOriginValidationError(message)


def _forbid_authority_reference(reference_id: object, revision: object) -> None:
    if reference_id is not None or revision is not None:
        raise InstructionOriginValidationError(
            "this origin class cannot assert an authority reference"
        )


def _audit_actor(actor: InstructionActorType) -> AuditActorType:
    if actor in {"retriever", "extractor", "importer", "unknown"}:
        return "system"
    if actor == "tool":
        return "capability"
    return cast(AuditActorType, actor)


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{key} is missing or invalid")
    return value


def _optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InstructionOriginValidationError(f"{key} is invalid")
    return value


def _optional_int(metadata: dict[str, object], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InstructionOriginValidationError(f"{key} is invalid")
    return value


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise InstructionOriginValidationError(f"{key} is not a list")
    return cast(list[object], value)


__all__ = [
    "ForbiddenInstructionMutationError",
    "InstructionAcquisitionMethod",
    "InstructionActorType",
    "InstructionAuthorityClass",
    "InstructionAuthorityDecision",
    "InstructionAuthorityPurpose",
    "InstructionContextBundle",
    "InstructionContextItem",
    "InstructionOriginClass",
    "InstructionOriginCorruptError",
    "InstructionOriginError",
    "InstructionOriginInfo",
    "InstructionOriginService",
    "InstructionOriginValidationError",
    "InstructionSource",
    "InstructionTransformation",
    "_instruction_origin_from_record",
    "_validate_instruction_origin_graph",
]
