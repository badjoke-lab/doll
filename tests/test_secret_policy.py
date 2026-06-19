from __future__ import annotations

from typing import cast

import pytest

from doll.secret_policy import (
    SecretClassificationError,
    SecretDisposition,
    SecretHandlingLocation,
    SecretReferenceValidationError,
    classify_secret_class,
    evaluate_secret_handling,
    validate_ordinary_state_record,
    validate_secret_reference_metadata,
)


def _valid_reference() -> dict[str, object]:
    return {
        "reference_id": "credential:example:primary",
        "credential_class": "api_key",
        "store_adapter_class": "test.synthetic",
        "label": "Example API credential",
        "status": "active",
        "provider_class": "example_service",
        "allowed_operation_scope": ["example.read", "example.write"],
        "allowed_destination_scope": ["api.example.invalid"],
        "created_at": "2026-06-19T00:00:00Z",
    }


def test_secret_value_is_denied_in_ordinary_state_even_with_secret_sensitivity() -> None:
    decision = evaluate_secret_handling(
        payload_kind="secret_value",
        location="ordinary_state",
        sensitivity="secret",
    )
    assert decision.allowed is False
    assert decision.disposition == "deny"
    assert decision.reason == "secret_value_prohibited"


@pytest.mark.parametrize(
    ("location", "disposition"),
    [
        ("input", "transient_only"),
        ("bounded_operation", "transient_only"),
        ("external_secret_store", "allow"),
        ("audit", "deny"),
        ("log", "deny"),
        ("export", "deny"),
        ("backup", "deny"),
        ("diagnostic", "deny"),
        ("model_context", "deny"),
        ("output", "deny"),
    ],
)
def test_secret_value_handling_matrix(location: str, disposition: str) -> None:
    decision = evaluate_secret_handling(
        payload_kind="secret_value",
        location=cast(SecretHandlingLocation, location),
    )
    assert decision.disposition == cast(SecretDisposition, disposition)
    assert decision.allowed is (disposition != "deny")


def test_unknown_or_uncertain_payload_fails_closed() -> None:
    unknown = evaluate_secret_handling(payload_kind="unknown", location="input")
    uncertain = evaluate_secret_handling(
        payload_kind="non_secret",
        location="output",
        uncertain=True,
    )
    assert unknown.allowed is False
    assert uncertain.allowed is False
    assert unknown.reason == "classification_uncertain"
    assert uncertain.reason == "classification_uncertain"


def test_non_secret_payload_is_allowed() -> None:
    decision = evaluate_secret_handling(payload_kind="non_secret", location="output")
    assert decision.allowed is True
    assert decision.disposition == "allow"
    assert decision.reason == "non_secret_payload"


def test_unsupported_secret_destination_fails_closed() -> None:
    decision = evaluate_secret_handling(
        payload_kind="secret_value",
        location=cast(SecretHandlingLocation, "unsupported"),
    )
    assert decision.allowed is False
    assert decision.reason == "unsupported_secret_destination"


def test_valid_secret_reference_round_trips_as_non_secret_metadata() -> None:
    reference = validate_secret_reference_metadata(_valid_reference())
    assert reference.reference_id == "credential:example:primary"
    assert reference.credential_class == "api_key"
    assert reference.allowed_operation_scope == ("example.read", "example.write")
    assert reference.as_record_metadata() == _valid_reference()


@pytest.mark.parametrize(
    "field",
    [
        "password",
        "token",
        "private_key",
        "cookie",
        "recovery_phrase",
        "authorization_header",
        "encoded_value",
        "reconstruction_hint",
        "value",
        "last_four",
    ],
)
def test_secret_reference_rejects_value_or_reconstruction_fields(field: str) -> None:
    payload = _valid_reference()
    payload[field] = "synthetic-not-a-real-secret"
    with pytest.raises(SecretReferenceValidationError, match="field is prohibited"):
        validate_secret_reference_metadata(payload)


def test_secret_reference_rejects_unknown_fields_and_nested_metadata() -> None:
    payload = _valid_reference()
    payload["metadata"] = {"note": "not part of the accepted contract"}
    with pytest.raises(SecretReferenceValidationError, match="unknown SecretReference field"):
        validate_secret_reference_metadata(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"credential_class": "unknown"},
        {"store_adapter_class": "Bad Adapter"},
        {"status": "missing"},
        {"allowed_operation_scope": ["valid", "valid"]},
        {"allowed_destination_scope": ["../escape"]},
        {"created_at": "not-a-timestamp"},
        {"status": "rotated"},
        {"status": "revoked"},
        {"reference_id": " invalid"},
        {"provider_class": "Bad Provider"},
        {"label": "bad\tlabel"},
        {"allowed_operation_scope": "not-a-list"},
    ],
)
def test_secret_reference_rejects_malformed_contract(change: dict[str, object]) -> None:
    payload = _valid_reference()
    payload.update(change)
    with pytest.raises(SecretReferenceValidationError):
        validate_secret_reference_metadata(payload)


def test_secret_reference_rejects_non_object_and_missing_fields() -> None:
    with pytest.raises(SecretReferenceValidationError, match="must be an object"):
        validate_secret_reference_metadata(cast(dict[str, object], []))
    with pytest.raises(SecretReferenceValidationError, match="missing SecretReference fields"):
        validate_secret_reference_metadata({})


def test_secret_reference_rejects_invalid_optional_string_and_scope_items() -> None:
    invalid_provider = _valid_reference()
    invalid_provider["provider_class"] = ""
    with pytest.raises(SecretReferenceValidationError, match="provider_class"):
        validate_secret_reference_metadata(invalid_provider)

    invalid_scope = _valid_reference()
    invalid_scope["allowed_operation_scope"] = [cast(object, 1)]
    with pytest.raises(SecretReferenceValidationError, match="allowed_operation_scope"):
        validate_secret_reference_metadata(invalid_scope)


def test_secret_reference_defaults_optional_fields_and_scopes() -> None:
    payload = {
        "reference_id": "credential:minimal",
        "credential_class": "password",
        "store_adapter_class": "test.synthetic",
        "label": "Minimal reference",
        "status": "active",
    }
    reference = validate_secret_reference_metadata(payload)
    assert reference.provider_class is None
    assert reference.allowed_operation_scope == ()
    assert reference.allowed_destination_scope == ()
    assert reference.created_at is None


def test_secret_reference_accepts_lifecycle_timestamps() -> None:
    rotated = _valid_reference()
    rotated.update(
        {
            "status": "rotated",
            "rotated_at": "2026-06-19T01:00:00Z",
        }
    )
    revoked = _valid_reference()
    revoked.update(
        {
            "status": "revoked",
            "revoked_at": "2026-06-19T02:00:00Z",
        }
    )
    assert validate_secret_reference_metadata(rotated).status == "rotated"
    assert validate_secret_reference_metadata(revoked).status == "revoked"


def test_ordinary_state_allows_only_validated_secret_reference_for_secret_label() -> None:
    validate_ordinary_state_record(
        record_type="secret_reference",
        sensitivity="secret",
        metadata=_valid_reference(),
    )
    validate_ordinary_state_record(
        record_type="secret_reference",
        sensitivity="sensitive",
        metadata=_valid_reference(),
    )
    validate_ordinary_state_record(
        record_type="memory",
        sensitivity="personal",
        metadata={"content": "synthetic"},
    )
    with pytest.raises(SecretClassificationError, match="does not permit secret values"):
        validate_ordinary_state_record(
            record_type="memory",
            sensitivity="secret",
            metadata={"content": "synthetic"},
        )
    with pytest.raises(SecretClassificationError, match="require sensitive or secret"):
        validate_ordinary_state_record(
            record_type="secret_reference",
            sensitivity="personal",
            metadata=_valid_reference(),
        )


def test_secret_reference_is_reference_only_in_portable_state_locations() -> None:
    for location in ("ordinary_state", "export", "backup"):
        decision = evaluate_secret_handling(
            payload_kind="secret_reference",
            location=cast(SecretHandlingLocation, location),
        )
        assert decision.allowed is True
        assert decision.disposition == "reference_only"


def test_secret_reference_is_allowed_as_metadata_outside_portable_state() -> None:
    decision = evaluate_secret_handling(
        payload_kind="secret_reference",
        location="diagnostic",
    )
    assert decision.allowed is True
    assert decision.disposition == "allow"


def test_secret_classification_is_closed_enum() -> None:
    assert classify_secret_class("credential") == "credential"
    with pytest.raises(SecretClassificationError, match="unknown secret class"):
        classify_secret_class("invented")
