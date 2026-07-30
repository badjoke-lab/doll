from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from doll.local_failure_guidance import (
    LOCAL_FAILURE_GUIDANCE_CODES,
    guidance_for_runtime_failure,
)

_FORBIDDEN_GUIDANCE_TEXT = (
    "api key",
    "automatic download",
    "automatic install",
    "automatic switch",
    "cloud",
    "http://",
    "https://",
    "provider login",
    "remote upload",
    "run a shell",
    "tool execution",
)


def test_every_runtime_failure_code_has_bounded_local_only_guidance() -> None:
    assert LOCAL_FAILURE_GUIDANCE_CODES == (
        "adapter_not_configured",
        "adapter_failure",
        "cancelled",
        "invalid_response",
        "model_not_found",
        "resource_limit",
        "runtime_unavailable",
        "timeout",
        "unsupported_operation",
    )

    guidance_ids: set[str] = set()
    for failure_code in LOCAL_FAILURE_GUIDANCE_CODES:
        guidance = guidance_for_runtime_failure(failure_code)
        guidance_ids.add(guidance.guidance_id)

        assert guidance.failure_code == failure_code
        assert guidance.guidance_id.startswith("doll.local-runtime.")
        assert guidance.guidance_id.endswith(".v1")
        assert 1 <= len(guidance.summary) <= 160
        assert 2 <= len(guidance.available_options) <= 4
        assert guidance.state_preserved is True
        assert guidance.automatic_action_taken is False
        assert guidance.cloud_fallback_used is False

        visible_text = " ".join((guidance.summary, *guidance.available_options)).lower()
        assert all(token not in visible_text for token in _FORBIDDEN_GUIDANCE_TEXT)
        assert all(
            option.strip() == option and 1 <= len(option) <= 180
            for option in guidance.available_options
        )

    assert len(guidance_ids) == len(LOCAL_FAILURE_GUIDANCE_CODES)


def test_guidance_is_immutable_and_repeatable() -> None:
    first = guidance_for_runtime_failure("runtime_unavailable")
    second = guidance_for_runtime_failure("runtime_unavailable")

    assert first is second
    with pytest.raises(FrozenInstanceError):
        first.summary = "changed"  # type: ignore[misc]
