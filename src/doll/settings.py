"""Authoritative preferences, policies, and scoped permission records."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    RecordSensitivity,
    RecordStatus,
    StaleRevisionError,
    StateCorruptError,
    _utc_now,
)
from doll.state_repository import (
    StateRepository,
    _validate_record_fields,
)
from doll.state_repository import (
    _serialize_metadata as _serialize_record_metadata,
)

PermissionMode = Literal["denied", "allow_once", "ask", "scoped"]
PermissionMutationActor = Literal["user", "model", "runtime", "capability", "system"]
PermissionConsumeActor = Literal["capability", "system"]

_ALLOWED_PERMISSION_MODES = frozenset({"denied", "allow_once", "ask", "scoped"})
_ALLOWED_MANAGEMENT_ACTORS = frozenset({"user"})
_ALLOWED_CONSUME_ACTORS = frozenset({"capability", "system"})
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SECRET_SCOPE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "credential",
        "credentials",
        "authorization",
        "cookie",
    }
)
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_MISSING = object()

MAX_KEY_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 500
MAX_POLICY_RULE_LENGTH = 2000
MAX_JSON_BYTES = 16 * 1024
MAX_SCOPE_BYTES = 4096
MAX_SCOPE_DEPTH = 8
MAX_SCOPE_STRING_LENGTH = 500
MAX_SETTINGS_LIMIT = 200


class SettingsError(RuntimeError):
    """Base class for authoritative settings failures."""


class SettingsValidationError(SettingsError):
    """Raised when a preference, policy, or permission is invalid."""


class DuplicateSettingError(SettingsError):
    """Raised when an active record already owns a stable identity."""


class ForbiddenPermissionMutationError(SettingsError):
    """Raised when a non-user path attempts to create or widen permission state."""


class PermissionDeniedError(SettingsError):
    """Raised when an allow-once record cannot be consumed."""


class SettingsCorruptError(SettingsError):
    """Raised when a typed setting record is malformed."""


@dataclass(frozen=True, slots=True)
class PreferenceInfo:
    record_id: str
    key: str
    value: object
    description: str | None
    revision: int
    status: RecordStatus
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PolicyInfo:
    record_id: str
    key: str
    rule: str
    enabled: bool
    revision: int
    status: RecordStatus
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    record_id: str
    capability_id: str
    scope: dict[str, object]
    mode: PermissionMode
    expires_at: str | None
    approval_source: str
    last_changed_at: str
    last_used_at: str | None
    remaining_uses: int | None
    revision: int
    status: RecordStatus
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    record_id: str | None
    capability_id: str
    scope: dict[str, object]
    effective_mode: PermissionMode
    reason: Literal["active", "expired", "consumed", "archived", "no_record"]


@dataclass(slots=True)
class PreferenceService:
    repository: StateRepository

    def create(
        self,
        *,
        key: str,
        value: object,
        description: str | None = None,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        actor_type: PermissionMutationActor = "user",
    ) -> PreferenceInfo:
        _require_user_management(actor_type)
        safe_key = _validate_key("preference key", key)
        safe_value = _validate_json_value(value, maximum=MAX_JSON_BYTES)
        safe_description = _validate_optional_text(
            "preference description", description, MAX_DESCRIPTION_LENGTH
        )
        metadata: dict[str, object] = {
            "preference_key": safe_key,
            "value": safe_value,
            "description": safe_description,
        }
        record_id = _create_typed_record(
            self.repository,
            record_type="preference",
            title=safe_key,
            metadata=metadata,
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="preference.create",
            identity=("preference_key", safe_key),
            audit_metadata={"preference_key": safe_key},
        )
        return self.get(record_id)

    def update(
        self,
        record_id: str,
        *,
        expected_revision: int,
        value: object,
        description: str | None = None,
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PreferenceInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "preference")
        metadata: dict[str, object] = {
            "preference_key": current.key,
            "value": _validate_json_value(value, maximum=MAX_JSON_BYTES),
            "description": _validate_optional_text(
                "preference description", description, MAX_DESCRIPTION_LENGTH
            ),
        }
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata=metadata,
            status=current.status,
            operation_id=operation_id,
            action="preference.update",
            audit_metadata={"preference_key": current.key},
        )
        return self.get(record_id)

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PreferenceInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "preference")
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata={
                "preference_key": current.key,
                "value": current.value,
                "description": current.description,
            },
            status="archived",
            operation_id=operation_id,
            action="preference.archive",
            audit_metadata={"preference_key": current.key},
        )
        return self.get(record_id)

    def get(self, record_id: str) -> PreferenceInfo:
        record = _require_record_type(self.repository, record_id, "preference")
        return _preference_from_record(record)

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[PreferenceInfo, ...]:
        return tuple(
            _preference_from_record(record)
            for record in _list_typed_records(
                self.repository, "preference", include_archived=include_archived, limit=limit
            )
        )


@dataclass(slots=True)
class PolicyService:
    repository: StateRepository

    def create(
        self,
        *,
        key: str,
        rule: str,
        enabled: bool = True,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        actor_type: PermissionMutationActor = "user",
    ) -> PolicyInfo:
        _require_user_management(actor_type)
        safe_key = _validate_key("policy key", key)
        safe_rule = _validate_text("policy rule", rule, MAX_POLICY_RULE_LENGTH)
        if not isinstance(enabled, bool):
            raise SettingsValidationError("policy enabled flag must be boolean")
        record_id = _create_typed_record(
            self.repository,
            record_type="policy",
            title=safe_key,
            metadata={"policy_key": safe_key, "rule": safe_rule, "enabled": enabled},
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="policy.create",
            identity=("policy_key", safe_key),
            audit_metadata={"policy_key": safe_key, "enabled": enabled},
        )
        return self.get(record_id)

    def update(
        self,
        record_id: str,
        *,
        expected_revision: int,
        rule: str,
        enabled: bool,
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PolicyInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "policy")
        safe_rule = _validate_text("policy rule", rule, MAX_POLICY_RULE_LENGTH)
        if not isinstance(enabled, bool):
            raise SettingsValidationError("policy enabled flag must be boolean")
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata={"policy_key": current.key, "rule": safe_rule, "enabled": enabled},
            status=current.status,
            operation_id=operation_id,
            action="policy.update",
            audit_metadata={"policy_key": current.key, "enabled": enabled},
        )
        return self.get(record_id)

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PolicyInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "policy")
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata={"policy_key": current.key, "rule": current.rule, "enabled": current.enabled},
            status="archived",
            operation_id=operation_id,
            action="policy.archive",
            audit_metadata={"policy_key": current.key},
        )
        return self.get(record_id)

    def get(self, record_id: str) -> PolicyInfo:
        return _policy_from_record(_require_record_type(self.repository, record_id, "policy"))

    def list(self, *, include_archived: bool = False, limit: int = 50) -> tuple[PolicyInfo, ...]:
        return tuple(
            _policy_from_record(record)
            for record in _list_typed_records(
                self.repository, "policy", include_archived=include_archived, limit=limit
            )
        )


@dataclass(slots=True)
class PermissionService:
    repository: StateRepository

    def create(
        self,
        *,
        capability_id: str,
        scope: dict[str, object],
        mode: PermissionMode,
        expires_at: str | None = None,
        approval_source: str = "management-cli",
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        actor_type: PermissionMutationActor = "user",
    ) -> PermissionInfo:
        _require_user_management(actor_type)
        safe_capability = _validate_key("capability ID", capability_id)
        safe_scope = _validate_scope(scope)
        safe_mode = _validate_permission_mode(mode, safe_scope)
        safe_expiration = _validate_optional_utc("permission expiration", expires_at)
        safe_approval_source = _validate_approval_source(approval_source)
        now = _utc_now()
        metadata = _permission_metadata(
            capability_id=safe_capability,
            scope=safe_scope,
            mode=safe_mode,
            expires_at=safe_expiration,
            approval_source=safe_approval_source,
            last_changed_at=now,
            last_used_at=None,
        )
        scope_identity = _canonical_json(safe_scope)
        record_id = _create_typed_record(
            self.repository,
            record_type="permission",
            title=safe_capability,
            metadata=metadata,
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="permission.create",
            identity=("permission_identity", f"{safe_capability}\0{scope_identity}"),
            audit_metadata={
                "capability_id": safe_capability,
                "mode": safe_mode,
                "scope_kind": safe_scope["kind"],
                "approval_source": safe_approval_source,
            },
        )
        return self.get(record_id)

    def update(
        self,
        record_id: str,
        *,
        expected_revision: int,
        mode: PermissionMode,
        expires_at: str | None = None,
        approval_source: str = "management-cli",
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PermissionInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "permission")
        safe_mode = _validate_permission_mode(mode, current.scope)
        safe_expiration = _validate_optional_utc("permission expiration", expires_at)
        safe_approval_source = _validate_approval_source(approval_source)
        metadata = _permission_metadata(
            capability_id=current.capability_id,
            scope=current.scope,
            mode=safe_mode,
            expires_at=safe_expiration,
            approval_source=safe_approval_source,
            last_changed_at=_utc_now(),
            last_used_at=None,
        )
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata=metadata,
            status=current.status,
            operation_id=operation_id,
            action="permission.update",
            audit_metadata={
                "capability_id": current.capability_id,
                "previous_mode": current.mode,
                "mode": safe_mode,
                "scope_kind": current.scope["kind"],
                "approval_source": safe_approval_source,
            },
        )
        return self.get(record_id)

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: PermissionMutationActor = "user",
    ) -> PermissionInfo:
        _require_user_management(actor_type)
        current = self.get(record_id)
        _require_active_record(current.status, "permission")
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata=_permission_metadata_from_info(current),
            status="archived",
            operation_id=operation_id,
            action="permission.archive",
            audit_metadata={
                "capability_id": current.capability_id,
                "mode": current.mode,
                "scope_kind": current.scope["kind"],
            },
        )
        return self.get(record_id)

    def consume_allow_once(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str,
        actor_type: PermissionConsumeActor = "capability",
    ) -> PermissionInfo:
        if actor_type not in _ALLOWED_CONSUME_ACTORS:
            raise ForbiddenPermissionMutationError(
                "only the capability broker or core system may consume allow-once permission"
            )
        current = self.get(record_id)
        decision = _decision_from_permission(current)
        if decision.effective_mode != "allow_once":
            raise PermissionDeniedError(f"allow-once permission is unavailable: {decision.reason}")
        now = _utc_now()
        metadata = _permission_metadata(
            capability_id=current.capability_id,
            scope=current.scope,
            mode="denied",
            expires_at=current.expires_at,
            approval_source=current.approval_source,
            last_changed_at=now,
            last_used_at=now,
            remaining_uses=0,
        )
        _update_typed_record(
            self.repository,
            current_record=self.repository.get_record(record_id),
            expected_revision=expected_revision,
            metadata=metadata,
            status=current.status,
            operation_id=operation_id,
            action="permission.consume_once",
            audit_actor_type=actor_type,
            audit_metadata={
                "capability_id": current.capability_id,
                "previous_mode": "allow_once",
                "mode": "denied",
                "scope_kind": current.scope["kind"],
            },
        )
        return self.get(record_id)

    def get(self, record_id: str) -> PermissionInfo:
        record = _require_record_type(self.repository, record_id, "permission")
        return _permission_from_record(record)

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[PermissionInfo, ...]:
        return tuple(
            _permission_from_record(record)
            for record in _list_typed_records(
                self.repository, "permission", include_archived=include_archived, limit=limit
            )
        )

    def effective(self, record_id: str) -> PermissionDecision:
        return _decision_from_permission(self.get(record_id))

    def resolve(self, *, capability_id: str, scope: dict[str, object]) -> PermissionDecision:
        safe_capability = _validate_key("capability ID", capability_id)
        safe_scope = _validate_scope(scope)
        matching: list[PermissionInfo] = []
        for record in _list_all_typed_records(
            self.repository,
            "permission",
            include_archived=False,
        ):
            permission = _permission_from_record(record)
            if permission.capability_id == safe_capability and permission.scope == safe_scope:
                matching.append(permission)
        if not matching:
            return PermissionDecision(
                record_id=None,
                capability_id=safe_capability,
                scope=safe_scope,
                effective_mode="denied",
                reason="no_record",
            )
        if len(matching) != 1:
            raise StateCorruptError("multiple active permission records share one identity")
        return _decision_from_permission(matching[0])


def _create_typed_record(
    repository: StateRepository,
    *,
    record_type: str,
    title: str,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    action: str,
    identity: tuple[str, str],
    audit_metadata: dict[str, object],
) -> str:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type=record_type,
        schema_version=1,
        status="active",
        provenance="user-created",
        sensitivity=sensitivity,
    )
    safe_operation_id = _validate_operation_id(operation_id)
    record_id = str(uuid4())
    now = _utc_now()
    metadata_json = _serialize_record_metadata(metadata)
    connection = repository.connection

    connection.execute("BEGIN IMMEDIATE")
    try:
        _assert_unique_active_identity(
            repository, record_type=record_type, identity=identity, exclude_id=None
        )
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at, revision,
                status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, ?, 1, ?, ?, 1, 'active', 'user-created', ?, ?, ?)
            """,
            (record_id, record_type, now, now, sensitivity, title, metadata_json),
        )
        _insert_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type="user",
            action=action,
            target_type=record_type,
            target_id=record_id,
            metadata=audit_metadata,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("settings record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    repository._sync_after_commit(state_revision)
    return record_id


def _update_typed_record(
    repository: StateRepository,
    *,
    current_record: RecordEnvelope,
    expected_revision: int,
    metadata: dict[str, object],
    status: RecordStatus,
    operation_id: str | None,
    action: str,
    audit_metadata: dict[str, object],
    audit_actor_type: str = "user",
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    safe_operation_id = _validate_operation_id(operation_id)
    metadata_json = _serialize_record_metadata(metadata)
    now = _utc_now()
    connection = repository.connection

    connection.execute("BEGIN IMMEDIATE")
    try:
        refreshed = repository.get_record(current_record.id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = ?, metadata_json = ?
            WHERE id = ? AND revision = ?
            """,
            (now, status, metadata_json, current_record.id, expected_revision),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("record revision changed during update")
        _insert_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type=audit_actor_type,
            action=action,
            target_type=current_record.record_type,
            target_id=current_record.id,
            metadata=audit_metadata,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("settings record could not be updated") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    repository._sync_after_commit(state_revision)


def _insert_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    actor_type: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, object],
) -> None:
    safe_action = _validate_audit_token("action", action, 120)
    metadata_json = _serialize_audit_metadata(metadata)
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            actor_type,
            safe_action,
            target_type,
            target_id,
            f"Changed {target_type} record",
            metadata_json,
        ),
    )


def _assert_unique_active_identity(
    repository: StateRepository,
    *,
    record_type: str,
    identity: tuple[str, str],
    exclude_id: str | None,
) -> None:
    field, expected = identity
    actual: str | None
    for record in _list_all_typed_records(
        repository,
        record_type,
        include_archived=False,
    ):
        if exclude_id is not None and record.id == exclude_id:
            continue
        if record_type == "permission":
            permission = _permission_from_record(record)
            actual = f"{permission.capability_id}\0{_canonical_json(permission.scope)}"
        else:
            raw = record.metadata.get(field)
            actual = raw if isinstance(raw, str) else None
        if actual == expected:
            raise DuplicateSettingError(f"active {record_type} identity already exists")


def _list_all_typed_records(
    repository: StateRepository,
    record_type: str,
    *,
    include_archived: bool,
) -> tuple[RecordEnvelope, ...]:
    status_clause = "" if include_archived else "AND status = 'active'"
    try:
        rows = repository.connection.execute(
            f"""
            SELECT id
            FROM records
            WHERE record_type = ? {status_clause}
            ORDER BY created_at DESC, id DESC
            """,
            (record_type,),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StateCorruptError(f"{record_type} records are unreadable") from exc
    return tuple(repository.get_record(cast(str, row[0])) for row in rows)


def _list_typed_records(
    repository: StateRepository,
    record_type: str,
    *,
    include_archived: bool,
    limit: int,
) -> tuple[RecordEnvelope, ...]:
    if limit < 1 or limit > MAX_SETTINGS_LIMIT:
        raise SettingsValidationError(
            f"settings list limit must be between 1 and {MAX_SETTINGS_LIMIT}"
        )
    status_clause = "" if include_archived else "AND status = 'active'"
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
    return tuple(repository.get_record(cast(str, row[0])) for row in rows)


def _require_record_type(
    repository: StateRepository, record_id: str, expected_type: str
) -> RecordEnvelope:
    record = repository.get_record(record_id)
    if record.record_type != expected_type:
        raise KeyError(record_id)
    return record


def _require_user_management(actor_type: PermissionMutationActor) -> None:
    if actor_type not in _ALLOWED_MANAGEMENT_ACTORS:
        raise ForbiddenPermissionMutationError(
            "permission and policy management requires an explicit user-controlled actor"
        )


def _require_active_record(status: RecordStatus, record_type: str) -> None:
    if status != "active":
        raise SettingsValidationError(f"archived {record_type} record cannot be changed")


def _validate_key(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise SettingsValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_KEY_LENGTH:
        raise SettingsValidationError(f"{name} is empty or too long")
    if not _KEY_PATTERN.fullmatch(normalized):
        raise SettingsValidationError(f"{name} contains unsupported characters")
    return normalized


def _validate_text(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise SettingsValidationError(f"{name} must be text")
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if not normalized or len(normalized) > maximum:
        raise SettingsValidationError(f"{name} is empty or too long")
    if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
        raise SettingsValidationError(f"{name} contains control characters")
    return normalized


def _validate_optional_text(name: str, value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    return _validate_text(name, value, maximum)


def _validate_json_value(value: object, *, maximum: int) -> object:
    _validate_nested_json(value, depth=0, scope=False)
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SettingsValidationError("setting value must be JSON-compatible") from exc
    if len(encoded.encode("utf-8")) > maximum:
        raise SettingsValidationError(f"setting JSON exceeds {maximum} bytes")
    return json.loads(encoded)


def _validate_scope(scope: dict[str, object]) -> dict[str, object]:
    if not isinstance(scope, dict):
        raise SettingsValidationError("permission scope must be a JSON object")
    normalized = cast(dict[str, object], _validate_json_value(scope, maximum=MAX_SCOPE_BYTES))
    kind = normalized.get("kind")
    if not isinstance(kind, str):
        raise SettingsValidationError("permission scope requires a text kind")
    normalized["kind"] = _validate_key("permission scope kind", kind)
    return normalized


def _validate_nested_json(value: object, *, depth: int, scope: bool) -> None:
    if depth > MAX_SCOPE_DEPTH:
        raise SettingsValidationError("setting JSON nesting is too deep")
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or not key:
                raise SettingsValidationError("setting JSON keys must be non-empty strings")
            normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized_key in _SECRET_SCOPE_KEYS:
                raise SettingsValidationError("setting JSON contains a secret-like key")
            _validate_nested_json(nested, depth=depth + 1, scope=scope)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_nested_json(nested, depth=depth + 1, scope=scope)
        return
    if isinstance(value, str):
        if len(value) > MAX_SCOPE_STRING_LENGTH:
            raise SettingsValidationError("setting JSON string is too long")
        if any(ord(character) < 32 for character in value):
            raise SettingsValidationError("setting JSON string contains control characters")
        if value.startswith("/") or _DRIVE_PATH_PATTERN.match(value):
            raise SettingsValidationError("setting JSON must not contain an absolute local path")
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise SettingsValidationError("setting value must be JSON-compatible")


def _validate_permission_mode(mode: str, scope: dict[str, object]) -> PermissionMode:
    if mode not in _ALLOWED_PERMISSION_MODES:
        raise SettingsValidationError(f"invalid permission mode: {mode}")
    safe_mode = cast(PermissionMode, mode)
    if safe_mode == "scoped":
        if scope.get("kind") == "global" or len(scope) < 2:
            raise SettingsValidationError(
                "scoped permission requires a non-global scope with at least one constraint"
            )
    return safe_mode


def _validate_approval_source(value: str) -> str:
    safe = _validate_key("approval source", value)
    if safe not in {"management-cli", "management-ui"}:
        raise ForbiddenPermissionMutationError(
            "approval source must be a user-controlled management interface"
        )
    return safe


def _validate_optional_utc(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SettingsValidationError(f"{name} must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SettingsValidationError(f"{name} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise SettingsValidationError(f"{name} must be UTC")
    return value


def _validate_operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def _permission_metadata(
    *,
    capability_id: str,
    scope: dict[str, object],
    mode: PermissionMode,
    expires_at: str | None,
    approval_source: str,
    last_changed_at: str,
    last_used_at: str | None,
    remaining_uses: int | None | object = _MISSING,
) -> dict[str, object]:
    uses: int | None
    if remaining_uses is _MISSING:
        uses = 1 if mode == "allow_once" else None
    else:
        uses = cast(int | None, remaining_uses)
    return {
        "capability_id": capability_id,
        "scope": scope,
        "mode": mode,
        "expires_at": expires_at,
        "approval_source": approval_source,
        "last_changed_at": last_changed_at,
        "last_used_at": last_used_at,
        "remaining_uses": uses,
        "permission_identity": f"{capability_id}\0{_canonical_json(scope)}",
    }


def _permission_metadata_from_info(info: PermissionInfo) -> dict[str, object]:
    return _permission_metadata(
        capability_id=info.capability_id,
        scope=info.scope,
        mode=info.mode,
        expires_at=info.expires_at,
        approval_source=info.approval_source,
        last_changed_at=info.last_changed_at,
        last_used_at=info.last_used_at,
        remaining_uses=info.remaining_uses,
    )


def _preference_from_record(record: RecordEnvelope) -> PreferenceInfo:
    try:
        key = _validate_key("preference key", _required_string(record.metadata, "preference_key"))
        value = _validate_json_value(record.metadata["value"], maximum=MAX_JSON_BYTES)
        description = _optional_string(record.metadata, "description")
        if description is not None:
            description = _validate_text(
                "preference description", description, MAX_DESCRIPTION_LENGTH
            )
    except (KeyError, SettingsValidationError, TypeError, ValueError) as exc:
        raise SettingsCorruptError("preference record is malformed") from exc
    return PreferenceInfo(
        record_id=record.id,
        key=key,
        value=value,
        description=description,
        revision=record.revision,
        status=record.status,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _policy_from_record(record: RecordEnvelope) -> PolicyInfo:
    try:
        key = _validate_key("policy key", _required_string(record.metadata, "policy_key"))
        rule = _validate_text(
            "policy rule", _required_string(record.metadata, "rule"), MAX_POLICY_RULE_LENGTH
        )
        enabled = record.metadata["enabled"]
        if not isinstance(enabled, bool):
            raise SettingsValidationError("policy enabled flag must be boolean")
    except (KeyError, SettingsValidationError, TypeError, ValueError) as exc:
        raise SettingsCorruptError("policy record is malformed") from exc
    return PolicyInfo(
        record_id=record.id,
        key=key,
        rule=rule,
        enabled=enabled,
        revision=record.revision,
        status=record.status,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _permission_from_record(record: RecordEnvelope) -> PermissionInfo:
    try:
        capability_id = _validate_key(
            "capability ID", _required_string(record.metadata, "capability_id")
        )
        raw_scope = record.metadata["scope"]
        if not isinstance(raw_scope, dict):
            raise SettingsValidationError("permission scope must be an object")
        scope = _validate_scope(cast(dict[str, object], raw_scope))
        mode = _validate_permission_mode(_required_string(record.metadata, "mode"), scope)
        expires_at = _validate_optional_utc(
            "permission expiration", _optional_string(record.metadata, "expires_at")
        )
        approval_source = _validate_approval_source(
            _required_string(record.metadata, "approval_source")
        )
        raw_last_changed_at = _required_string(record.metadata, "last_changed_at")
        validated_last_changed_at = _validate_optional_utc(
            "permission changed time",
            raw_last_changed_at,
        )
        if validated_last_changed_at is None:
            raise SettingsValidationError("permission changed time is missing")
        last_changed_at: str = validated_last_changed_at
        last_used_at = _validate_optional_utc(
            "permission used time", _optional_string(record.metadata, "last_used_at")
        )
        remaining_uses = record.metadata.get("remaining_uses")
        if remaining_uses is not None and (
            not isinstance(remaining_uses, int)
            or isinstance(remaining_uses, bool)
            or remaining_uses not in {0, 1}
        ):
            raise SettingsValidationError("permission remaining uses is invalid")
        expected_identity = f"{capability_id}\0{_canonical_json(scope)}"
        if record.metadata.get("permission_identity") != expected_identity:
            raise SettingsValidationError("permission identity is inconsistent")
        if mode == "allow_once" and remaining_uses != 1:
            raise SettingsValidationError("active allow-once permission must have one use")
    except (
        KeyError,
        SettingsValidationError,
        ForbiddenPermissionMutationError,
        TypeError,
        ValueError,
        AssertionError,
    ) as exc:
        raise SettingsCorruptError("permission record is malformed") from exc
    return PermissionInfo(
        record_id=record.id,
        capability_id=capability_id,
        scope=scope,
        mode=mode,
        expires_at=expires_at,
        approval_source=approval_source,
        last_changed_at=last_changed_at,
        last_used_at=last_used_at,
        remaining_uses=remaining_uses,
        revision=record.revision,
        status=record.status,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _decision_from_permission(permission: PermissionInfo) -> PermissionDecision:
    if permission.status != "active":
        return PermissionDecision(
            record_id=permission.record_id,
            capability_id=permission.capability_id,
            scope=permission.scope,
            effective_mode="denied",
            reason="archived",
        )
    if permission.expires_at is not None:
        expires = datetime.fromisoformat(permission.expires_at[:-1] + "+00:00")
        if expires <= datetime.now(UTC):
            return PermissionDecision(
                record_id=permission.record_id,
                capability_id=permission.capability_id,
                scope=permission.scope,
                effective_mode="denied",
                reason="expired",
            )
    if permission.mode == "allow_once" and permission.remaining_uses != 1:
        return PermissionDecision(
            record_id=permission.record_id,
            capability_id=permission.capability_id,
            scope=permission.scope,
            effective_mode="denied",
            reason="consumed",
        )
    return PermissionDecision(
        record_id=permission.record_id,
        capability_id=permission.capability_id,
        scope=permission.scope,
        effective_mode=permission.mode,
        reason="active",
    )


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise SettingsValidationError(f"{key} is missing or invalid")
    return value


def _optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SettingsValidationError(f"{key} is invalid")
    return value
