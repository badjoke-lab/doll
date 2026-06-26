from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.artifact import ArtifactInfo
from doll.project_state import ProjectService
from doll.resume_bundle import (
    BUNDLE_ROOT,
    ResumeBundleIntegrityError,
    ResumeBundleService,
    ResumeBundleValidationError,
    _canonical_json,
    _handoff_work,
    _integer_mapping,
    _is_within,
    _json_array,
    _json_object,
    _json_value,
    _jsonl_count,
    _missing_reference,
    _optional_string,
    _record_summary,
    _reject_json_constant,
    _required_int,
    _required_string,
    _unavailable_reference,
    _unique_object,
    _validate_archive_infos,
    _validate_member_limits,
    _validate_shareable_members,
    verify_resume_bundle,
)
from doll.secret_detection import SecretScanResult
from doll.state import RecordEnvelope, RecordSensitivity
from doll.state_package import _write_deterministic_zip
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService


@dataclass(slots=True)
class _FakeRepository:
    records: dict[str, RecordEnvelope]
    read_only: bool = True

    def get_record(self, record_id: str) -> RecordEnvelope:
        try:
            return self.records[record_id]
        except KeyError:
            raise KeyError(record_id) from None


def _record(
    record_id: str,
    *,
    record_type: str = "artifact",
    sensitivity: RecordSensitivity = "personal",
    title: str | None = "record",
) -> RecordEnvelope:
    return RecordEnvelope(
        id=record_id,
        record_type=record_type,
        schema_version=1,
        created_at="2026-06-26T00:00:00Z",
        updated_at="2026-06-26T00:00:00Z",
        revision=1,
        status="active",
        provenance="user-created",
        sensitivity=sensitivity,
        title=title,
        metadata={},
    )


def _artifact(path: str = "resume/reference.txt") -> ArtifactInfo:
    return ArtifactInfo(
        artifact_id="artifact-id",
        title="Reference artifact",
        artifact_type="text",
        managed_path=path,
        content_hash="0" * 64,
        size_bytes=1,
        created_by="user",
        operation_id="operation-id",
        created_at="2026-06-26T00:00:00Z",
        sensitivity="personal",
        format="txt",
        media_type="text/plain",
    )


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _bundle(tmp_path: Path) -> Path:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = ProjectService(repository).create_v2(
            name="Coverage project",
            description="Synthetic verifier fixture.",
            objective="Exercise Resume Bundle defensive validation.",
            in_scope=("Verifier",),
            out_of_scope=("Network",),
            success_criteria=("Malformed bundles fail closed",),
            project_status="active",
            started_at="2026-06-26T00:00:00Z",
        )
        WorkItemService(repository).create(
            project_id=project.project_id,
            kind="task",
            title="Verify bundle",
            description="Inspect one deterministic bundle.",
        )
        project_id = project.project_id
    output = tmp_path / "valid.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        ResumeBundleService(repository).export(project_id, output)
    return output


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _refresh_checksum(members: dict[str, bytes], member_name: str) -> None:
    checksum_name = f"{BUNDLE_ROOT}/checksums.json"
    checksums = json.loads(members[checksum_name])
    for entry in checksums["entries"]:
        if entry["path"] == member_name:
            content = members[member_name]
            entry["sha256"] = hashlib.sha256(content).hexdigest()
            entry["size_bytes"] = len(content)
            break
    members[checksum_name] = _json_bytes(checksums)


def _write_hostile(tmp_path: Path, name: str, members: dict[str, bytes]) -> Path:
    output = tmp_path / name
    _write_deterministic_zip(output, members)
    return output


def test_export_requires_read_only_repository(tmp_path: Path) -> None:
    repository = cast(StateRepository, _FakeRepository({}, read_only=False))
    with pytest.raises(ResumeBundleValidationError):
        ResumeBundleService(repository).export("project", tmp_path / "bundle.zip")


def test_reference_helpers_cover_missing_wrong_secret_and_valid_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = {
        "wrong": _record("wrong", record_type="memory"),
        "secret": _record("secret", sensitivity="secret"),
        "valid": _record("valid"),
        "source": _record("source", record_type="memory"),
        "secret-source": _record("secret-source", record_type="memory", sensitivity="secret"),
    }
    repository = cast(StateRepository, _FakeRepository(records))
    service = ResumeBundleService(repository)
    monkeypatch.setattr("doll.resume_bundle._artifact_from_record", lambda record: _artifact())

    artifact_refs, artifact_omissions = service._artifact_references(
        {"missing", "wrong", "secret", "valid"}
    )
    assert artifact_omissions == 1
    assert {item["availability"] for item in artifact_refs} == {
        "unavailable",
        "requires_separate_approved_export",
    }
    assert any(item.get("reason") == "missing_record" for item in artifact_refs)
    assert any(item.get("reason") == "wrong_record_type" for item in artifact_refs)

    source_refs, source_omissions = service._source_references(
        {"missing-source", "source", "secret-source"}
    )
    assert source_omissions == 1
    assert {item["availability"] for item in source_refs} == {
        "unavailable",
        "reference_only",
    }


def test_artifact_reference_rejects_unsafe_managed_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = cast(StateRepository, _FakeRepository({"valid": _record("valid")}))
    service = ResumeBundleService(repository)
    monkeypatch.setattr(
        "doll.resume_bundle._artifact_from_record",
        lambda record: _artifact("../escape.txt"),
    )
    with pytest.raises(ResumeBundleValidationError):
        service._artifact_references({"valid"})


def test_small_helpers_cover_success_and_failure_paths(tmp_path: Path) -> None:
    record = _record("record-id", record_type="memory", title=None)
    assert _record_summary(record)["record_id"] == "record-id"
    assert _missing_reference("missing", "source")["reason"] == "missing_record"
    assert _unavailable_reference(record, "wrong")["reason"] == "wrong"
    assert _handoff_work(()) == ["- none"]
    assert _is_within(tmp_path, tmp_path)
    assert _is_within(tmp_path / "child", tmp_path)
    assert not _is_within(tmp_path.parent, tmp_path)

    with pytest.raises(ResumeBundleValidationError):
        _canonical_json({"invalid": {1, 2}})
    with pytest.raises(ResumeBundleIntegrityError):
        _json_value(b'{"a":1,"a":2}', "duplicate")
    with pytest.raises(ResumeBundleIntegrityError):
        _json_value(b"NaN", "constant")
    with pytest.raises(ResumeBundleIntegrityError):
        _json_object(b"[]", "object")
    with pytest.raises(ResumeBundleIntegrityError):
        _json_array(b"{}", "array")
    with pytest.raises(ResumeBundleIntegrityError):
        _jsonl_count(b"\xff", "lines")
    with pytest.raises(ResumeBundleIntegrityError):
        _jsonl_count(b"{}\n\n", "lines")
    with pytest.raises(ResumeBundleIntegrityError):
        _jsonl_count(b"[]\n", "lines")
    with pytest.raises(ValueError):
        _unique_object([("a", 1), ("a", 2)])
    with pytest.raises(ValueError):
        _reject_json_constant("NaN")

    assert _required_string({"value": "ok"}, "value") == "ok"
    assert _required_int({"value": 0}, "value") == 0
    assert _optional_string(None) is None
    assert _optional_string("value") == "value"
    with pytest.raises(ResumeBundleIntegrityError):
        _required_string({}, "value")
    with pytest.raises(ResumeBundleIntegrityError):
        _required_int({"value": True}, "value")
    with pytest.raises(ResumeBundleIntegrityError):
        _optional_string(1)

    assert _integer_mapping({"counts": {"a": 1}}, "counts") == {"a": 1}
    with pytest.raises(ResumeBundleIntegrityError):
        _integer_mapping({"counts": []}, "counts")
    with pytest.raises(ResumeBundleIntegrityError):
        _integer_mapping(
            {"counts": cast(dict[str, object], {1: 1})},
            "counts",
        )
    with pytest.raises(ResumeBundleIntegrityError):
        _integer_mapping({"counts": {"a": -1}}, "counts")


def test_shareable_member_validation_rejects_binary_and_scan_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ResumeBundleValidationError):
        _validate_shareable_members({"binary": b"\xff"})
    with pytest.raises(ResumeBundleValidationError):
        _validate_shareable_members({"secret": b'api_key="sk-1234567890abcdefghijklmnop"'})

    def truncated_scan(text: str, *, max_scan_chars: int) -> SecretScanResult:
        del text, max_scan_chars
        return SecretScanResult(
            findings=(),
            input_characters=2,
            scanned_characters=1,
            input_truncated=True,
            finding_limit_reached=False,
        )

    monkeypatch.setattr("doll.resume_bundle.scan_secrets", truncated_scan)
    with pytest.raises(ResumeBundleValidationError):
        _validate_shareable_members({"text": b"ok"})


def test_member_and_archive_limits_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("doll.resume_bundle._MAX_MEMBER_BYTES", 2)
    monkeypatch.setattr("doll.resume_bundle._MAX_TOTAL_BYTES", 3)
    with pytest.raises(ResumeBundleValidationError):
        _validate_member_limits({"large": b"abc"}, ResumeBundleValidationError)
    with pytest.raises(ResumeBundleValidationError):
        _validate_member_limits({"one": b"ab", "two": b"ab"}, ResumeBundleValidationError)

    unsafe = zipfile.ZipInfo("../unsafe")
    with pytest.raises(ResumeBundleIntegrityError):
        _validate_archive_infos([unsafe])
    directory = zipfile.ZipInfo("directory/")
    with pytest.raises(ResumeBundleIntegrityError):
        _validate_archive_infos([directory])
    encrypted = zipfile.ZipInfo("member")
    encrypted.flag_bits = 1
    with pytest.raises(ResumeBundleIntegrityError):
        _validate_archive_infos([encrypted])
    oversized = zipfile.ZipInfo("member")
    oversized.file_size = 3
    with pytest.raises(ResumeBundleIntegrityError):
        _validate_archive_infos([oversized])


def test_verifier_rejects_unreadable_duplicate_and_wrong_inventory(
    tmp_path: Path,
) -> None:
    source = _bundle(tmp_path)
    members = _members(source)

    unreadable = tmp_path / "unreadable.zip"
    unreadable.write_bytes(b"not-a-zip")
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(unreadable)

    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
        archive.writestr(f"{BUNDLE_ROOT}/manifest.json", members[f"{BUNDLE_ROOT}/manifest.json"])
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(duplicate)

    missing = dict(members)
    missing.pop(f"{BUNDLE_ROOT}/source-references.jsonl")
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "missing.zip", missing))

    extra = dict(members)
    extra[f"{BUNDLE_ROOT}/extra.json"] = b"{}\n"
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "extra.zip", extra))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bundle_format_version", 99),
        ("checksum_algorithm", "sha512"),
        ("generated_at_or_reproducibility_mode", "timestamped"),
        ("selection_options", []),
        ("checkpoint_freshness", "future"),
        ("checkpoint_id", 1),
        ("generated_from_state_revision", True),
    ],
)
def test_verifier_rejects_invalid_manifest_values(
    tmp_path: Path,
    key: str,
    value: object,
) -> None:
    members = _members(_bundle(tmp_path))
    manifest_name = f"{BUNDLE_ROOT}/manifest.json"
    manifest = json.loads(members[manifest_name])
    manifest[key] = value
    members[manifest_name] = _json_bytes(manifest)
    _refresh_checksum(members, manifest_name)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, f"invalid-{key}.zip", members))


def test_verifier_rejects_secret_selection_and_identity_mismatches(
    tmp_path: Path,
) -> None:
    source = _bundle(tmp_path)

    members = _members(source)
    manifest_name = f"{BUNDLE_ROOT}/manifest.json"
    manifest = json.loads(members[manifest_name])
    manifest["selection_options"]["include_secret_records"] = True
    members[manifest_name] = _json_bytes(manifest)
    _refresh_checksum(members, manifest_name)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "secret-option.zip", members))

    members = _members(source)
    project_name = f"{BUNDLE_ROOT}/project.json"
    project = json.loads(members[project_name])
    project["project_id"] = "different"
    members[project_name] = _json_bytes(project)
    _refresh_checksum(members, project_name)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "project-id.zip", members))

    members = _members(source)
    checkpoint_name = f"{BUNDLE_ROOT}/checkpoint.json"
    members[checkpoint_name] = b"{}\n"
    _refresh_checksum(members, checkpoint_name)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "checkpoint-id.zip", members))


def test_verifier_rejects_checksum_contract_failures(tmp_path: Path) -> None:
    source = _bundle(tmp_path)
    checksum_name = f"{BUNDLE_ROOT}/checksums.json"

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["algorithm"] = "sha512"
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "algorithm.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"] = {}
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "entries.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"][0] = "invalid"
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "entry.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"][0]["sha256"] = "short"
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "digest.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"].reverse()
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "order.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"].pop()
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "incomplete.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"][0]["sha256"] = "0" * 64
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "mismatch.zip", members))

    members = _members(source)
    checksums = json.loads(members[checksum_name])
    checksums["entries"][-1]["path"] = f"{BUNDLE_ROOT}/zzzz.json"
    members[checksum_name] = _json_bytes(checksums)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "missing-member.zip", members))


def test_verifier_rejects_missing_handoff_notice(tmp_path: Path) -> None:
    members = _members(_bundle(tmp_path))
    handoff_name = f"{BUNDLE_ROOT}/HANDOFF.md"
    members[handoff_name] = b"# Derived output\n"
    _refresh_checksum(members, handoff_name)
    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(_write_hostile(tmp_path, "handoff.zip", members))
