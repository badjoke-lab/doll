from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import doll.backup as backup
import doll.restore as restore
from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.project_experience import (
    ProjectExperienceActor,
    ProjectExperienceAssertionState,
    ProjectExperienceEventKind,
    ProjectExperienceOutcome,
    ProjectExperienceService,
    ProjectExperienceValidationError,
)
from doll.project_state import ProjectInfo, ProjectService
from doll.resume_bundle import BUNDLE_ROOT, ResumeBundleService, verify_resume_bundle
from doll.state_package import (
    StatePackageValidationError,
    _validate_cross_record_links,
    export_state_package,
    import_state_package,
    verify_state_package,
)
from doll.state_repository import StateRepository
from doll.work_item import WorkItemInfo, WorkItemService


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository) -> ProjectInfo:
    return ProjectService(repository).create_v2(
        name="Project experience continuity",
        description="Synthetic ProjectExperienceRecord fixture.",
        objective="Preserve semantic work history without mutating current project state.",
        in_scope=("project experience",),
        out_of_scope=("automatic authority",),
        success_criteria=("experience survives continuity operations",),
        project_status="active",
        started_at="2026-08-15T00:00:00Z",
    )


def _project_and_work(repository: StateRepository) -> tuple[ProjectInfo, WorkItemInfo]:
    project = _project(repository)
    work = WorkItemService(repository).create(
        project_id=project.project_id,
        kind="investigation",
        title="Investigate continuity behavior",
        description="Synthetic work item for ProjectExperienceRecord links.",
        priority=10,
    )
    return project, work


def test_imp_094_records_supported_semantic_history_without_current_state_authority(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project, work = _project_and_work(repository)
        project_before = ProjectService(repository).get(project.project_id)
        work_before = WorkItemService(repository).get(work.work_item_id)
        service = ProjectExperienceService(repository)
        specifications: tuple[
            tuple[
                ProjectExperienceEventKind,
                ProjectExperienceOutcome | None,
                ProjectExperienceAssertionState,
                ProjectExperienceActor,
            ],
            ...,
        ] = (
            ("observation", None, "user_recorded", "user"),
            ("hypothesis", None, "model_proposed", "model"),
            ("attempt", None, "imported_external", "importer"),
            ("outcome", "failed", "deterministic_system", "system"),
            ("resolution", "worked", "user_confirmed", "user"),
            ("lesson", None, "user_recorded", "user"),
        )
        created = tuple(
            service.record(
                project_id=project.project_id,
                work_item_id=work.work_item_id,
                event_kind=event_kind,
                summary=f"Synthetic {event_kind} experience.",
                outcome=outcome,
                occurred_at=f"2026-08-15T00:0{index}:00Z",
                assertion_state=assertion_state,
                actor_type=actor_type,
            )
            for index, (event_kind, outcome, assertion_state, actor_type) in enumerate(
                specifications
            )
        )

        assert {item.event_kind for item in created} == {
            "observation",
            "hypothesis",
            "attempt",
            "outcome",
            "resolution",
            "lesson",
        }
        assert {item.assertion_state for item in created} == {
            "user_recorded",
            "user_confirmed",
            "deterministic_system",
            "imported_external",
            "model_proposed",
        }
        assert created[3].outcome == "failed"
        assert created[4].outcome == "worked"
        assert (
            ProjectService(repository).get(project.project_id).revision == project_before.revision
        )
        assert ProjectService(repository).get(project.project_id).project_status == (
            project_before.project_status
        )
        assert WorkItemService(repository).get(work.work_item_id).revision == work_before.revision
        assert (
            WorkItemService(repository).get(work.work_item_id).work_status
            == work_before.work_status
        )

        with pytest.raises(ProjectExperienceValidationError, match="producing actor"):
            service.record(
                project_id=project.project_id,
                event_kind="observation",
                summary="Actor mismatch must fail.",
                occurred_at="2026-08-15T01:00:00Z",
                assertion_state="model_proposed",
                actor_type="user",
            )


def test_imp_094_corrections_append_and_preserve_published_history(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        service = ProjectExperienceService(repository)
        failed = service.record(
            project_id=project.project_id,
            event_kind="outcome",
            summary="The first approach failed under the synthetic fixture.",
            outcome="failed",
            occurred_at="2026-08-15T02:00:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )
        corrected = service.correct(
            failed.experience_id,
            summary="Correction adds context without rewriting the first event.",
            occurred_at="2026-08-15T02:05:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )

        original = service.get(failed.experience_id)
        assert original.summary == "The first approach failed under the synthetic fixture."
        assert original.outcome == "failed"
        assert original.revision == 1
        assert corrected.experience_id != original.experience_id
        assert corrected.supersedes_id == original.experience_id
        assert corrected.outcome == "failed"
        assert corrected.revision == 1
        assert len(service.list(project_id=project.project_id)) == 2


def test_imp_094_sensitivity_and_private_host_boundaries_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        service = ProjectExperienceService(repository)
        secret_memory = ConfirmedMemoryService(repository).create(
            subject="Synthetic secret source",
            content="This record exists only to exercise the secret link boundary.",
            sensitivity="secret",
        )
        with pytest.raises(ProjectExperienceValidationError, match="secret source"):
            service.record(
                project_id=project.project_id,
                event_kind="observation",
                summary="Non-secret experience cannot link to a secret source.",
                occurred_at="2026-08-15T03:00:00Z",
                assertion_state="user_recorded",
                actor_type="user",
                source_ids=(secret_memory.record_id,),
            )
        with pytest.raises(ProjectExperienceValidationError, match="absolute paths"):
            service.record(
                project_id=project.project_id,
                event_kind="observation",
                summary="Observed private file /Users/example/private.txt during work.",
                occurred_at="2026-08-15T03:01:00Z",
                assertion_state="user_recorded",
                actor_type="user",
            )
        with pytest.raises(ProjectExperienceValidationError, match="SecretReference"):
            service.record(
                project_id=project.project_id,
                event_kind="lesson",
                summary="Synthetic secret experience content.",
                occurred_at="2026-08-15T03:02:00Z",
                assertion_state="user_recorded",
                actor_type="user",
                sensitivity="secret",
            )


def test_imp_094_state_package_round_trip_and_cross_link_validation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project, work = _project_and_work(repository)
        service = ProjectExperienceService(repository)
        failed = service.record(
            project_id=project.project_id,
            work_item_id=work.work_item_id,
            event_kind="outcome",
            summary="Synthetic package-linked failure.",
            outcome="failed",
            occurred_at="2026-08-15T04:00:00Z",
            assertion_state="deterministic_system",
            actor_type="system",
        )
        resolved = service.record(
            project_id=project.project_id,
            work_item_id=work.work_item_id,
            event_kind="resolution",
            summary="Synthetic package-linked resolution.",
            outcome="worked",
            occurred_at="2026-08-15T04:05:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
            related_record_ids=(failed.experience_id,),
        )
        records = {
            row[0]: repository.get_record(row[0])
            for row in repository.connection.execute("SELECT id FROM records").fetchall()
        }
        without_project = dict(records)
        without_project.pop(project.project_id)
        with pytest.raises(StatePackageValidationError):
            _validate_cross_record_links(without_project)

    package = tmp_path / "project-experience.doll.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        inspection = export_state_package(
            repository,
            package,
            exported_at="2026-08-15T04:10:00Z",
        )
    assert inspection.record_counts["project_experience"] == 2
    assert verify_state_package(package) == inspection

    target = tmp_path / "package-imported"
    import_state_package(package, target)
    with state.open_state_repository(target, read_only=True) as repository:
        restored_failed = ProjectExperienceService(repository).get(failed.experience_id)
        restored_resolved = ProjectExperienceService(repository).get(resolved.experience_id)
        assert restored_failed.outcome == "failed"
        assert restored_resolved.outcome == "worked"
        assert restored_resolved.related_record_ids == (failed.experience_id,)
        assert restored_resolved.project_id == project.project_id
        assert restored_resolved.work_item_id == work.work_item_id


def test_imp_094_state_backup_restore_and_fresh_process_inspection(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        experience = ProjectExperienceService(repository).record(
            project_id=project.project_id,
            event_kind="lesson",
            summary="This lesson must survive backup and restore.",
            occurred_at="2026-08-15T05:00:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )

    backup_path = tmp_path / "project-experience-backup.zip"
    backup.create_state_backup(initialized.root, backup_path, operation_id="imp-094-backup")
    target = tmp_path / "restored"
    result = restore.restore_state_backup(backup_path, target)
    assert result.fresh_process_validated is True
    with state.open_state_repository(target, read_only=True) as repository:
        restored = ProjectExperienceService(repository).get(experience.experience_id)
        assert restored.summary == "This lesson must survive backup and restore."
        assert restored.project_id == project.project_id

    script = """
import json
import sys
from pathlib import Path
from doll import state
from doll.project_experience import ProjectExperienceService
with state.open_state_repository(Path(sys.argv[1]), read_only=True) as repository:
    item = ProjectExperienceService(repository).get(sys.argv[2])
    print(json.dumps({"id": item.experience_id, "summary": item.summary}, sort_keys=True))
"""
    environment = dict(os.environ)
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(target), experience.experience_id],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload == {
        "id": experience.experience_id,
        "summary": "This lesson must survive backup and restore.",
    }


def test_imp_094_resume_bundle_v1_explicitly_omits_non_secret_experience_content(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        service = ProjectExperienceService(repository)
        service.record(
            project_id=project.project_id,
            event_kind="lesson",
            summary="Visible experience intentionally omitted from Resume Bundle v1.",
            occurred_at="2026-08-15T06:00:00Z",
            assertion_state="user_recorded",
            actor_type="user",
        )
        service.record(
            project_id=project.project_id,
            event_kind="lesson",
            summary="Sensitive experience is also omitted from Resume Bundle v1.",
            occurred_at="2026-08-15T06:01:00Z",
            assertion_state="user_recorded",
            actor_type="user",
            sensitivity="sensitive",
        )

    output = tmp_path / "resume.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        inspection = ResumeBundleService(repository).export(project.project_id, output)
    assert inspection.omitted_record_counts["project_experiences"] == 2
    assert verify_resume_bundle(output) == inspection
    with zipfile.ZipFile(output, "r") as archive:
        manifest = json.loads(archive.read(f"{BUNDLE_ROOT}/manifest.json"))
        bundle_bytes = b"".join(archive.read(name) for name in archive.namelist())
    assert manifest["selection_options"]["project_experience"] == "omitted_in_bundle_v1"
    assert manifest["omitted_record_counts"]["project_experiences"] == 2
    assert b"Visible experience intentionally omitted" not in bundle_bytes
    assert b"Sensitive experience is also omitted" not in bundle_bytes
