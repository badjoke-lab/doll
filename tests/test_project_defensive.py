from __future__ import annotations

from typing import cast

import pytest

from doll.project_state import (
    ProjectDecisionValidationError,
    _deterministic_json,
    _metadata_list,
    _optional_string,
    _required_string,
    _validate_decision_status,
    _validate_optional_reference_id,
    _validate_project_status,
    _validate_reference_ids,
    _validate_text,
    _validate_text_items,
    _validate_utc,
)


def test_project_decision_validation_helpers() -> None:
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text("x", cast(str, 1), 10)
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text("x", "", 10)
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text("x", "bad\x00", 10)
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text_items("items", cast(object, "x"))  # type: ignore[arg-type]
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text_items("items", ["x", "x"])
    with pytest.raises(ProjectDecisionValidationError):
        _validate_project_status("unknown")
    with pytest.raises(ProjectDecisionValidationError):
        _validate_decision_status("unknown")
    with pytest.raises(ProjectDecisionValidationError):
        _validate_utc("time", "bad")
    with pytest.raises(ProjectDecisionValidationError):
        _validate_utc("time", "badZ")
    with pytest.raises(ProjectDecisionValidationError):
        _validate_reference_ids("ids", cast(object, "id"))  # type: ignore[arg-type]
    with pytest.raises(ProjectDecisionValidationError):
        _validate_reference_ids("ids", [cast(str, 1)])
    with pytest.raises(ProjectDecisionValidationError):
        _validate_reference_ids(
            "ids",
            ["00000000-0000-0000-0000-000000000001"] * 2,
        )
    assert _validate_optional_reference_id("id", None) is None


def test_metadata_helpers_and_json() -> None:
    with pytest.raises(ProjectDecisionValidationError):
        _required_string({}, "x")
    assert _optional_string({}, "x") is None
    with pytest.raises(ProjectDecisionValidationError):
        _optional_string({"x": 1}, "x")
    with pytest.raises(ProjectDecisionValidationError):
        _metadata_list({}, "x")
    assert _deterministic_json({"b": 1, "a": "日本語"}) == ('{"a":"日本語","b":1}\n')
