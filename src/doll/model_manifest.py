"""Authoritative local runtime, model, and explicit binding records."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
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
from doll.state_repository import StateRepository, _serialize_metadata, _validate_record_fields

ManifestActor = Literal["user", "model", "runtime", "importer", "system"]
ManifestState = Literal[
    "draft",
    "candidate",
    "verified",
    "quarantined",
    "deprecated",
    "unavailable",
]
LicenseReviewState = Literal[
    "unreviewed",
    "reviewed_compatible",
    "reviewed_restricted",
    "rejected",
]
BindingState = Literal[
    "candidate",
    "active",
    "previous",
    "fallback",
    "disabled",
    "rolled_back",
]
SmokeTestStatus = Literal["not_run", "passed", "failed"]

RUNTIME_MANIFEST_SCHEMA_VERSION = 1
MODEL_MANIFEST_SCHEMA_VERSION = 1
MODEL_BINDING_SCHEMA_VERSION = 1

_RUNTIME_TYPE = "runtime_manifest"
_MODEL_TYPE = "model_manifest"
_BINDING_TYPE = "model_binding"
_MANIFEST_STATES = frozenset(
    {"draft", "candidate", "verified", "quarantined", "deprecated", "unavailable"}
)
_LICENSE_STATES = frozenset(
    {"unreviewed", "reviewed_compatible", "reviewed_restricted", "rejected"}
)
_BINDING_STATES = frozenset(
    {"candidate", "active", "previous", "fallback", "disabled", "rolled_back"}
)
_SMOKE_STATES = frozenset({"not_run", "passed", "failed"})
_ALLOWED_OPERATIONS = frozenset({"health", "inventory", "generate", "stream", "cancel"})
_TRUSTED_PROVENANCE = frozenset({"user-created", "user-confirmed"})
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,199}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHECKSUM = re.compile(r"^[0-9a-f]{16,256}$")
_PRIVATE_PATH = re.compile(r"(?:/Users/|/home/|/private/|[A-Za-z]:[\\/])")
_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")

_MAX_TEXT = 500
_MAX_DISPLAY = 240
_MAX_LIST = 128
_MAX_REFERENCES = 128
_MAX_CAPABILITIES = 128
_MAX_CHECKSUMS = 8
_MAX_LIST_LIMIT = 500

_RUNTIME_KEYS = frozenset(
    {
        "adapter_id",
        "adapter_version",
        "runtime_class",
        "connection_kind",
        "runtime_version",
        "declaration_fingerprint",
        "operations",
        "offline_capable",
        "cloud_fallback",
        "automatic_download",
        "platforms",
        "compatibility",
        "source_references",
        "manifest_state",
        "verification_evidence_ids",
        "quarantine_reason",
    }
)
_MODEL_KEYS = frozenset(
    {
        "runtime_manifest_id",
        "runtime_private_locator",
        "display_name",
        "exact_revision",
        "checksums",
        "source_references",
        "license_id",
        "license_review_state",
        "model_format",
        "size_bytes",
        "context_limit",
        "capabilities",
        "platforms",
        "compatibility",
        "manifest_state",
        "verification_evidence_ids",
        "quarantine_reason",
    }
)
_BINDING_KEYS = frozenset(
    {
        "scope_type",
        "scope_key",
        "runtime_manifest_id",
        "runtime_manifest_revision",
        "model_manifest_id",
        "model_manifest_revision",
        "binding_state",
        "activated_at",
        "activation_evidence_ids",
        "previous_binding_id",
        "fallback_priority",
        "fallback_eligible",
        "rollback_target_id",
        "rollback_reason",
        "smoke_test_status",
    }
)


class ModelManifestError(StateError):
    """Base class for runtime, model, and binding failures."""


class ModelManifestValidationError(ModelManifestError):
    """Raised when requested manifest or binding data is invalid."""


class ModelManifestCorruptError(ModelManifestError):
    """Raised when persisted manifest or binding data is malformed."""


@dataclass(frozen=True, slots=True)
class RuntimeManifestInfo:
    runtime_manifest_id: str
    label: str
    adapter_id: str
    adapter_version: str
    runtime_class: str
    connection_kind: str
    runtime_version: str | None
    declaration_fingerprint: str
    operations: tuple[str, ...]
    offline_capable: bool
    cloud_fallback: bool
    automatic_download: bool
    platforms: tuple[str, ...]
    compatibility: tuple[str, ...]
    source_references: tuple[str, ...]
    manifest_state: ManifestState
    verification_evidence_ids: tuple[str, ...]
    quarantine_reason: str | None
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ModelManifestInfo:
    model_manifest_id: str
    runtime_manifest_id: str
    runtime_private_locator: str
    display_name: str
    exact_revision: str
    checksums: tuple[tuple[str, str], ...]
    source_references: tuple[str, ...]
    license_id: str
    license_review_state: LicenseReviewState
    model_format: str
    size_bytes: int | None
    context_limit: int | None
    capabilities: tuple[str, ...]
    platforms: tuple[str, ...]
    compatibility: tuple[str, ...]
    manifest_state: ManifestState
    verification_evidence_ids: tuple[str, ...]
    quarantine_reason: str | None
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ModelBindingInfo:
    binding_id: str
    scope_type: str
    scope_key: str
    runtime_manifest_id: str
    runtime_manifest_revision: int
    model_manifest_id: str
    model_manifest_revision: int
    binding_state: BindingState
    activated_at: str | None
    activation_evidence_ids: tuple[str, ...]
    previous_binding_id: str | None
    fallback_priority: int | None
    fallback_eligible: bool
    rollback_target_id: str | None
    rollback_reason: str | None
    smoke_test_status: SmokeTestStatus
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ModelManifestService:
    repository: StateRepository

    def create_runtime(
        self,
        *,
        label: str,
        adapter_id: str,
        adapter_version: str,
        runtime_class: str,
        connection_kind: str,
        operations: Sequence[str],
        offline_capable: bool,
        cloud_fallback: bool,
        automatic_download: bool,
        runtime_version: str | None = None,
        platforms: Sequence[str] = (),
        compatibility: Sequence[str] = (),
        source_references: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> RuntimeManifestInfo:
        record_id = str(uuid4())
        safe_adapter_id = _token("adapter ID", adapter_id)
        safe_adapter_version = _token("adapter version", adapter_version)
        safe_runtime_class = _token("runtime class", runtime_class)
        safe_connection = _token("connection kind", connection_kind)
        safe_operations = _tokens("operations", operations, allowed=_ALLOWED_OPERATIONS)
        metadata: dict[str, object] = {
            "adapter_id": safe_adapter_id,
            "adapter_version": safe_adapter_version,
            "runtime_class": safe_runtime_class,
            "connection_kind": safe_connection,
            "runtime_version": _optional_token("runtime version", runtime_version),
            "declaration_fingerprint": _runtime_fingerprint(
                safe_adapter_id,
                safe_adapter_version,
                safe_runtime_class,
                safe_connection,
                safe_operations,
                offline_capable,
                cloud_fallback,
                automatic_download,
            ),
            "operations": list(safe_operations),
            "offline_capable": _bool("offline capable", offline_capable),
            "cloud_fallback": _bool("cloud fallback", cloud_fallback),
            "automatic_download": _bool("automatic download", automatic_download),
            "platforms": list(_tokens("platforms", platforms)),
            "compatibility": list(_tokens("compatibility", compatibility)),
            "source_references": list(_references(source_references)),
            "manifest_state": "candidate",
            "verification_evidence_ids": [],
            "quarantine_reason": None,
        }
        _create_record(
            self.repository,
            record_id=record_id,
            record_type=_RUNTIME_TYPE,
            title=_text("runtime label", label, _MAX_DISPLAY),
            metadata=metadata,
            sensitivity=sensitivity,
            provenance=_actor_provenance(actor_type),
            actor_type=actor_type,
            action="runtime_manifest.create",
            operation_id=operation_id,
        )
        return self.get_runtime(record_id)

    def create_model(
        self,
        *,
        runtime_manifest_id: str,
        runtime_private_locator: str,
        display_name: str,
        exact_revision: str,
        checksums: Mapping[str, str],
        license_id: str,
        model_format: str,
        size_bytes: int | None = None,
        context_limit: int | None = None,
        capabilities: Sequence[str] = (),
        platforms: Sequence[str] = (),
        compatibility: Sequence[str] = (),
        source_references: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        runtime = self.get_runtime(runtime_manifest_id)
        if runtime.lifecycle_status != "active":
            raise ModelManifestValidationError("runtime manifest is archived")
        record_id = str(uuid4())
        metadata: dict[str, object] = {
            "runtime_manifest_id": runtime.runtime_manifest_id,
            "runtime_private_locator": _locator(runtime_private_locator),
            "display_name": _text("model display name", display_name, _MAX_DISPLAY),
            "exact_revision": _text("exact model revision", exact_revision, _MAX_TEXT),
            "checksums": [
                {"algorithm": algorithm, "value": value}
                for algorithm, value in _checksums(checksums)
            ],
            "source_references": list(_references(source_references)),
            "license_id": _token("license ID", license_id),
            "license_review_state": "unreviewed",
            "model_format": _token("model format", model_format),
            "size_bytes": _optional_positive_int("model size", size_bytes),
            "context_limit": _optional_positive_int("context limit", context_limit),
            "capabilities": list(_tokens("capabilities", capabilities)),
            "platforms": list(_tokens("platforms", platforms)),
            "compatibility": list(_tokens("compatibility", compatibility)),
            "manifest_state": "candidate",
            "verification_evidence_ids": [],
            "quarantine_reason": None,
        }
        _create_record(
            self.repository,
            record_id=record_id,
            record_type=_MODEL_TYPE,
            title=cast(str, metadata["display_name"]),
            metadata=metadata,
            sensitivity=sensitivity,
            provenance=_actor_provenance(actor_type),
            actor_type=actor_type,
            action="model_manifest.create",
            operation_id=operation_id,
        )
        return self.get_model(record_id)

    def create_binding(
        self,
        *,
        scope_type: str,
        scope_key: str,
        runtime_manifest_id: str,
        model_manifest_id: str,
        smoke_test_status: SmokeTestStatus = "not_run",
        sensitivity: RecordSensitivity = "personal",
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        runtime = self.get_runtime(runtime_manifest_id)
        model = self.get_model(model_manifest_id)
        if model.runtime_manifest_id != runtime.runtime_manifest_id:
            raise ModelManifestValidationError("model manifest belongs to another runtime")
        record_id = str(uuid4())
        metadata: dict[str, object] = {
            "scope_type": _token("binding scope type", scope_type),
            "scope_key": _scope_key(scope_key),
            "runtime_manifest_id": runtime.runtime_manifest_id,
            "runtime_manifest_revision": runtime.revision,
            "model_manifest_id": model.model_manifest_id,
            "model_manifest_revision": model.revision,
            "binding_state": "candidate",
            "activated_at": None,
            "activation_evidence_ids": [],
            "previous_binding_id": None,
            "fallback_priority": None,
            "fallback_eligible": False,
            "rollback_target_id": None,
            "rollback_reason": None,
            "smoke_test_status": _smoke_state(smoke_test_status),
        }
        _create_record(
            self.repository,
            record_id=record_id,
            record_type=_BINDING_TYPE,
            title=f"{metadata['scope_type']}:{metadata['scope_key']}",
            metadata=metadata,
            sensitivity=sensitivity,
            provenance=_actor_provenance(actor_type),
            actor_type=actor_type,
            action="model_binding.create",
            operation_id=operation_id,
        )
        return self.get_binding(record_id)

    def get_runtime(self, record_id: str) -> RuntimeManifestInfo:
        return _runtime_from_record(_require_record(self.repository, record_id, _RUNTIME_TYPE))

    def get_model(self, record_id: str) -> ModelManifestInfo:
        return _model_from_record(_require_record(self.repository, record_id, _MODEL_TYPE))

    def get_binding(self, record_id: str) -> ModelBindingInfo:
        return _binding_from_record(_require_record(self.repository, record_id, _BINDING_TYPE))

    def list_runtimes(
        self, *, include_archived: bool = False, limit: int = 100
    ) -> tuple[RuntimeManifestInfo, ...]:
        return tuple(
            cast(RuntimeManifestInfo, item)
            for item in self._list(_RUNTIME_TYPE, include_archived, limit)
        )

    def list_models(
        self, *, include_archived: bool = False, limit: int = 100
    ) -> tuple[ModelManifestInfo, ...]:
        return tuple(
            cast(ModelManifestInfo, item)
            for item in self._list(_MODEL_TYPE, include_archived, limit)
        )

    def list_bindings(
        self, *, include_archived: bool = False, limit: int = 100
    ) -> tuple[ModelBindingInfo, ...]:
        return tuple(
            cast(ModelBindingInfo, item)
            for item in self._list(_BINDING_TYPE, include_archived, limit)
        )

    def _list(self, record_type: str, include_archived: bool, limit: int) -> tuple[object, ...]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= _MAX_LIST_LIMIT
        ):
            raise ModelManifestValidationError("manifest list limit is invalid")
        rows = self.repository.connection.execute(
            "SELECT id FROM records WHERE record_type = ? ORDER BY created_at, id",
            (record_type,),
        ).fetchall()
        result: list[object] = []
        for row in rows:
            record = self.repository.get_record(cast(str, row[0]))
            if not include_archived and record.status != "active":
                continue
            parser = {
                _RUNTIME_TYPE: _runtime_from_record,
                _MODEL_TYPE: _model_from_record,
                _BINDING_TYPE: _binding_from_record,
            }[record_type]
            result.append(parser(record))
            if len(result) >= limit:
                break
        return tuple(result)

    def verify_runtime(
        self,
        runtime_manifest_id: str,
        *,
        expected_revision: int,
        evidence_ids: Sequence[str] = (),
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> RuntimeManifestInfo:
        _require_user(actor_type, "runtime verification")
        current = self.get_runtime(runtime_manifest_id)
        if current.manifest_state not in {"draft", "candidate"}:
            raise ModelManifestValidationError("runtime manifest cannot be verified from its state")
        if not current.offline_capable or current.cloud_fallback or current.automatic_download:
            raise ModelManifestValidationError("runtime declaration is not local-only")
        metadata = dict(
            _require_record(self.repository, runtime_manifest_id, _RUNTIME_TYPE).metadata
        )
        metadata["manifest_state"] = "verified"
        metadata["verification_evidence_ids"] = list(_evidence_ids(self.repository, evidence_ids))
        metadata["quarantine_reason"] = None
        _update_one(
            self.repository,
            record_id=runtime_manifest_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="runtime_manifest.verify",
            operation_id=operation_id,
        )
        return self.get_runtime(runtime_manifest_id)

    def review_model_license(
        self,
        model_manifest_id: str,
        *,
        expected_revision: int,
        review_state: LicenseReviewState,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        _require_user(actor_type, "model license review")
        if review_state == "unreviewed":
            raise ModelManifestValidationError("license review cannot be reset to unreviewed")
        current = self.get_model(model_manifest_id)
        if current.manifest_state not in {"draft", "candidate"}:
            raise ModelManifestValidationError(
                "verified or inactive model license review is immutable"
            )
        record = _require_record(self.repository, model_manifest_id, _MODEL_TYPE)
        metadata = dict(record.metadata)
        metadata["license_review_state"] = _license_state(review_state)
        _update_one(
            self.repository,
            record_id=model_manifest_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="model_manifest.review_license",
            operation_id=operation_id,
        )
        return self.get_model(model_manifest_id)

    def verify_model(
        self,
        model_manifest_id: str,
        *,
        expected_revision: int,
        evidence_ids: Sequence[str] = (),
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        _require_user(actor_type, "model verification")
        current = self.get_model(model_manifest_id)
        if current.manifest_state not in {"draft", "candidate"}:
            raise ModelManifestValidationError("model manifest cannot be verified from its state")
        runtime = self.get_runtime(current.runtime_manifest_id)
        if runtime.lifecycle_status != "active" or runtime.manifest_state != "verified":
            raise ModelManifestValidationError("model runtime is not verified")
        if current.license_review_state not in {"reviewed_compatible", "reviewed_restricted"}:
            raise ModelManifestValidationError("model license has not been accepted for use")
        if (
            current.platforms
            and runtime.platforms
            and not set(current.platforms).intersection(runtime.platforms)
        ):
            raise ModelManifestValidationError("model and runtime platforms are incompatible")
        metadata = dict(_require_record(self.repository, model_manifest_id, _MODEL_TYPE).metadata)
        metadata["manifest_state"] = "verified"
        metadata["verification_evidence_ids"] = list(_evidence_ids(self.repository, evidence_ids))
        metadata["quarantine_reason"] = None
        _update_one(
            self.repository,
            record_id=model_manifest_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="model_manifest.verify",
            operation_id=operation_id,
        )
        return self.get_model(model_manifest_id)

    def quarantine_runtime(
        self,
        runtime_manifest_id: str,
        *,
        expected_revision: int,
        reason: str,
        actor_type: ManifestActor = "system",
        operation_id: str | None = None,
    ) -> RuntimeManifestInfo:
        _require_quarantine_actor(actor_type)
        self._quarantine(
            runtime_manifest_id, _RUNTIME_TYPE, expected_revision, reason, actor_type, operation_id
        )
        return self.get_runtime(runtime_manifest_id)

    def quarantine_model(
        self,
        model_manifest_id: str,
        *,
        expected_revision: int,
        reason: str,
        actor_type: ManifestActor = "system",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        _require_quarantine_actor(actor_type)
        self._quarantine(
            model_manifest_id, _MODEL_TYPE, expected_revision, reason, actor_type, operation_id
        )
        return self.get_model(model_manifest_id)

    def _quarantine(
        self,
        record_id: str,
        record_type: str,
        expected_revision: int,
        reason: str,
        actor_type: ManifestActor,
        operation_id: str | None,
    ) -> None:
        record = _require_record(self.repository, record_id, record_type)
        self._require_no_selectable_bindings(record_id, record_type)
        metadata = dict(record.metadata)
        metadata["manifest_state"] = "quarantined"
        metadata["quarantine_reason"] = _text("quarantine reason", reason, _MAX_TEXT)
        _update_one(
            self.repository,
            record_id=record_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed" if actor_type == "user" else "system-generated",
            actor_type=actor_type,
            action=f"{record_type}.quarantine",
            operation_id=operation_id,
        )

    def deprecate_runtime(
        self,
        runtime_manifest_id: str,
        *,
        expected_revision: int,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> RuntimeManifestInfo:
        _require_user(actor_type, "runtime deprecation")
        self._set_manifest_inactive(
            runtime_manifest_id,
            _RUNTIME_TYPE,
            expected_revision,
            "deprecated",
            actor_type,
            operation_id,
        )
        return self.get_runtime(runtime_manifest_id)

    def mark_runtime_unavailable(
        self,
        runtime_manifest_id: str,
        *,
        expected_revision: int,
        actor_type: ManifestActor = "system",
        operation_id: str | None = None,
    ) -> RuntimeManifestInfo:
        if actor_type not in {"user", "system"}:
            raise ModelManifestValidationError(
                "runtime unavailability requires user or system authority"
            )
        self._set_manifest_inactive(
            runtime_manifest_id,
            _RUNTIME_TYPE,
            expected_revision,
            "unavailable",
            actor_type,
            operation_id,
        )
        return self.get_runtime(runtime_manifest_id)

    def deprecate_model(
        self,
        model_manifest_id: str,
        *,
        expected_revision: int,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        _require_user(actor_type, "model deprecation")
        self._set_manifest_inactive(
            model_manifest_id,
            _MODEL_TYPE,
            expected_revision,
            "deprecated",
            actor_type,
            operation_id,
        )
        return self.get_model(model_manifest_id)

    def mark_model_unavailable(
        self,
        model_manifest_id: str,
        *,
        expected_revision: int,
        actor_type: ManifestActor = "system",
        operation_id: str | None = None,
    ) -> ModelManifestInfo:
        if actor_type not in {"user", "system"}:
            raise ModelManifestValidationError(
                "model unavailability requires user or system authority"
            )
        self._set_manifest_inactive(
            model_manifest_id,
            _MODEL_TYPE,
            expected_revision,
            "unavailable",
            actor_type,
            operation_id,
        )
        return self.get_model(model_manifest_id)

    def _set_manifest_inactive(
        self,
        record_id: str,
        record_type: str,
        expected_revision: int,
        state: Literal["deprecated", "unavailable"],
        actor_type: ManifestActor,
        operation_id: str | None,
    ) -> None:
        record = _require_record(self.repository, record_id, record_type)
        self._require_no_selectable_bindings(record_id, record_type)
        metadata = dict(record.metadata)
        metadata["manifest_state"] = state
        metadata["quarantine_reason"] = None
        _update_one(
            self.repository,
            record_id=record_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance=("user-confirmed" if actor_type == "user" else "system-generated"),
            actor_type=actor_type,
            action=f"{record_type}.{state}",
            operation_id=operation_id,
        )

    def _require_no_selectable_bindings(self, manifest_id: str, record_type: str) -> None:
        key = "runtime_manifest_id" if record_type == _RUNTIME_TYPE else "model_manifest_id"
        row = self.repository.connection.execute(
            "SELECT 1 FROM records WHERE record_type = 'model_binding' "
            "AND status = 'active' AND json_valid(metadata_json) "
            "AND json_extract(metadata_json, ?) = ? "
            "AND json_extract(metadata_json, '$.binding_state') IN ('active', 'fallback') "
            "LIMIT 1",
            (f"$.{key}", manifest_id),
        ).fetchone()
        if row is not None:
            raise ModelManifestValidationError(
                "selectable bindings must be disabled before manifest deactivation"
            )

    def set_smoke_test(
        self,
        binding_id: str,
        *,
        expected_revision: int,
        status: SmokeTestStatus,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        _require_user(actor_type, "binding smoke-test confirmation")
        record = _require_record(self.repository, binding_id, _BINDING_TYPE)
        metadata = dict(record.metadata)
        metadata["smoke_test_status"] = _smoke_state(status)
        _update_one(
            self.repository,
            record_id=binding_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="model_binding.smoke_test",
            operation_id=operation_id,
        )
        return self.get_binding(binding_id)

    def activate_binding(
        self,
        binding_id: str,
        *,
        expected_revision: int,
        evidence_ids: Sequence[str] = (),
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        _require_user(actor_type, "binding activation")
        candidate_record = _require_record(self.repository, binding_id, _BINDING_TYPE)
        candidate = _binding_from_record(candidate_record)
        if candidate.binding_state not in {"candidate", "fallback", "previous", "disabled"}:
            raise ModelManifestValidationError("binding cannot be activated from its state")
        if candidate.smoke_test_status != "passed":
            raise ModelManifestValidationError("binding smoke test has not passed")
        runtime, model = self._activation_manifests(candidate)
        evidence = _evidence_ids(self.repository, evidence_ids)
        current_active = self._active_for_scope(
            candidate.scope_type, candidate.scope_key, exclude_id=binding_id
        )
        connection = self.repository.connection
        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            refreshed = self.repository.get_record(binding_id)
            if refreshed.revision != expected_revision:
                raise StaleRevisionError(
                    f"record revision is {refreshed.revision}, expected {expected_revision}"
                )
            previous_id: str | None = None
            if current_active is not None:
                previous_record = self.repository.get_record(current_active.binding_id)
                previous_metadata = dict(previous_record.metadata)
                previous_metadata["binding_state"] = "previous"
                previous_metadata["fallback_eligible"] = False
                previous_metadata["fallback_priority"] = None
                _sql_update_record(
                    connection,
                    previous_record,
                    previous_metadata,
                    "user-confirmed",
                    previous_record.revision,
                )
                previous_id = current_active.binding_id
            metadata = dict(refreshed.metadata)
            metadata.update(
                {
                    "runtime_manifest_revision": runtime.revision,
                    "model_manifest_revision": model.revision,
                    "binding_state": "active",
                    "activated_at": now,
                    "activation_evidence_ids": list(evidence),
                    "previous_binding_id": previous_id,
                    "fallback_priority": None,
                    "fallback_eligible": False,
                    "rollback_target_id": previous_id,
                    "rollback_reason": None,
                }
            )
            _sql_update_record(
                connection,
                refreshed,
                metadata,
                "user-confirmed",
                expected_revision,
            )
            _insert_audit(
                self.repository,
                operation_id=_operation_id(operation_id),
                action="model_binding.activate",
                target_type=_BINDING_TYPE,
                target_id=binding_id,
                actor_type="user",
                metadata={
                    "scope_key": candidate.scope_key,
                    "previous_binding": previous_id is not None,
                },
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ModelManifestValidationError("scope already has an active binding") from exc
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)
        return self.get_binding(binding_id)

    def set_fallback(
        self,
        binding_id: str,
        *,
        expected_revision: int,
        priority: int,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        _require_user(actor_type, "fallback eligibility")
        binding = self.get_binding(binding_id)
        if binding.binding_state not in {"candidate", "previous", "disabled", "fallback"}:
            raise ModelManifestValidationError("binding cannot become fallback from its state")
        if binding.smoke_test_status != "passed":
            raise ModelManifestValidationError("fallback smoke test has not passed")
        self._activation_manifests(binding)
        if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 1000:
            raise ModelManifestValidationError("fallback priority is invalid")
        record = _require_record(self.repository, binding_id, _BINDING_TYPE)
        metadata = dict(record.metadata)
        metadata["binding_state"] = "fallback"
        metadata["fallback_priority"] = priority
        metadata["fallback_eligible"] = True
        _update_one(
            self.repository,
            record_id=binding_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="model_binding.set_fallback",
            operation_id=operation_id,
        )
        return self.get_binding(binding_id)

    def disable_binding(
        self,
        binding_id: str,
        *,
        expected_revision: int,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        _require_user(actor_type, "binding disable")
        binding = self.get_binding(binding_id)
        if binding.binding_state == "rolled_back":
            raise ModelManifestValidationError("rolled-back binding cannot be disabled")
        record = _require_record(self.repository, binding_id, _BINDING_TYPE)
        metadata = dict(record.metadata)
        metadata["binding_state"] = "disabled"
        metadata["fallback_priority"] = None
        metadata["fallback_eligible"] = False
        _update_one(
            self.repository,
            record_id=binding_id,
            expected_revision=expected_revision,
            metadata=metadata,
            provenance="user-confirmed",
            actor_type="user",
            action="model_binding.disable",
            operation_id=operation_id,
        )
        return self.get_binding(binding_id)

    def rollback_binding(
        self,
        binding_id: str,
        *,
        expected_revision: int,
        reason: str,
        actor_type: ManifestActor = "user",
        operation_id: str | None = None,
    ) -> ModelBindingInfo:
        _require_user(actor_type, "binding rollback")
        active_record = _require_record(self.repository, binding_id, _BINDING_TYPE)
        active = _binding_from_record(active_record)
        if active.binding_state != "active" or active.previous_binding_id is None:
            raise ModelManifestValidationError("active binding has no rollback target")
        previous_record = _require_record(
            self.repository, active.previous_binding_id, _BINDING_TYPE
        )
        previous = _binding_from_record(previous_record)
        if previous.scope_key != active.scope_key or previous.binding_state != "previous":
            raise ModelManifestValidationError("rollback target is not the previous scope binding")
        self._activation_manifests(previous)
        safe_reason = _text("rollback reason", reason, _MAX_TEXT)
        connection = self.repository.connection
        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        try:
            connection.execute("BEGIN IMMEDIATE")
            refreshed_active = self.repository.get_record(binding_id)
            if refreshed_active.revision != expected_revision:
                raise StaleRevisionError(
                    f"record revision is {refreshed_active.revision}, expected {expected_revision}"
                )
            refreshed_previous = self.repository.get_record(previous.binding_id)
            previous_metadata = dict(refreshed_previous.metadata)
            previous_metadata.update(
                {
                    "binding_state": "active",
                    "activated_at": _utc_now(),
                    "previous_binding_id": None,
                    "fallback_priority": None,
                    "fallback_eligible": False,
                    "rollback_target_id": None,
                    "rollback_reason": None,
                }
            )
            active_metadata = dict(refreshed_active.metadata)
            active_metadata.update(
                {
                    "binding_state": "rolled_back",
                    "fallback_priority": None,
                    "fallback_eligible": False,
                    "rollback_target_id": previous.binding_id,
                    "rollback_reason": safe_reason,
                }
            )
            _sql_update_record(
                connection,
                refreshed_active,
                active_metadata,
                "user-confirmed",
                expected_revision,
            )
            _sql_update_record(
                connection,
                refreshed_previous,
                previous_metadata,
                "user-confirmed",
                refreshed_previous.revision,
            )
            _insert_audit(
                self.repository,
                operation_id=_operation_id(operation_id),
                action="model_binding.rollback",
                target_type=_BINDING_TYPE,
                target_id=binding_id,
                actor_type="user",
                metadata={
                    "scope_key": active.scope_key,
                    "restored_binding_id": previous.binding_id,
                },
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)
        return self.get_binding(binding_id)

    def _activation_manifests(
        self, binding: ModelBindingInfo
    ) -> tuple[RuntimeManifestInfo, ModelManifestInfo]:
        runtime = self.get_runtime(binding.runtime_manifest_id)
        model = self.get_model(binding.model_manifest_id)
        if runtime.lifecycle_status != "active" or runtime.manifest_state != "verified":
            raise ModelManifestValidationError("binding runtime is not verified")
        if model.lifecycle_status != "active" or model.manifest_state != "verified":
            raise ModelManifestValidationError("binding model is not verified")
        if model.runtime_manifest_id != runtime.runtime_manifest_id:
            raise ModelManifestValidationError("binding model belongs to another runtime")
        if runtime.revision != binding.runtime_manifest_revision:
            raise ModelManifestValidationError("binding runtime revision is stale")
        if model.revision != binding.model_manifest_revision:
            raise ModelManifestValidationError("binding model revision is stale")
        return runtime, model

    def _active_for_scope(
        self,
        scope_type: str,
        scope_key: str,
        *,
        exclude_id: str | None = None,
    ) -> ModelBindingInfo | None:
        rows = self.repository.connection.execute(
            "SELECT id FROM records WHERE record_type = ? AND status = 'active' "
            "AND json_valid(metadata_json) "
            "AND json_extract(metadata_json, '$.scope_type') = ? "
            "AND json_extract(metadata_json, '$.scope_key') = ? "
            "AND json_extract(metadata_json, '$.binding_state') = 'active' ORDER BY id",
            (_BINDING_TYPE, scope_type, scope_key),
        ).fetchall()
        active = [
            self.get_binding(cast(str, row[0])) for row in rows if cast(str, row[0]) != exclude_id
        ]
        if len(active) > 1:
            raise ModelManifestCorruptError("scope has multiple active bindings")
        return active[0] if active else None


def _runtime_from_record(record: RecordEnvelope) -> RuntimeManifestInfo:
    try:
        _require_shape(record, _RUNTIME_TYPE, RUNTIME_MANIFEST_SCHEMA_VERSION, _RUNTIME_KEYS)
        metadata = record.metadata
        adapter_id = _token("adapter ID", metadata["adapter_id"])
        adapter_version = _token("adapter version", metadata["adapter_version"])
        runtime_class = _token("runtime class", metadata["runtime_class"])
        connection_kind = _token("connection kind", metadata["connection_kind"])
        operations = _tokens(
            "operations", _list(metadata["operations"]), allowed=_ALLOWED_OPERATIONS
        )
        fingerprint = _fingerprint(metadata["declaration_fingerprint"])
        expected = _runtime_fingerprint(
            adapter_id,
            adapter_version,
            runtime_class,
            connection_kind,
            operations,
            _bool("offline capable", metadata["offline_capable"]),
            _bool("cloud fallback", metadata["cloud_fallback"]),
            _bool("automatic download", metadata["automatic_download"]),
        )
        if fingerprint != expected:
            raise ModelManifestValidationError("runtime declaration fingerprint does not match")
        state = _manifest_state(metadata["manifest_state"])
        reason = _optional_text("quarantine reason", metadata["quarantine_reason"], _MAX_TEXT)
        if (state == "quarantined") != (reason is not None):
            raise ModelManifestValidationError("runtime quarantine metadata is inconsistent")
        return RuntimeManifestInfo(
            runtime_manifest_id=_uuid("runtime manifest ID", record.id),
            label=_text("runtime label", record.title, _MAX_DISPLAY),
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            runtime_class=runtime_class,
            connection_kind=connection_kind,
            runtime_version=_optional_token("runtime version", metadata["runtime_version"]),
            declaration_fingerprint=fingerprint,
            operations=operations,
            offline_capable=cast(bool, metadata["offline_capable"]),
            cloud_fallback=cast(bool, metadata["cloud_fallback"]),
            automatic_download=cast(bool, metadata["automatic_download"]),
            platforms=_tokens("platforms", _list(metadata["platforms"])),
            compatibility=_tokens("compatibility", _list(metadata["compatibility"])),
            source_references=_references(_list(metadata["source_references"])),
            manifest_state=state,
            verification_evidence_ids=_uuid_list(
                "verification evidence IDs", _list(metadata["verification_evidence_ids"])
            ),
            quarantine_reason=reason,
            revision=record.revision,
            lifecycle_status=record.status,
            provenance=record.provenance,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
    except (KeyError, TypeError, ValueError, ModelManifestValidationError) as exc:
        raise ModelManifestCorruptError("runtime manifest record is invalid") from exc


def _model_from_record(record: RecordEnvelope) -> ModelManifestInfo:
    try:
        _require_shape(record, _MODEL_TYPE, MODEL_MANIFEST_SCHEMA_VERSION, _MODEL_KEYS)
        metadata = record.metadata
        state = _manifest_state(metadata["manifest_state"])
        reason = _optional_text("quarantine reason", metadata["quarantine_reason"], _MAX_TEXT)
        if (state == "quarantined") != (reason is not None):
            raise ModelManifestValidationError("model quarantine metadata is inconsistent")
        return ModelManifestInfo(
            model_manifest_id=_uuid("model manifest ID", record.id),
            runtime_manifest_id=_uuid("runtime manifest ID", metadata["runtime_manifest_id"]),
            runtime_private_locator=_locator(metadata["runtime_private_locator"]),
            display_name=_text("model display name", metadata["display_name"], _MAX_DISPLAY),
            exact_revision=_text("exact model revision", metadata["exact_revision"], _MAX_TEXT),
            checksums=_checksum_payload(metadata["checksums"]),
            source_references=_references(_list(metadata["source_references"])),
            license_id=_token("license ID", metadata["license_id"]),
            license_review_state=_license_state(metadata["license_review_state"]),
            model_format=_token("model format", metadata["model_format"]),
            size_bytes=_optional_positive_int("model size", metadata["size_bytes"]),
            context_limit=_optional_positive_int("context limit", metadata["context_limit"]),
            capabilities=_tokens("capabilities", _list(metadata["capabilities"])),
            platforms=_tokens("platforms", _list(metadata["platforms"])),
            compatibility=_tokens("compatibility", _list(metadata["compatibility"])),
            manifest_state=state,
            verification_evidence_ids=_uuid_list(
                "verification evidence IDs", _list(metadata["verification_evidence_ids"])
            ),
            quarantine_reason=reason,
            revision=record.revision,
            lifecycle_status=record.status,
            provenance=record.provenance,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
    except (KeyError, TypeError, ValueError, ModelManifestValidationError) as exc:
        raise ModelManifestCorruptError("model manifest record is invalid") from exc


def _binding_from_record(record: RecordEnvelope) -> ModelBindingInfo:
    try:
        _require_shape(record, _BINDING_TYPE, MODEL_BINDING_SCHEMA_VERSION, _BINDING_KEYS)
        metadata = record.metadata
        state = _binding_state(metadata["binding_state"])
        activated_at = _optional_timestamp(metadata["activated_at"])
        fallback_priority = _optional_positive_int(
            "fallback priority", metadata["fallback_priority"]
        )
        fallback_eligible = _bool("fallback eligible", metadata["fallback_eligible"])
        if state == "active" and activated_at is None:
            raise ModelManifestValidationError("active binding has no activation time")
        if state == "fallback" and (not fallback_eligible or fallback_priority is None):
            raise ModelManifestValidationError("fallback binding metadata is inconsistent")
        if state != "fallback" and (fallback_eligible or fallback_priority is not None):
            raise ModelManifestValidationError("non-fallback binding has fallback metadata")
        return ModelBindingInfo(
            binding_id=_uuid("binding ID", record.id),
            scope_type=_token("scope type", metadata["scope_type"]),
            scope_key=_scope_key(metadata["scope_key"]),
            runtime_manifest_id=_uuid("runtime manifest ID", metadata["runtime_manifest_id"]),
            runtime_manifest_revision=_positive_int(
                "runtime manifest revision", metadata["runtime_manifest_revision"]
            ),
            model_manifest_id=_uuid("model manifest ID", metadata["model_manifest_id"]),
            model_manifest_revision=_positive_int(
                "model manifest revision", metadata["model_manifest_revision"]
            ),
            binding_state=state,
            activated_at=activated_at,
            activation_evidence_ids=_uuid_list(
                "activation evidence IDs", _list(metadata["activation_evidence_ids"])
            ),
            previous_binding_id=_optional_uuid(
                "previous binding ID", metadata["previous_binding_id"]
            ),
            fallback_priority=fallback_priority,
            fallback_eligible=fallback_eligible,
            rollback_target_id=_optional_uuid("rollback target ID", metadata["rollback_target_id"]),
            rollback_reason=_optional_text(
                "rollback reason", metadata["rollback_reason"], _MAX_TEXT
            ),
            smoke_test_status=_smoke_state(metadata["smoke_test_status"]),
            revision=record.revision,
            lifecycle_status=record.status,
            provenance=record.provenance,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
    except (KeyError, TypeError, ValueError, ModelManifestValidationError) as exc:
        raise ModelManifestCorruptError("model binding record is invalid") from exc


def _require_shape(
    record: RecordEnvelope, record_type: str, version: int, keys: frozenset[str]
) -> None:
    if record.record_type != record_type or record.schema_version != version:
        raise ModelManifestValidationError("record type or schema is invalid")
    if record.status not in {"active", "archived"}:
        raise ModelManifestValidationError("record lifecycle is invalid")
    if frozenset(record.metadata) != keys:
        raise ModelManifestValidationError("record metadata shape is invalid")


def _create_record(
    repository: StateRepository,
    *,
    record_id: str,
    record_type: str,
    title: str,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
    provenance: RecordProvenance,
    actor_type: ManifestActor,
    action: str,
    operation_id: str | None,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type=record_type,
        schema_version=1,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    # Reuse ordinary-record policy before the direct transactional insert.
    from doll.state_repository import _validate_secret_boundary

    _validate_secret_boundary(record_type=record_type, sensitivity=sensitivity, metadata=metadata)
    connection = repository.connection
    now = _utc_now()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO records (id, record_type, schema_version, created_at, updated_at, "
            "revision, status, provenance, sensitivity, title, metadata_json) "
            "VALUES (?, ?, 1, ?, ?, 1, 'active', ?, ?, ?, ?)",
            (
                record_id,
                record_type,
                now,
                now,
                provenance,
                sensitivity,
                title,
                _serialize_metadata(metadata),
            ),
        )
        _insert_audit(
            repository,
            operation_id=_operation_id(operation_id),
            action=action,
            target_type=record_type,
            target_id=record_id,
            actor_type=actor_type,
            metadata={
                "provenance": provenance,
                "state": cast(str, metadata.get("manifest_state") or metadata.get("binding_state")),
            },
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("manifest record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _update_one(
    repository: StateRepository,
    *,
    record_id: str,
    expected_revision: int,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    actor_type: ManifestActor,
    action: str,
    operation_id: str | None,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    record = repository.get_record(record_id)
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        refreshed = repository.get_record(record_id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        _sql_update_record(connection, refreshed, metadata, provenance, expected_revision)
        _insert_audit(
            repository,
            operation_id=_operation_id(operation_id),
            action=action,
            target_type=record.record_type,
            target_id=record_id,
            actor_type=actor_type,
            metadata={"revision": expected_revision + 1},
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _sql_update_record(
    connection: sqlite3.Connection,
    record: RecordEnvelope,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    expected_revision: int,
) -> None:
    connection.execute(
        "UPDATE records SET updated_at = ?, revision = revision + 1, provenance = ?, "
        "metadata_json = ? WHERE id = ? AND revision = ? AND status = 'active'",
        (_utc_now(), provenance, _serialize_metadata(metadata), record.id, expected_revision),
    )
    changed = connection.execute("SELECT changes()").fetchone()
    if changed is None or cast(int, changed[0]) != 1:
        raise StaleRevisionError("manifest record revision changed during update")


def _insert_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    action: str,
    target_type: str,
    target_id: str,
    actor_type: ManifestActor,
    metadata: dict[str, object],
) -> None:
    repository.connection.execute(
        "INSERT INTO audit_events (event_id, operation_id, occurred_at, actor_type, action, "
        "target_type, target_id, result, summary, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'success', ?, ?)",
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
            target_type,
            target_id,
            "Changed authoritative local-model configuration",
            _serialize_audit_metadata(metadata),
        ),
    )


def _require_record(
    repository: StateRepository, record_id: str, record_type: str
) -> RecordEnvelope:
    safe_id = _uuid("record ID", record_id)
    try:
        record = repository.get_record(safe_id)
    except KeyError as exc:
        raise ModelManifestValidationError("manifest record does not exist") from exc
    if record.record_type != record_type:
        raise ModelManifestValidationError("record has the wrong manifest type")
    return record


def _evidence_ids(repository: StateRepository, values: Sequence[str]) -> tuple[str, ...]:
    result = _uuid_list("evidence IDs", values)
    for record_id in result:
        try:
            record = repository.get_record(record_id)
        except KeyError as exc:
            raise ModelManifestValidationError("evidence record does not exist") from exc
        if (
            record.record_type != "evidence"
            or record.status != "active"
            or record.sensitivity == "secret"
        ):
            raise ModelManifestValidationError("evidence record is not active and portable")
    return result


def _actor_provenance(actor_type: ManifestActor) -> RecordProvenance:
    mapping: dict[ManifestActor, RecordProvenance] = {
        "user": "user-created",
        "model": "model-proposed",
        "importer": "imported",
        "runtime": "system-generated",
        "system": "system-generated",
    }
    return mapping[actor_type]


def _audit_actor(actor_type: ManifestActor) -> str:
    return "system" if actor_type == "importer" else actor_type


def _require_user(actor_type: ManifestActor, action: str) -> None:
    if actor_type != "user":
        raise ModelManifestValidationError(f"{action} requires the user path")


def _require_quarantine_actor(actor_type: ManifestActor) -> None:
    if actor_type not in {"user", "system"}:
        raise ModelManifestValidationError("manifest quarantine requires user or system authority")


def _operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _runtime_fingerprint(
    adapter_id: str,
    adapter_version: str,
    runtime_class: str,
    connection_kind: str,
    operations: tuple[str, ...],
    offline_capable: bool,
    cloud_fallback: bool,
    automatic_download: bool,
) -> str:
    payload = json.dumps(
        {
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "automatic_download": automatic_download,
            "cloud_fallback": cloud_fallback,
            "connection_kind": connection_kind,
            "offline_capable": offline_capable,
            "operations": list(operations),
            "runtime_class": runtime_class,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _fingerprint(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or not _SHA256.fullmatch(value[7:])
    ):
        raise ModelManifestValidationError("declaration fingerprint is invalid")
    return value


def _checksums(values: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, Mapping) or not 1 <= len(values) <= _MAX_CHECKSUMS:
        raise ModelManifestValidationError("model checksums are invalid")
    result: list[tuple[str, str]] = []
    for raw_algorithm, raw_value in values.items():
        algorithm = _token("checksum algorithm", raw_algorithm).lower()
        value = _text("checksum value", raw_value, 256).lower()
        if not _CHECKSUM.fullmatch(value):
            raise ModelManifestValidationError("checksum value is invalid")
        result.append((algorithm, value))
    return tuple(sorted(result))


def _checksum_payload(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ModelManifestValidationError("model checksums must be a list")
    mapping: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict) or frozenset(item) != {"algorithm", "value"}:
            raise ModelManifestValidationError("model checksum entry is invalid")
        algorithm = item["algorithm"]
        checksum = item["value"]
        if not isinstance(algorithm, str) or not isinstance(checksum, str) or algorithm in mapping:
            raise ModelManifestValidationError("model checksum entry is invalid")
        mapping[algorithm] = checksum
    return _checksums(mapping)


def _locator(value: object) -> str:
    text = _text("runtime-private locator", value, _MAX_TEXT)
    if _PRIVATE_PATH.search(text) or _URL.match(text) or "@" in text or "?" in text or "#" in text:
        raise ModelManifestValidationError("runtime-private locator is unsafe")
    return text


def _scope_key(value: object) -> str:
    text = _text("binding scope key", value, 180)
    if _PRIVATE_PATH.search(text) or _URL.match(text):
        raise ModelManifestValidationError("binding scope key is unsafe")
    return text


def _references(values: Sequence[object]) -> tuple[str, ...]:
    if len(values) > _MAX_REFERENCES:
        raise ModelManifestValidationError("too many source references")
    result: list[str] = []
    for value in values:
        text = _text("source reference", value, 2048)
        if _PRIVATE_PATH.search(text):
            raise ModelManifestValidationError("source reference contains a private path")
        result.append(text)
    if len(set(result)) != len(result):
        raise ModelManifestValidationError("source references contain duplicates")
    return tuple(sorted(result))


def _tokens(
    label: str, values: Sequence[object], *, allowed: frozenset[str] | None = None
) -> tuple[str, ...]:
    if len(values) > _MAX_LIST:
        raise ModelManifestValidationError(f"{label} has too many values")
    result = tuple(sorted(_token(label, value) for value in values))
    if len(set(result)) != len(result):
        raise ModelManifestValidationError(f"{label} contains duplicates")
    if allowed is not None and not set(result).issubset(allowed):
        raise ModelManifestValidationError(f"{label} contains unsupported values")
    return result


def _token(label: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ModelManifestValidationError(f"{label} is invalid")
    return value


def _optional_token(label: str, value: object) -> str | None:
    if value is None:
        return None
    return _token(label, value)


def _text(label: str, value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or value != value.strip():
        raise ModelManifestValidationError(f"{label} is invalid")
    if "\x00" in value or _PRIVATE_PATH.search(value):
        raise ModelManifestValidationError(f"{label} contains unsafe private data")
    return value


def _optional_text(label: str, value: object, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(label, value, maximum)


def _bool(label: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ModelManifestValidationError(f"{label} is invalid")
    return value


def _positive_int(label: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ModelManifestValidationError(f"{label} is invalid")
    return value


def _optional_positive_int(label: str, value: object) -> int | None:
    if value is None:
        return None
    return _positive_int(label, value)


def _uuid(label: str, value: object) -> str:
    if not isinstance(value, str):
        raise ModelManifestValidationError(f"{label} is invalid")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ModelManifestValidationError(f"{label} is invalid") from exc
    if str(parsed) != value:
        raise ModelManifestValidationError(f"{label} is not canonical")
    return value


def _optional_uuid(label: str, value: object) -> str | None:
    if value is None:
        return None
    return _uuid(label, value)


def _uuid_list(label: str, values: Sequence[object]) -> tuple[str, ...]:
    if len(values) > _MAX_LIST:
        raise ModelManifestValidationError(f"{label} has too many values")
    result = tuple(sorted(_uuid(label, value) for value in values))
    if len(set(result)) != len(result):
        raise ModelManifestValidationError(f"{label} contains duplicates")
    return result


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ModelManifestValidationError("manifest list value is invalid")
    return value


def _manifest_state(value: object) -> ManifestState:
    if not isinstance(value, str) or value not in _MANIFEST_STATES:
        raise ModelManifestValidationError("manifest state is invalid")
    return cast(ManifestState, value)


def _license_state(value: object) -> LicenseReviewState:
    if not isinstance(value, str) or value not in _LICENSE_STATES:
        raise ModelManifestValidationError("license review state is invalid")
    return cast(LicenseReviewState, value)


def _binding_state(value: object) -> BindingState:
    if not isinstance(value, str) or value not in _BINDING_STATES:
        raise ModelManifestValidationError("binding state is invalid")
    return cast(BindingState, value)


def _smoke_state(value: object) -> SmokeTestStatus:
    if not isinstance(value, str) or value not in _SMOKE_STATES:
        raise ModelManifestValidationError("smoke-test state is invalid")
    return cast(SmokeTestStatus, value)


def _optional_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
        raise ModelManifestValidationError("activation timestamp is invalid")
    return value
