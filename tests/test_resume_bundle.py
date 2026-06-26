from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.checkpoint import ProjectCheckpointService
from doll.cli import app
from doll.procedure import ProcedureService
from doll.project_state import DecisionService, ProjectService
from doll.resume_bundle import (
    BUNDLE_ROOT,
    ResumeBundleIntegrityError,
    ResumeBundleService,
    verify_resume_bundle,
)
from doll.settings import PolicyService
from doll.state_package import _write_deterministic_zip
from doll.state_repository import StateRepository
from doll.work_item import AcceptanceCriterion, WorkItemService

runner = CliRunner()


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _fixture(repository: StateRepository) -> tuple[str, dict[str, str]]:
    policy = PolicyService(repository).create(
        key="resume.local-only",
        rule="Resume Bundle generation remains local and read-only.",
        enabled=True,
    )
    decision = DecisionService(repository).create(
        decision="Export references only",
        reason="Artifact bytes require a separate approved export.",
        decision_status="accepted",
        decided_at="2026-06-25T00:10:00Z",
    )
    artifact = WorkspaceFileService(repository).create_bytes(
        managed_path="resume/reference.txt",
        content=b"artifact content is not copied into bundle v1\n",
        title="Resume reference artifact",
        artifact_type="text",
        format="txt",
        media_type="text/plain",
    )
    project = ProjectService(repository).create_v2(
        name="Resume Bundle project",
        description="Synthetic deterministic Resume Bundle fixture.",
        objective="Export an inspectable deterministic project handoff.",
        in_scope=("Resume Bundle",),
        out_of_scope=("Artifact bytes",),
        success_criteria=("Two exports are byte-for-byte identical",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
        decision_ids=(decision.decision_id,),
        artifact_ids=(artifact.artifact_id,),
        governing_policy_ids=(policy.record_id,),
    )
    work = WorkItemService(repository)
    active = work.create(
        project_id=project.project_id,
        kind="task",
        title="Implement Resume Bundle",
        description="Build deterministic export and verification.",
        priority=10,
        artifact_ids=(artifact.artifact_id,),
    )
    active = work.transition(
        active.work_item_id,
        expected_revision=active.revision,
        to_status="in_progress",
    )
    ready = work.create(
        project_id=project.project_id,
        kind="task",
        title="Run continuity gate",
        description="Next project-continuity acceptance step.",
        priority=20,
    )
    blocker = work.create(
        project_id=project.project_id,
        kind="investigation",
        title="Resolve selection edge cases",
        description="Current blocker record.",
        priority=5,
    )
    blocked = work.create(
        project_id=project.project_id,
        kind="task",
        title="Finalize handoff",
        description="Blocked handoff work.",
        priority=30,
        acceptance_criteria=(
            AcceptanceCriterion(
                "bundle-checksums",
                "Bundle checksums must verify.",
                "record",
                True,
            ),
        ),
    )
    blocked = work.transition(
        blocked.work_item_id,
        expected_revision=blocked.revision,
        to_status="blocked",
        blocked_by_ids=(blocker.work_item_id,),
    )
    secret = work.create(
        project_id=project.project_id,
        kind="review",
        title="SECRET BUNDLE TEXT",
        description="Must not appear in normal Resume Bundle output.",
        sensitivity="secret",
    )
    procedure = ProcedureService(repository).create_approved(
        project_id=project.project_id,
        title="Inspect Resume Bundle",
        purpose="Verify checksums and inspect machine-readable files.",
        version=1,
        ordered_steps=("Open manifest.json and checksums.json.",),
        validation_steps=("Verify every listed SHA-256 digest.",),
        rollback_steps=("Delete the derived bundle if validation fails.",),
    )
    checkpoint_service = ProjectCheckpointService(repository)
    proposed = checkpoint_service.propose(
        project_id=project.project_id,
        as_of="2026-06-25T03:00:00Z",
        summary="Resume Bundle implementation is active.",
        current_phase="Phase 4B",
        current_goal="Complete deterministic Resume Bundle export.",
        active_work_item_ids=(active.work_item_id,),
        next_work_item_ids=(ready.work_item_id, blocker.work_item_id),
        blocked_work_item_ids=(blocked.work_item_id,),
        required_validation_ids=(blocker.work_item_id,),
        actor_type="model",
    )
    checkpoint = checkpoint_service.confirm(
        proposed.checkpoint_id,
        expected_revision=proposed.revision,
    )
    return project.project_id, {
        "artifact": artifact.artifact_id,
        "active": active.work_item_id,
        "ready": ready.work_item_id,
        "blocked": blocked.work_item_id,
        "secret": secret.work_item_id,
        "procedure": procedure.procedure_id,
        "checkpoint": checkpoint.checkpoint_id,
    }


def _snapshot(repository: StateRepository) -> tuple[int, tuple[tuple[str, int], ...], int]:
    revisions = tuple(
        (cast(str, row[0]), cast(int, row[1]))
        for row in repository.connection.execute(
            "SELECT id, revision FROM records ORDER BY id"
        ).fetchall()
    )
    audits = cast(
        int,
        repository.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
    )
    return repository.status().state_revision, revisions, audits


def test_resume_bundle_is_deterministic_scoped_and_integrity_checkable(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, ids = _fixture(repository)
        before = _snapshot(repository)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        first_inspection = ResumeBundleService(repository).export(project_id, first)
        second_inspection = ResumeBundleService(repository).export(project_id, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_inspection == second_inspection
    assert first_inspection.project_id == project_id
    assert first_inspection.checkpoint_id == ids["checkpoint"]
    assert first_inspection.checkpoint_freshness == "current"
    assert first_inspection.member_count == 14
    assert verify_resume_bundle(first) == first_inspection

    with zipfile.ZipFile(first, "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(f"{BUNDLE_ROOT}/manifest.json"))
        handoff = archive.read(f"{BUNDLE_ROOT}/HANDOFF.md").decode("utf-8")
        artifact_refs = archive.read(
            f"{BUNDLE_ROOT}/artifact-references.jsonl"
        ).decode("utf-8")
        entire_bundle = b"".join(archive.read(name) for name in archive.namelist())

    assert names == {
        f"{BUNDLE_ROOT}/manifest.json",
        f"{BUNDLE_ROOT}/project.json",
        f"{BUNDLE_ROOT}/checkpoint.json",
        f"{BUNDLE_ROOT}/active-work-items.jsonl",
        f"{BUNDLE_ROOT}/next-work-items.jsonl",
        f"{BUNDLE_ROOT}/blocked-work-items.jsonl",
        f"{BUNDLE_ROOT}/decisions.jsonl",
        f"{BUNDLE_ROOT}/procedures.jsonl",
        f"{BUNDLE_ROOT}/relevant-policies.jsonl",
        f"{BUNDLE_ROOT}/validation-requirements.json",
        f"{BUNDLE_ROOT}/artifact-references.jsonl",
        f"{BUNDLE_ROOT}/source-references.jsonl",
        f"{BUNDLE_ROOT}/HANDOFF.md",
        f"{BUNDLE_ROOT}/checksums.json",
    }
    assert manifest["generated_at_or_reproducibility_mode"] == "reproducible"
    assert manifest["selection_options"]["artifact_content"] == "references_only"
    assert "generated and non-authoritative" in handoff
    assert "Implement Resume Bundle" in handoff
    assert "Finalize handoff" in handoff
    assert ids["artifact"] in artifact_refs
    assert "requires_separate_approved_export" in artifact_refs
    assert b"artifact content is not copied" not in entire_bundle
    assert b"SECRET BUNDLE TEXT" not in entire_bundle
    assert str(initialized.root).encode() not in entire_bundle

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        after = _snapshot(repository)
    assert after == before


def test_resume_bundle_cli_and_fresh_process(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, _ = _fixture(repository)
    cli_output = tmp_path / "cli.zip"
    result = runner.invoke(
        app,
        [
            "project",
            "resume",
            "export",
            project_id,
            "--output",
            str(cli_output),
            "--workspace",
            str(initialized.root),
        ],
    )
    assert result.exit_code == 0
    assert cli_output.exists()
    assert verify_resume_bundle(cli_output).project_id == project_id

    process_output = tmp_path / "process.zip"
    environment = dict(os.environ)
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "doll",
            "project",
            "resume",
            "export",
            project_id,
            "--output",
            str(process_output),
            "--workspace",
            str(initialized.root),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert process_output.read_bytes() == cli_output.read_bytes()


def test_resume_bundle_rejects_tampering(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, _ = _fixture(repository)
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        ResumeBundleService(repository).export(project_id, source)

    with zipfile.ZipFile(source, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members[f"{BUNDLE_ROOT}/HANDOFF.md"] += b"tampered\n"
    hostile = tmp_path / "hostile.zip"
    _write_deterministic_zip(hostile, members)

    with pytest.raises(ResumeBundleIntegrityError):
        verify_resume_bundle(hostile)
