from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from doll import state, workspace
from doll.project_state import ProjectService
from doll.resume_bundle import (
    BUNDLE_ROOT,
    ResumeBundleExportError,
    ResumeBundleIntegrityError,
    ResumeBundleService,
    ResumeBundleValidationError,
    verify_resume_bundle,
)
from doll.state_package import _write_deterministic_zip
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, *, secret_text: str | None = None) -> str:
    project = ProjectService(repository).create_v2(
        name="Resume Bundle hardening project",
        description="Synthetic hardening fixture.",
        objective="Reject unsafe or incomplete Resume Bundle publication.",
        in_scope=("Resume Bundle hardening",),
        out_of_scope=("Network activity",),
        success_criteria=("Unsafe output is never published",),
        project_status="active",
        started_at="2026-06-26T00:00:00Z",
    )
    WorkItemService(repository).create(
        project_id=project.project_id,
        kind="task",
        title="Inspect hardened export",
        description=secret_text or "Generate and verify one bounded bundle.",
        priority=10,
    )
    return project.project_id


def _rewrite_checksum(members: dict[str, bytes], member_name: str) -> None:
    checksum_name = f"{BUNDLE_ROOT}/checksums.json"
    checksums = json.loads(members[checksum_name])
    for entry in checksums["entries"]:
        if entry["path"] == member_name:
            content = members[member_name]
            entry["sha256"] = hashlib.sha256(content).hexdigest()
            entry["size_bytes"] = len(content)
            break
    members[checksum_name] = (
        json.dumps(
            checksums,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def test_resume_bundle_rejects_output_inside_workspace(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
    output = initialized.root / "inside.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ResumeBundleValidationError):
            ResumeBundleService(repository).export(project_id, output)

    assert not output.exists()


def test_resume_bundle_rejects_detected_secret_text(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    token = "sk-1234567890abcdefghijklmnop"
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository, secret_text=f'api_key = "{token}"')
    output = tmp_path / "secret.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ResumeBundleValidationError):
            ResumeBundleService(repository).export(project_id, output)

    assert not output.exists()


def test_resume_bundle_failed_writer_cleans_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
    output = tmp_path / "failed.zip"

    def fail_after_partial_write(path: Path, members: dict[str, bytes]) -> None:
        del members
        path.write_bytes(b"partial")
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(
        "doll.resume_bundle._write_deterministic_zip",
        fail_after_partial_write,
    )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ResumeBundleExportError):
            ResumeBundleService(repository).export(project_id, output)

    assert not output.exists()
    assert not tuple(tmp_path.glob(".failed.zip.*.tmp"))


def test_resume_bundle_existing_output_is_preserved(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
    output = tmp_path / "existing.zip"
    output.write_bytes(b"keep")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ResumeBundleExportError):
            ResumeBundleService(repository).export(project_id, output)

    assert output.read_bytes() == b"keep"


def test_resume_bundle_verifier_rejects_non_utf8_handoff(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        ResumeBundleService(repository).export(project_id, source)

    with zipfile.ZipFile(source, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    handoff_name = f"{BUNDLE_ROOT}/HANDOFF.md"
    members[handoff_name] = b"\xff"
    _rewrite_checksum(members, handoff_name)
    hostile = tmp_path / "hostile-utf8.zip"
    _write_deterministic_zip(hostile, members)

    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(hostile)


def test_resume_bundle_verifier_rejects_inconsistent_counts(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        ResumeBundleService(repository).export(project_id, source)

    with zipfile.ZipFile(source, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest_name = f"{BUNDLE_ROOT}/manifest.json"
    manifest = json.loads(members[manifest_name])
    manifest["included_record_counts"]["next_work_items"] += 1
    members[manifest_name] = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    _rewrite_checksum(members, manifest_name)
    hostile = tmp_path / "hostile-counts.zip"
    _write_deterministic_zip(hostile, members)

    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(hostile)
