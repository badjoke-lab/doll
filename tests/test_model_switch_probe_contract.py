from __future__ import annotations

from doll.model_switch import (
    MODEL_SWITCH_PROBE_INPUT,
    MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS,
    MODEL_SWITCH_PROBE_TIMEOUT_SECONDS,
    validate_model_switch_probe_output,
)


def test_probe_contract_accepts_nonempty_bounded_generation_without_semantic_coupling() -> None:
    assert validate_model_switch_probe_output("DOLL_SWITCH_OK")
    assert validate_model_switch_probe_output("DOLDRUM_SWITCH_OK")
    assert validate_model_switch_probe_output("A local model response with ordinary prose.\n")


def test_probe_contract_rejects_empty_nul_or_oversized_output() -> None:
    rejected = (
        None,
        "",
        "   ",
        "valid-looking\x00text",
        "A" * (MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS + 1),
    )
    assert all(not validate_model_switch_probe_output(value) for value in rejected)


def test_probe_request_is_bounded_non_authoritative_and_slow_cpu_compatible() -> None:
    assert "local_model_switch_smoke_test" in MODEL_SWITCH_PROBE_INPUT
    assert "response is discarded and grants no authority" in MODEL_SWITCH_PROBE_INPUT
    assert MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS == 2_048
    assert MODEL_SWITCH_PROBE_TIMEOUT_SECONDS == 60.0
