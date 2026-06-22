"""Internal validation and immutable value contracts for high-risk confirmation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from doll.audit import _serialize_metadata
from doll.capabilities import CapabilityRequest, _validate_request_envelope
from doll.instruction_origin import InstructionOriginClass
from doll.state import StateError

ConfirmationDecisionValue = Literal["approved", "denied"]
ConfirmationReason = Literal[
    "not_required",
    "not_evaluated",
    "approved",
    "missing",
    "denied",
    "expired",
    "consumed",
    "revoked",
    "mismatch",
    "corrupt",
]
ConfirmationMutationActor = Literal[
    "user", "model", "runtime", "capability", "system", "tool", "content", "import"
]
ConfirmationConsumeActor = Literal["capability", "system"]

DEFAULT_CONFIRMATION_TTL_SECONDS = 120
MAX_CONFIRMATION_TTL_SECONDS = 600
MAX_CONFIRMATION_EVENTS = 32
MAX_PREVIEW_TEXT_LENGTH = 500
MAX_CREDENTIAL_CLASS_LENGTH = 120
MAX_CONFIRMATION_ID_LENGTH = 200

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ConfirmationError(StateError):
    """Base class for high-risk confirmation failures."""


class ConfirmationValidationError(ConfirmationError):
    """Raised when a confirmation request is malformed or unsafe."""


class ForbiddenConfirmationMutationError(ConfirmationError):
    """Raised when an untrusted path attempts confirmation mutation."""


class ConfirmationUnavailableError(ConfirmationError):
    """Raised when an exact approved confirmation cannot be consumed."""


class ConfirmationCorruptError(ConfirmationError):
    """Raised when append-only confirmation history is malformed."""


@dataclass(frozen=True, slots=True)
class ConfirmationPreview:
    """Bounded consequences shown through a trusted management path."""

    effect_summary: str
    irreversible: bool
    recovery_description: str | None = None
    credential_class: str | None = None
    account_label: str | None = None


@dataclass(frozen=True, slots=True)
class ConfirmationInfo:
    confirmation_id: str
    operation_id: str
    capability_id: str
    capability_version: str
    request_fingerprint: str
    registry_fingerprint: str
    decision: ConfirmationDecisionValue
    issued_at: str
    expires_at: str
    target_kind: str
    destination_host: str | None
    side_effects: tuple[str, ...]
    credential_class: str | None
    data_leaves_machine: bool
    irreversible: bool
    recovery_available: bool
    effect_summary: str
    account_label: str | None
    recovery_description: str | None


@dataclass(frozen=True, slots=True)
class ConfirmationResolution:
    confirmation_id: str | None
    reason: ConfirmationReason
    request_fingerprint: str
    info: ConfirmationInfo | None

    @property
    def approved(self) -> bool:
        return self.reason == "approved"


def require_user_management(
    actor_type: ConfirmationMutationActor,
    origin_class: InstructionOriginClass,
) -> None:
    if actor_type != "user" or origin_class != "user_management_action":
        raise ForbiddenConfirmationMutationError(
            "confirmation requires a trusted user-controlled management action"
        )


def validate_ttl(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfirmationValidationError("confirmation TTL must be an integer")
    if value < 1 or value > MAX_CONFIRMATION_TTL_SECONDS:
        raise ConfirmationValidationError(
            f"confirmation TTL must be between 1 and {MAX_CONFIRMATION_TTL_SECONDS} seconds"
        )
    return value


def safe_now(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except Exception:
        raise ConfirmationValidationError("confirmation clock failed") from None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ConfirmationValidationError("confirmation clock must return a timezone-aware value")
    return value.astimezone(UTC)


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfirmationCorruptError("confirmation timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ConfirmationCorruptError("confirmation timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def validate_token(name: str, value: object, maximum: int) -> str:
    if not isinstance(value, str):
        raise ConfirmationValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or not _TOKEN_PATTERN.fullmatch(normalized):
        raise ConfirmationValidationError(f"{name} is invalid")
    return normalized


def validate_optional_token(name: str, value: str | None, maximum: int) -> str | None:
    return None if value is None else validate_token(name, value, maximum)


def validate_fingerprint(name: str, value: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value):
        raise ConfirmationValidationError(f"{name} is invalid")
    return value


def validate_preview(preview: ConfirmationPreview) -> ConfirmationPreview:
    if not isinstance(preview, ConfirmationPreview):
        raise ConfirmationValidationError("confirmation preview is invalid")
    effect_summary = _validate_preview_text("effect summary", preview.effect_summary, required=True)
    recovery = _validate_preview_text(
        "recovery description", preview.recovery_description, required=False
    )
    credential = validate_optional_token(
        "credential class", preview.credential_class, MAX_CREDENTIAL_CLASS_LENGTH
    )
    account = _validate_preview_text("account label", preview.account_label, required=False)
    if not isinstance(preview.irreversible, bool):
        raise ConfirmationValidationError("irreversible flag must be boolean")
    return ConfirmationPreview(
        effect_summary=cast(str, effect_summary),
        irreversible=preview.irreversible,
        recovery_description=recovery,
        credential_class=credential,
        account_label=account,
    )


def _validate_preview_text(
    name: str,
    value: str | None,
    *,
    required: bool,
) -> str | None:
    if value is None:
        if required:
            raise ConfirmationValidationError(f"{name} is required")
        return None
    normalized = " ".join(value.split())
    if not normalized:
        if required:
            raise ConfirmationValidationError(f"{name} is required")
        return None
    if len(normalized) > MAX_PREVIEW_TEXT_LENGTH:
        raise ConfirmationValidationError(f"{name} exceeds {MAX_PREVIEW_TEXT_LENGTH} characters")
    try:
        _serialize_metadata({"value": normalized})
    except StateError as exc:
        raise ConfirmationValidationError(f"{name} contains unsafe data") from exc
    return normalized


def confirmation_fingerprint(
    request: CapabilityRequest,
    *,
    registry_fingerprint: str,
    normalized_destination: str | None,
    credential_class: str | None = None,
) -> str:
    """Return the exact-operation fingerprint used by confirmation."""

    envelope = _validate_request_envelope(request)
    safe_registry = validate_fingerprint("registry fingerprint", registry_fingerprint)
    safe_credential = validate_optional_token(
        "credential class", credential_class, MAX_CREDENTIAL_CLASS_LENGTH
    )
    _reject_secret_strings(envelope.arguments)
    _reject_secret_strings(envelope.permission_scope)
    payload: dict[str, object] = {
        "schema_version": 1,
        "registry_fingerprint": safe_registry,
        "capability_id": envelope.capability_id,
        "capability_version": envelope.capability_version,
        "operation_id": envelope.operation_id,
        "session_id": envelope.session_id,
        "actor_type": envelope.actor_type,
        "origin_class": envelope.origin_class,
        "arguments": _canonical_value(envelope.arguments),
        "target": {
            "kind": envelope.target.kind,
            "identifier": envelope.target.identifier,
        },
        "destination": normalized_destination,
        "side_effects": sorted(envelope.declared_side_effects),
        "risk_tier": envelope.declared_risk_tier,
        "permission_scope": _canonical_value(envelope.permission_scope),
        "resource_limits": {
            "max_input_chars": envelope.resource_limits.max_input_chars,
            "max_output_bytes": envelope.resource_limits.max_output_bytes,
            "max_items": envelope.resource_limits.max_items,
        },
        "timeout_seconds": envelope.timeout_seconds,
        "cancellation_id": envelope.cancellation_id,
        "credential_class": safe_credential,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ConfirmationValidationError("confirmation input contains unsupported JSON data")


def _reject_secret_strings(value: object) -> None:
    from doll.audit import _reject_secret_text

    if isinstance(value, Mapping):
        for key, nested in value.items():
            _reject_secret_text(str(key))
            _reject_secret_strings(nested)
        return
    if isinstance(value, list):
        for item in value:
            _reject_secret_strings(item)
        return
    if isinstance(value, str):
        try:
            _reject_secret_text(value)
        except StateError as exc:
            raise ConfirmationValidationError(
                "secret-like values cannot be embedded in confirmation input"
            ) from exc
