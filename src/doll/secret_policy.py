"""Model-independent secret classification and handling policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

SecretClass = Literal[
    "credential",
    "authentication_material",
    "cryptographic_key",
    "session_material",
    "recovery_material",
    "personal_sensitive",
    "unknown_secret",
]
CredentialClass = Literal[
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "session_cookie",
    "recovery_phrase",
    "authorization_header",
    "other",
]
SecretReferenceStatus = Literal["active", "rotated", "revoked"]
SecretPayloadKind = Literal["non_secret", "secret_value", "secret_reference", "unknown"]
SecretHandlingLocation = Literal[
    "input",
    "ordinary_state",
    "audit",
    "log",
    "export",
    "backup",
    "diagnostic",
    "model_context",
    "output",
    "external_secret_store",
    "bounded_operation",
]
SecretDisposition = Literal["allow", "reference_only", "transient_only", "deny"]

_ALLOWED_SECRET_CLASSES = frozenset(
    {
        "credential",
        "authentication_material",
        "cryptographic_key",
        "session_material",
        "recovery_material",
        "personal_sensitive",
        "unknown_secret",
    }
)
_ALLOWED_CREDENTIAL_CLASSES = frozenset(
    {
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "session_cookie",
        "recovery_phrase",
        "authorization_header",
        "other",
    }
)
_ALLOWED_REFERENCE_STATUSES = frozenset({"active", "rotated", "revoked"})
_ALLOWED_REFERENCE_FIELDS = frozenset(
    {
        "reference_id",
        "credential_class",
        "store_adapter_class",
        "label",
        "status",
        "provider_class",
        "allowed_operation_scope",
        "allowed_destination_scope",
        "created_at",
        "rotated_at",
        "revoked_at",
    }
)
_PROHIBITED_REFERENCE_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secret_value",
        "credential",
        "credential_value",
        "credentials",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "private_key",
        "key",
        "cookie",
        "session_cookie",
        "recovery_phrase",
        "seed_phrase",
        "mnemonic",
        "authorization",
        "authorization_header",
        "auth_header",
        "bearer_token",
        "value",
        "raw_value",
        "encoded_value",
        "encrypted_value",
        "ciphertext",
        "reconstruction_hint",
        "value_hint",
        "prefix",
        "suffix",
        "last_four",
        "checksum",
    }
)
_REFERENCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ADAPTER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@*-]{0,199}$")
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_REFERENCE_ONLY_LOCATIONS = frozenset({"ordinary_state", "export", "backup"})
_SECRET_VALUE_DENIED_LOCATIONS = frozenset(
    {
        "ordinary_state",
        "audit",
        "log",
        "export",
        "backup",
        "diagnostic",
        "model_context",
        "output",
    }
)


class SecretPolicyError(RuntimeError):
    """Base class for secret policy failures."""


class SecretClassificationError(SecretPolicyError):
    """Raised when a secret classification or handling request is invalid."""


class SecretReferenceValidationError(SecretPolicyError):
    """Raised when non-secret SecretReference metadata is malformed."""


@dataclass(frozen=True, slots=True)
class SecretReferenceMetadata:
    """Validated non-secret metadata pointing to an external secret-store entry."""

    reference_id: str
    credential_class: CredentialClass
    store_adapter_class: str
    label: str
    status: SecretReferenceStatus
    provider_class: str | None
    allowed_operation_scope: tuple[str, ...]
    allowed_destination_scope: tuple[str, ...]
    created_at: str | None
    rotated_at: str | None
    revoked_at: str | None

    def as_record_metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "reference_id": self.reference_id,
            "credential_class": self.credential_class,
            "store_adapter_class": self.store_adapter_class,
            "label": self.label,
            "status": self.status,
            "allowed_operation_scope": list(self.allowed_operation_scope),
            "allowed_destination_scope": list(self.allowed_destination_scope),
        }
        for key, value in (
            ("provider_class", self.provider_class),
            ("created_at", self.created_at),
            ("rotated_at", self.rotated_at),
            ("revoked_at", self.revoked_at),
        ):
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True, slots=True)
class SecretHandlingDecision:
    """Deterministic secret handling decision with no secret-bearing content."""

    payload_kind: SecretPayloadKind
    location: SecretHandlingLocation
    disposition: SecretDisposition
    allowed: bool
    reason: str
    requires_external_store: bool
    requires_bounded_operation: bool


def classify_secret_class(value: str) -> SecretClass:
    if value not in _ALLOWED_SECRET_CLASSES:
        raise SecretClassificationError("unknown secret class")
    return cast(SecretClass, value)


def evaluate_secret_handling(
    *,
    payload_kind: SecretPayloadKind,
    location: SecretHandlingLocation,
    sensitivity: str | None = None,
    uncertain: bool = False,
) -> SecretHandlingDecision:
    """Return the fail-closed handling decision for one classified payload."""

    del sensitivity  # A sensitivity label never grants secret-value persistence.
    if uncertain or payload_kind == "unknown":
        return _decision(payload_kind, location, "deny", "classification_uncertain")
    if payload_kind == "non_secret":
        return _decision(payload_kind, location, "allow", "non_secret_payload")
    if payload_kind == "secret_reference":
        disposition: SecretDisposition = (
            "reference_only" if location in _REFERENCE_ONLY_LOCATIONS else "allow"
        )
        return _decision(payload_kind, location, disposition, "validated_non_secret_reference")
    if location in _SECRET_VALUE_DENIED_LOCATIONS:
        return _decision(payload_kind, location, "deny", "secret_value_prohibited")
    if location == "external_secret_store":
        return _decision(payload_kind, location, "allow", "external_store_only")
    if location in {"input", "bounded_operation"}:
        return _decision(payload_kind, location, "transient_only", "bounded_transient_use")
    return _decision(payload_kind, location, "deny", "unsupported_secret_destination")


def validate_secret_reference_metadata(metadata: dict[str, object]) -> SecretReferenceMetadata:
    """Validate the exact non-secret metadata allowed in SecretReferenceRecord."""

    if not isinstance(metadata, dict):
        raise SecretReferenceValidationError("SecretReference metadata must be an object")
    for raw_key in metadata:
        normalized = _normalize_field_name(raw_key)
        if normalized in _PROHIBITED_REFERENCE_FIELDS:
            raise SecretReferenceValidationError(f"SecretReference field is prohibited: {raw_key}")
        if raw_key not in _ALLOWED_REFERENCE_FIELDS:
            raise SecretReferenceValidationError(f"unknown SecretReference field: {raw_key}")
    required = {
        "reference_id",
        "credential_class",
        "store_adapter_class",
        "label",
        "status",
    }
    missing = sorted(required.difference(metadata))
    if missing:
        raise SecretReferenceValidationError(
            f"missing SecretReference fields: {', '.join(missing)}"
        )
    reference_id = _required_string(metadata, "reference_id", maximum=128)
    if _REFERENCE_ID_PATTERN.fullmatch(reference_id) is None:
        raise SecretReferenceValidationError("invalid SecretReference reference_id")
    credential = _required_string(metadata, "credential_class", maximum=40)
    if credential not in _ALLOWED_CREDENTIAL_CLASSES:
        raise SecretReferenceValidationError("unknown SecretReference credential_class")
    adapter = _required_string(metadata, "store_adapter_class", maximum=80)
    if _ADAPTER_PATTERN.fullmatch(adapter) is None:
        raise SecretReferenceValidationError("invalid SecretReference store_adapter_class")
    label = _required_string(metadata, "label", maximum=160)
    status = _required_string(metadata, "status", maximum=20)
    if status not in _ALLOWED_REFERENCE_STATUSES:
        raise SecretReferenceValidationError("unknown SecretReference status")
    provider_class = _optional_string(metadata, "provider_class", maximum=80)
    if provider_class is not None and _ADAPTER_PATTERN.fullmatch(provider_class) is None:
        raise SecretReferenceValidationError("invalid SecretReference provider_class")
    operations = _scope(metadata, "allowed_operation_scope")
    destinations = _scope(metadata, "allowed_destination_scope")
    created_at = _timestamp(metadata, "created_at")
    rotated_at = _timestamp(metadata, "rotated_at")
    revoked_at = _timestamp(metadata, "revoked_at")
    if status == "rotated" and rotated_at is None:
        raise SecretReferenceValidationError("rotated SecretReference requires rotated_at")
    if status == "revoked" and revoked_at is None:
        raise SecretReferenceValidationError("revoked SecretReference requires revoked_at")
    return SecretReferenceMetadata(
        reference_id=reference_id,
        credential_class=cast(CredentialClass, credential),
        store_adapter_class=adapter,
        label=label,
        status=cast(SecretReferenceStatus, status),
        provider_class=provider_class,
        allowed_operation_scope=operations,
        allowed_destination_scope=destinations,
        created_at=created_at,
        rotated_at=rotated_at,
        revoked_at=revoked_at,
    )


def validate_ordinary_state_record(
    *,
    record_type: str,
    sensitivity: str,
    metadata: dict[str, object],
) -> None:
    """Enforce the ordinary-state side of the secret classification policy."""

    if record_type == "secret_reference":
        if sensitivity not in {"sensitive", "secret"}:
            raise SecretClassificationError(
                "SecretReference records require sensitive or secret sensitivity"
            )
        validate_secret_reference_metadata(metadata)
        return
    if sensitivity == "secret":
        raise SecretClassificationError(
            "secret sensitivity does not permit secret values in ordinary Doll State; "
            "store only a validated SecretReference record"
        )


def _decision(
    payload_kind: SecretPayloadKind,
    location: SecretHandlingLocation,
    disposition: SecretDisposition,
    reason: str,
) -> SecretHandlingDecision:
    return SecretHandlingDecision(
        payload_kind=payload_kind,
        location=location,
        disposition=disposition,
        allowed=disposition != "deny",
        reason=reason,
        requires_external_store=payload_kind == "secret_value"
        and location not in {"external_secret_store", "bounded_operation", "input"},
        requires_bounded_operation=payload_kind == "secret_value"
        and location in {"input", "bounded_operation"},
    )


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _required_string(metadata: dict[str, object], key: str, *, maximum: int) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SecretReferenceValidationError(f"invalid SecretReference {key}")
    if any(character.isspace() and character != " " for character in value):
        raise SecretReferenceValidationError(f"invalid SecretReference {key}")
    return value


def _optional_string(metadata: dict[str, object], key: str, *, maximum: int) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SecretReferenceValidationError(f"invalid SecretReference {key}")
    return value


def _scope(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key, [])
    if not isinstance(value, list) or len(value) > 32:
        raise SecretReferenceValidationError(f"invalid SecretReference {key}")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or _SCOPE_PATTERN.fullmatch(item) is None:
            raise SecretReferenceValidationError(f"invalid SecretReference {key}")
        if item in result:
            raise SecretReferenceValidationError(f"duplicate SecretReference {key} entry")
        result.append(item)
    return tuple(result)


def _timestamp(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or _TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise SecretReferenceValidationError(f"invalid SecretReference {key}")
    return value


__all__ = [
    "CredentialClass",
    "SecretClass",
    "SecretClassificationError",
    "SecretDisposition",
    "SecretHandlingDecision",
    "SecretHandlingLocation",
    "SecretPayloadKind",
    "SecretPolicyError",
    "SecretReferenceMetadata",
    "SecretReferenceStatus",
    "SecretReferenceValidationError",
    "classify_secret_class",
    "evaluate_secret_handling",
    "validate_ordinary_state_record",
    "validate_secret_reference_metadata",
]
