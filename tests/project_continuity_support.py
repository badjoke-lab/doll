from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import doll.state_package as package
from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.checkpoint import ProjectCheckpointService
from doll.procedure import ProcedureService
from doll.project_state import DecisionService, ProjectService
from doll.project_status import ProjectStatusService
from doll.resume_bundle import ResumeBundleService, verify_resume_bundle
from doll.settings import PolicyService
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService


@dataclass(frozen=True, slots=True)
class ProjectContinuityFixture:
    project_id: str
    artifact_id: str
    active_work_id: str
    ready_work_id: str
    blocker_work_id: str
    blocked_work_id: str
    procedure_id: str
    checkpoint_id: str
    secret_work_id: str | None


def initialize_workspace(tmp_path: Path, name: str) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def create_project_continuity_fixture(
    repository: StateRepository,
    *,
    include_secret: bool,
) -> ProjectContinuityFixture:
    policy = PolicyService(repository).create(
        key="continuity.local-only",
        rule="Project continuity remains local and inspectable.",
        enabled=True,
    )
    decision = DecisionService(repository).create(
        decision="Preserve project state independently of imported content",
        reason="Continuity records remain authoritative and model-independent.",
        decision_status="accepted",
        decided_at="2026-06-26T00:10:00Z",
    )
    artifact = WorkspaceFileService(repository).create_text(
        managed_path="continuity/evidence.txt",
        text="project continuity artifact bytes\n",
        title="Project continuity evidence",
        operation_id="imp-046-artifact",
    )
    project = ProjectService(repository).create_v2(
        name="Project continuity transfer fixture",
        description="Synthetic IMP-046 transfer and recovery fixture.",
        objective="Preserve inspectable project state through transfer and recovery.",
        in_scope=("Package transfer", "Backup restore", "Fresh-process inspection"),
        out_of_scope=("Model execution", "Network operations"),
        success_criteria=("Project state remains current after recovery",),
        project_status="active",
        started_at="2026-06-26T00:00:00Z",
        decision_ids=(decision.decision_id,),
        artifact_ids=(artifact.artifact_id,),
        governing_policy_ids=(policy.record_id,),
    )
    work = WorkItemService(repository)
    active = work.create(
        project_id=project.project_id,
        kind="task",
        title="Verify package transfer",
        description="Transfer project continuity records through package v2.",
        priority=10,
        source_decision_ids=(decision.decision_id,),
        artifact_ids=(artifact.artifact_id,),
    )
    active = work.transition(
        active.work_item_id,
        expected_revision=active.revision,
        to_status="in_progress",
        occurred_at="2026-06-26T01:00:00Z",
    )
    ready = work.create(
        project_id=project.project_id,
        kind="task",
        title="Run final project-continuity gate",
        description="Execute the later PROJ acceptance suite.",
        priority=20,
    )
    blocker = work.create(
        project_id=project.project_id,
        kind="investigation",
        title="Inspect recovery evidence",
        description="Review transfer and restore evidence before the final gate.",
        priority=5,
    )
    blocked = work.create(
        project_id=project.project_id,
        kind="task",
        title="Promote Phase 4B claim",
        description="Remain blocked until the final acceptance gate passes.",
        priority=30,
    )
    blocked = work.transition(
        blocked.work_item_id,
        expected_revision=blocked.revision,
        to_status="blocked",
        blocked_by_ids=(blocker.work_item_id,),
    )
    secret_work_id: str | None = None
    if include_secret:
        secret_work_id = work.create(
            project_id=project.project_id,
            kind="review",
            title="PRIVATE IMP-046 MARKER",
            description="This synthetic secret record must be omitted from normal exports.",
            sensitivity="secret",
        ).work_item_id
    procedure = ProcedureService(repository).create_approved(
        project_id=project.project_id,
        title="Inspect recovered project continuity",
        purpose="Inspect transferred state without granting execution authority.",
        version=1,
        ordered_steps=("Open the recovered workspace read-only.",),
        validation_steps=("Verify project status and Resume Bundle integrity.",),
        rollback_steps=("Discard the derived inspection output if verification fails.",),
    )
    checkpoint_service = ProjectCheckpointService(repository)
    proposed = checkpoint_service.propose(
        project_id=project.project_id,
        as_of="2026-06-26T02:00:00Z",
        summary="Transfer and recovery coverage is active.",
        current_phase="Phase 4B",
        current_goal="Complete project-continuity transfer and recovery coverage.",
        active_work_item_ids=(active.work_item_id,),
        next_work_item_ids=(blocker.work_item_id, ready.work_item_id),
        blocked_work_item_ids=(blocked.work_item_id,),
        required_validation_ids=(blocker.work_item_id,),
        actor_type="model",
    )
    checkpoint = checkpoint_service.confirm(
        proposed.checkpoint_id,
        expected_revision=proposed.revision,
    )
    return ProjectContinuityFixture(
        project_id=project.project_id,
        artifact_id=artifact.artifact_id,
        active_work_id=active.work_item_id,
        ready_work_id=ready.work_item_id,
        blocker_work_id=blocker.work_item_id,
        blocked_work_id=blocked.work_item_id,
        procedure_id=procedure.procedure_id,
        checkpoint_id=checkpoint.checkpoint_id,
        secret_work_id=secret_work_id,
    )


def assert_project_continuity(
    workspace_root: Path,
    fixture: ProjectContinuityFixture,
    bundle_output: Path,
) -> None:
    with state.open_state_repository(workspace_root, read_only=True) as repository:
        project = ProjectService(repository).get(fixture.project_id)
        active = WorkItemService(repository).get(fixture.active_work_id)
        procedure = ProcedureService(repository).get(fixture.procedure_id)
        checkpoint = ProjectCheckpointService(repository).get(fixture.checkpoint_id)
        status = ProjectStatusService(repository).build(fixture.project_id)
        WorkspaceFileService(repository).verify(fixture.artifact_id)
        inspection = ResumeBundleService(repository).export(
            fixture.project_id,
            bundle_output,
        )

    assert project.schema_version == 2
    assert project.objective == (
        "Preserve inspectable project state through transfer and recovery."
    )
    assert active.work_status == "in_progress"
    assert procedure.procedure_status == "approved"
    assert checkpoint.confirmation_state == "confirmed"
    assert status.latest_checkpoint is not None
    assert status.latest_checkpoint.checkpoint_id == fixture.checkpoint_id
    assert status.latest_checkpoint.freshness == "current"
    assert tuple(item.work_item_id for item in status.active_work) == (fixture.active_work_id,)
    assert tuple(item.work_item_id for item in status.next_ready_work) == (
        fixture.blocker_work_id,
        fixture.ready_work_id,
    )
    assert tuple(item.work_item_id for item in status.blocked_work) == (fixture.blocked_work_id,)
    assert inspection.project_id == fixture.project_id
    assert inspection.checkpoint_id == fixture.checkpoint_id
    assert inspection.checkpoint_freshness == "current"
    assert verify_resume_bundle(bundle_output) == inspection
    with zipfile.ZipFile(bundle_output, "r") as archive:
        combined = b"".join(archive.read(name) for name in archive.namelist())
    assert b"PRIVATE IMP-046 MARKER" not in combined


def package_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def write_package_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    checksums: dict[str, object] = {
        "algorithm": package.CHECKSUM_ALGORITHM,
        "entries": [
            {
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(updated.items())
        ],
    }
    updated[checksum_name] = package._json_bytes(checksums)
    package._write_deterministic_zip(path, updated)


def convert_package_to_v1(v2_package: Path, v1_package: Path) -> None:
    members = package_members(v2_package)
    for member in (
        "records/work-items.jsonl",
        "records/procedures.jsonl",
        "records/project-checkpoints.jsonl",
        "records/runtime-manifests.jsonl",
        "records/model-manifests.jsonl",
        "records/model-bindings.jsonl",
    ):
        members.pop(f"{package.PACKAGE_ROOT}/{member}")
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    manifest["package_format_version"] = 1
    included = cast(list[str], manifest["included_categories"])
    for category in (
        "work_item",
        "procedure",
        "project_checkpoint",
        "runtime_manifest",
        "model_manifest",
        "model_binding",
    ):
        included.remove(category)
        cast(dict[str, int], manifest["record_counts"]).pop(category)
        cast(dict[str, int], manifest["omitted_secret_counts"]).pop(category)
    manifest["compatibility_notes"] = [
        "Import requires package format version 1 and a supported state schema.",
        "checksums.json is the inventory and is not self-hashed.",
    ]
    members[manifest_name] = package._json_bytes(manifest)
    readme_name = f"{package.PACKAGE_ROOT}/README.txt"
    members[readme_name] = members[readme_name].replace(
        b"Format version: 2",
        b"Format version: 1",
    )
    write_package_members(v1_package, members)
