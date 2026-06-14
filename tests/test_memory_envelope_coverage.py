from __future__ import annotations

from typing import cast

import pytest

from doll.memory import MemoryValidationError, _validate_memory_envelope
from doll.state import RecordEnvelope, RecordSensitivity


def envelope(
    *,
    revision: int = 1,
    sensitivity: RecordSensitivity = "personal",
    created_at: str = "2026-06-14T00:00:00Z",
) -> RecordEnvelope:
    return RecordEnvelope(
        id="00000000-0000-0000-0000-000000000001",
        record_type="memory",
        schema_version=1,
        created_at=created_at,
        updated_at="2026-06-14T00:00:00Z",
        revision=revision,
        status="active",
        provenance="user-confirmed",
        sensitivity=sensitivity,
        title="subject",
        metadata={},
    )


def test_memory_envelope_rejects_non_positive_revision() -> None:
    with pytest.raises(MemoryValidationError, match="revision"):
        _validate_memory_envelope(envelope(revision=0))


def test_memory_envelope_rejects_unknown_sensitivity() -> None:
    with pytest.raises(MemoryValidationError, match="sensitivity"):
        _validate_memory_envelope(envelope(sensitivity=cast(RecordSensitivity, "unknown")))


def test_memory_envelope_rejects_missing_timestamp() -> None:
    with pytest.raises(MemoryValidationError, match="timestamps"):
        _validate_memory_envelope(envelope(created_at=cast(str, None)))
