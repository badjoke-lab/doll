from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from doll.state_package import (
    PACKAGE_ROOT,
    StatePackageIntegrityError,
    StatePackageLimitError,
    StatePackageUnsafePathError,
    StatePackageValidationError,
    _canonical_json,
    _load_jsonl_bytes,
    _required_nonnegative_int,
    _required_positive_int,
    _validate_checksums,
    _validate_member_name,
)


def test_state_package_validation_helpers() -> None:
    with pytest.raises(StatePackageUnsafePathError):
        _validate_member_name("")
    with pytest.raises(StatePackageUnsafePathError):
        _validate_member_name(f"{PACKAGE_ROOT}/./x")
    with pytest.raises(StatePackageUnsafePathError):
        _validate_member_name(f"{PACKAGE_ROOT}/bad\x00name")
    with pytest.raises(StatePackageUnsafePathError):
        _validate_member_name(f"{PACKAGE_ROOT}/records\\escape")
    with pytest.raises(StatePackageValidationError):
        _required_nonnegative_int({"x": True}, "x")
    with pytest.raises(StatePackageValidationError):
        _required_positive_int({"x": 0}, "x")
    with pytest.raises(StatePackageValidationError):
        _canonical_json(float("nan"))
    with pytest.raises(StatePackageValidationError):
        _load_jsonl_bytes(b"{}\n\n", "test")
    with pytest.raises(StatePackageValidationError):
        _load_jsonl_bytes(b"{}", "test")
    with pytest.raises(StatePackageValidationError):
        _validate_checksums([])
    with pytest.raises(StatePackageValidationError):
        _validate_checksums({"algorithm": "md5", "entries": []})
    with pytest.raises(StatePackageValidationError):
        _validate_checksums({"algorithm": "sha256", "entries": {}})


def test_duplicate_casefold_members_are_rejected(tmp_path: Path) -> None:
    package = tmp_path / "collision.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(f"{PACKAGE_ROOT}/A", b"a")
        archive.writestr(f"{PACKAGE_ROOT}/a", b"b")
    from doll.state_package import verify_state_package

    with pytest.raises(StatePackageUnsafePathError):
        verify_state_package(package)


def test_missing_checksums_is_rejected(tmp_path: Path) -> None:
    package = tmp_path / "missing.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(f"{PACKAGE_ROOT}/manifest.json", json.dumps({}))
    from doll.state_package import verify_state_package

    with pytest.raises(StatePackageIntegrityError):
        verify_state_package(package)


def test_member_size_limit_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import doll.state_package as module

    monkeypatch.setattr(module, "MAX_PACKAGE_MEMBER_BYTES", 1)
    package = tmp_path / "large.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(f"{PACKAGE_ROOT}/x", b"xx")
    with pytest.raises(StatePackageLimitError):
        module.verify_state_package(package)
