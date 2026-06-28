from __future__ import annotations

from doll.model_switch import (
    MODEL_SWITCH_PROBE_INPUT,
    MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS,
    MODEL_SWITCH_PROBE_TIMEOUT_SECONDS,
    validate_model_switch_probe_output,
)


def test_probe_contract_accepts_exact_and_harmless_uppercase_prefix_variation() -> None:
    assert validate_model_switch_probe_output("DOLL_SWITCH_OK")
    assert validate_model_switch_probe_output("DOLDRUM_SWITCH_OK")
    assert validate_model_switch_probe_output("  LOCAL_MODEL_SWITCH_OK\n")


def test_probe_contract_rejects_empty_explanatory_or_malformed_output() -> None:
    rejected = (
        None,
        "",
        "   ",
        "wrong response",
        'The response "DOLL_SWITCH_OK" passed.',
        "DOLL_SWITCH_OK.",
        "doll_switch_ok",
        "SWITCH_OK",
        "DOLL-SWITCH-OK",
        "A" * 48 + "_SWITCH_OK",
    )
    assert all(not validate_model_switch_probe_output(value) for value in rejected)


def test_probe_request_is_bounded_explicit_and_slow_cpu_compatible() -> None:
    assert "local_model_switch_smoke_test" in MODEL_SWITCH_PROBE_INPUT
    assert "ending in _SWITCH_OK" in MODEL_SWITCH_PROBE_INPUT
    assert MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS == 64
    assert MODEL_SWITCH_PROBE_TIMEOUT_SECONDS == 60.0
