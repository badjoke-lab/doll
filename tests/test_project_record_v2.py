from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.project_state import (
    ProjectDecisionValidationError,
    ProjectService,
)
from doll.settings import PolicyService


def _initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    updated[checksum_name] = package._json_bytes(
        {
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
    )
    package._write_deterministic_zip(path, updated)


def test_project_v1_remains_readable_with_neutral_v2_fields(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = ProjectService(repository).create(
            name="Legacy project",
            description="Created through the ProjectRecord v1 compatibility path.",
            project_status="active",
            started_at="2026-06-26T00:00:00Z",
        )
        exported = ProjectService(repository).export_json(project.project_id)

    assert project.schema_version == 1
    assert project.objective is None
    assert project.in_scope == ()
    assert project.out_of_scope == ()
    assert project.success_criteria == ()
    assert project.governing_policy_ids == ()
    payload = json.loads(exported)
    assert payload["export_schema"] == "doll.project.v1"
    assert payload["record"]["schema_version"] == 1
    assert "objective" not in payload["record"]["project"]


def test_project_v2_persists_exports_and_transfers(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        policy = PolicyService(repository).create(
            key="project.local_first",
            rule="Project continuity state remains locally controlled.",
        )
        project = ProjectService(repository).create_v2(
            name="doll Phase 4B",
            description="Build model-independent project continuity.",
            objective="Preserve enough authoritative project state to resume work elsewhere.",
            in_scope=("Project charter continuity", "Versioned state transfer"),
            out_of_scope=("Local model integration",),
            success_criteria=(
                "A fresh process can inspect the accepted project charter.",
                "Package transfer preserves the charter without fabrication.",
            ),
            project_status="active",
            started_at="2026-06-26T01:00:00Z",
            governing_policy_ids=(policy.record_id,),
            operation_id="imp-040-create-v2",
        )
        export_payload = json.loads(ProjectService(repository).export_json(project.project_id))

    assert project.schema_version == 2
    assert project.objective == (
        "Preserve enough authoritative project state to resume work elsewhere."
    )
    assert project.governing_policy_ids == (policy.record_id,)
    assert export_payload["export_schema"] == "doll.project.v2"
    assert export_payload["record"]["schema_version"] == 2
    assert export_payload["record"]["project"]["in_scope"] == [
        "Project charter continuity",
        "Versioned state transfer",
    ]

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        restored = ProjectService(repository).get(project.project_id)
        output = tmp_path / "project-v2.zip"
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-26T02:00:00Z",
        )
    assert restored == project

    target = tmp_path / "imported"
    package.import_state_package(output, target)
    with state.open_state_repository(target, read_only=True) as repository:
        imported = ProjectService(repository).get(project.project_id)
    assert imported.schema_version == 2
    assert imported.objective == project.objective
    assert imported.in_scope == project.in_scope
    assert imported.out_of_scope == project.out_of_scope
    assert imported.success_criteria == project.success_criteria
    assert imported.governing_policy_ids == project.governing_policy_ids


def test_project_v1_can_be_explicitly_upgraded_without_inference(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ProjectService(repository)
        legacy = service.create(
            name="Legacy",
            description="Legacy description remains description only.",
            project_status="planned",
            started_at="2026-06-26T00:00:00Z",
        )
        assert legacy.objective is None

        upgraded = service.update_v2(
            legacy.project_id,
            expected_revision=1,
            name=legacy.name,
            description=legacy.description,
            objective="Explicitly accepted objective.",
            in_scope=("Accepted work",),
            out_of_scope=("Excluded work",),
            success_criteria=("Observable result exists",),
            project_status="active",
            started_at=legacy.started_at,
            governing_policy_ids=(),
            operation_id="imp-040-upgrade",
        )
        record = repository.get_record(legacy.project_id)

    assert upgraded.schema_version == 2
    assert upgraded.revision == 2
    assert upgraded.objective == "Explicitly accepted objective."
    assert upgraded.objective != legacy.description
    assert record.schema_version == 2


def test_project_v2_rejects_invalid_governing_policy_links(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ProjectService(repository)
        wrong_type = repository.create_record(record_type="other", metadata={})
        policy_service = PolicyService(repository)
        archived = policy_service.create(
            key="project.archived",
            rule="Archived policy must not govern new project state.",
        )
        policy_service.archive(archived.record_id, expected_revision=1)

        for invalid_id in (str(uuid4()), wrong_type.id, archived.record_id):
            with pytest.raises(ProjectDecisionValidationError):
                service.create_v2(
                    name="Invalid policy project",
                    description="Synthetic invalid policy link.",
                    objective="Prove invalid policy links fail closed.",
                    in_scope=("Validation",),
                    out_of_scope=(),
                    success_criteria=("Creation is rejected",),
                    project_status="planned",
                    started_at="2026-06-26T00:00:00Z",
                    governing_policy_ids=(invalid_id,),
                )


def test_package_rejects_missing_project_v2_policy_link_before_mutation(
    tmp_path: Path,
) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        policy = PolicyService(repository).create(
            key="project.package_policy",
            rule="Synthetic package policy.",
        )
        ProjectService(repository).create_v2(
            name="Package project",
            description="Synthetic package link validation.",
            objective="Reject missing governing policy links.",
            in_scope=("Package validation",),
            out_of_scope=(),
            success_criteria=("Tampered package is rejected",),
            project_status="active",
            started_at="2026-06-26T00:00:00Z",
            governing_policy_ids=(policy.record_id,),
        )
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            source,
            exported_at="2026-06-26T03:00:00Z",
        )

    members = _read_members(source)
    projects_name = f"{package.PACKAGE_ROOT}/records/projects.jsonl"
    project_payload = cast(
        dict[str, object],
        json.loads(members[projects_name].decode("utf-8").strip()),
    )
    metadata = cast(dict[str, object], project_payload["metadata"])
    metadata["governing_policy_ids"] = [str(uuid4())]
    members[projects_name] = package._json_bytes(project_payload)
    hostile = tmp_path / "hostile.zip"
    _write_members(hostile, members)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(hostile, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"
