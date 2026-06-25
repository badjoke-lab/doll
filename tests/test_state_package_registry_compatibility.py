from __future__ import annotations

import pytest

import doll.state_package as package
from doll.state_package_registry import (
    PACKAGE_SYSTEM_CATEGORIES,
    AuthoritativeRecordCategory,
    AuthoritativeRecordRegistry,
)


def _compatibility_registry() -> AuthoritativeRecordRegistry:
    return AuthoritativeRecordRegistry(
        2,
        (
            AuthoritativeRecordCategory(
                "required_record",
                "records/required-records.jsonl",
                True,
                "required_record",
            ),
            AuthoritativeRecordCategory(
                "optional_record",
                "records/optional-records.jsonl",
                False,
                "optional_record",
            ),
        ),
    )


def test_manifest_categories_allow_legacy_optional_omission() -> None:
    registry = _compatibility_registry()
    included = frozenset({"required_record", *PACKAGE_SYSTEM_CATEGORIES})

    actual = package._validate_manifest_categories(
        {
            "included_categories": sorted(included),
            "excluded_categories": ["optional_record"],
        },
        registry,
    )

    assert actual == included


def test_manifest_categories_still_require_required_categories() -> None:
    registry = _compatibility_registry()

    with pytest.raises(package.StatePackageValidationError):
        package._validate_manifest_categories(
            {
                "included_categories": sorted(PACKAGE_SYSTEM_CATEGORIES),
                "excluded_categories": [],
            },
            registry,
        )
