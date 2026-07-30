"""Deterministic local-only guidance for closed runtime failure codes."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from doll.runtime_adapter import RuntimeFailureCode


@dataclass(frozen=True, slots=True)
class LocalFailureGuidance:
    """Provider-neutral options for one failed local runtime turn."""

    guidance_id: str
    failure_code: RuntimeFailureCode
    summary: str
    available_options: tuple[str, ...]
    state_preserved: bool = True
    automatic_action_taken: bool = False
    cloud_fallback_used: bool = False


LOCAL_FAILURE_GUIDANCE_CODES: Final[tuple[RuntimeFailureCode, ...]] = (
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


def _guidance(
    failure_code: RuntimeFailureCode,
    summary: str,
    *available_options: str,
) -> LocalFailureGuidance:
    return LocalFailureGuidance(
        guidance_id=f"doll.local-runtime.{failure_code.replace('_', '-')}.v1",
        failure_code=failure_code,
        summary=summary,
        available_options=available_options,
    )


_GUIDANCE = MappingProxyType(
    {
        "adapter_not_configured": _guidance(
            "adapter_not_configured",
            "No approved local runtime adapter is configured for this turn.",
            "Configure an approved local runtime adapter.",
            (
                "Continue with local state inspection, export, backup, or recovery "
                "without model execution."
            ),
        ),
        "adapter_failure": _guidance(
            "adapter_failure",
            "The selected local runtime adapter failed without returning usable output.",
            "Retry the request locally.",
            "Inspect local runtime health.",
            "Manually switch to an approved local fallback binding.",
        ),
        "cancelled": _guidance(
            "cancelled",
            "The local runtime request was cancelled before completion.",
            "Submit the request again when ready.",
            ("Continue with local state inspection or recovery without model execution."),
        ),
        "invalid_response": _guidance(
            "invalid_response",
            "The local runtime returned an empty, malformed, or unsafe response.",
            "Retry the request locally.",
            "Inspect the selected local runtime and model.",
            "Manually switch to an approved local fallback binding.",
        ),
        "model_not_found": _guidance(
            "model_not_found",
            "The selected approved local model is not available to the runtime.",
            "Inspect the local model inventory.",
            "Manually activate an approved installed local model or fallback binding.",
            (
                "Continue with local state inspection, export, backup, or recovery "
                "without model execution."
            ),
        ),
        "resource_limit": _guidance(
            "resource_limit",
            "The local request exceeded an available runtime resource limit.",
            "Reduce the request, selected context, or output limit.",
            "Use reduced-context mode.",
            "Manually switch to a lighter approved local model.",
        ),
        "runtime_unavailable": _guidance(
            "runtime_unavailable",
            "The configured local runtime is currently unavailable.",
            "Start or repair the configured local runtime.",
            "Inspect local runtime health.",
            "Manually switch to an approved local fallback binding.",
            (
                "Continue with local state inspection, export, backup, or recovery "
                "without model execution."
            ),
        ),
        "timeout": _guidance(
            "timeout",
            "The local runtime did not finish before the configured timeout.",
            "Retry with a smaller request or selected context.",
            "Increase the local timeout within the configured limit.",
            "Manually switch to a lighter approved local model.",
        ),
        "unsupported_operation": _guidance(
            "unsupported_operation",
            "The selected local runtime adapter does not support this operation.",
            "Use an approved local adapter that supports this operation.",
            (
                "Continue with local state inspection, export, backup, or recovery "
                "without model execution."
            ),
        ),
    }
)


def guidance_for_runtime_failure(
    failure_code: RuntimeFailureCode,
) -> LocalFailureGuidance:
    """Return the immutable guidance payload for one accepted failure code."""

    try:
        return _GUIDANCE[failure_code]
    except KeyError as exc:  # pragma: no cover - RuntimeFailureCode is closed
        raise ValueError("unsupported local runtime failure code") from exc
