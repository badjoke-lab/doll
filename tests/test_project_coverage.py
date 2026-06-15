from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from doll import state, workspace
from doll.cli import app
from doll.project_state import (
    DecisionService,
    ProjectDecisionCorruptError,
    ProjectDecisionValidationError,
    ProjectService,
    _deterministic_json,
    _metadata_reference_ids,
    _metadata_text_items,
    _optional_string,
    _project_from_record,
    _validate_envelope,
    _validate_reference_ids,
    _validate_text_items,
)
from doll.state import RecordSensitivity

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_decision_cli_update_and_nonempty_list(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    created = runner.invoke(
        app,
        [
            "decision",
            "create",
            "初期判断",
            "--reason",
            "初期理由",
            "--status",
            "accepted",
            "--decided-at",
            "2026-06-14T00:00:00Z",
            "--workspace",
            str(root),
        ],
    )
    assert created.exit_code == 0
    decision_id = next(
        line.removeprefix("Record ID: ")
        for line in created.output.splitlines()
        if line.startswith("Record ID: ")
    )

    updated = runner.invoke(
        app,
        [
            "decision",
            "update",
            decision_id,
            "--revision",
            "1",
            "--decision",
            "更新判断",
            "--reason",
            "更新理由",
            "--status",
            "accepted",
            "--decided-at",
            "2026-06-14T00:00:00Z",
            "--alternative",
            "別案",
            "--constraint",
            "制約",
            "--workspace",
            str(root),
        ],
    )
    assert updated.exit_code == 0
    assert "Revision: 2" in updated.output

    listed = runner.invoke(
        app,
        ["decision", "list", "--workspace", str(root)],
    )
    assert listed.exit_code == 0
    assert decision_id in listed.output
    assert "status=accepted" in listed.output


@pytest.mark.parametrize(
    ("service_name", "method_name", "arguments", "expected"),
    [
        (
            "project",
            "update",
            [
                "00000000-0000-0000-0000-000000000001",
                "--revision",
                "1",
                "--name",
                "name",
                "--description",
                "description",
                "--status",
                "active",
                "--started-at",
                "2026-06-14T00:00:00Z",
            ],
            "project update failed",
        ),
        (
            "project",
            "get",
            ["00000000-0000-0000-0000-000000000001"],
            "project inspection failed",
        ),
        (
            "project",
            "list",
            [],
            "project listing failed",
        ),
        (
            "project",
            "archive",
            [
                "00000000-0000-0000-0000-000000000001",
                "--revision",
                "1",
            ],
            "project archive failed",
        ),
        (
            "project",
            "export",
            ["00000000-0000-0000-0000-000000000001"],
            "project export failed",
        ),
        (
            "decision",
            "create",
            [
                "decision",
                "--reason",
                "reason",
                "--status",
                "accepted",
                "--decided-at",
                "2026-06-14T00:00:00Z",
            ],
            "decision creation failed",
        ),
        (
            "decision",
            "update",
            [
                "00000000-0000-0000-0000-000000000001",
                "--revision",
                "1",
                "--decision",
                "decision",
                "--reason",
                "reason",
                "--status",
                "accepted",
                "--decided-at",
                "2026-06-14T00:00:00Z",
            ],
            "decision update failed",
        ),
        (
            "decision",
            "list",
            [],
            "decision listing failed",
        ),
        (
            "decision",
            "archive",
            [
                "00000000-0000-0000-0000-000000000001",
                "--revision",
                "1",
            ],
            "decision archive failed",
        ),
        (
            "decision",
            "export",
            ["00000000-0000-0000-0000-000000000001"],
            "decision export failed",
        ),
    ],
)
def test_project_decision_cli_error_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
    method_name: str,
    arguments: list[str],
    expected: str,
) -> None:
    initialized = initialized_workspace(tmp_path)
    service_type = ProjectService if service_name == "project" else DecisionService
    service_method = "export_json" if method_name == "export" else method_name

    def fail(*args: object, **kwargs: object) -> None:
        raise ProjectDecisionValidationError("blocked")

    monkeypatch.setattr(service_type, service_method, fail)
    result = runner.invoke(
        app,
        [
            service_name,
            method_name,
            *arguments,
            "--workspace",
            str(initialized.root),
        ],
    )
    assert result.exit_code == 2
    assert expected in result.output
    assert str(initialized.root) not in result.output


def test_project_decision_envelope_defense_branches(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = ProjectService(repository).create(
            name="project",
            description="description",
            project_status="active",
            started_at="2026-06-14T00:00:00Z",
        )
        record = repository.get_record(project.project_id)

        invalid_records = [
            replace(record, record_type="decision"),
            replace(record, schema_version=2),
            replace(record, revision=0),
            replace(record, status="deleted"),
            replace(
                record,
                provenance="model-proposed",
            ),
            replace(
                record,
                sensitivity=cast(RecordSensitivity, "unknown"),
            ),
            replace(
                record,
                created_at="2026-06-15T00:00:00Z",
                updated_at="2026-06-14T00:00:00Z",
            ),
        ]
        for invalid in invalid_records:
            with pytest.raises(ProjectDecisionValidationError):
                _validate_envelope(invalid, "project", "user-created")

        with pytest.raises(ProjectDecisionCorruptError):
            _project_from_record(replace(record, title="different"))


def test_project_decision_additional_typed_link_paths(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)
        wrong = repository.create_record(record_type="other", metadata={})

        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="bad decision link",
                description="description",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
                decision_ids=(wrong.id,),
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="bad artifact link",
                description="description",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
                artifact_ids=(wrong.id,),
            )
        with pytest.raises(ProjectDecisionValidationError):
            decision_service.create(
                decision="bad supersedes",
                reason="reason",
                decision_status="accepted",
                decided_at="2026-06-14T00:00:00Z",
                supersedes_id=wrong.id,
            )

        base = decision_service.create(
            decision="base",
            reason="reason",
            decision_status="accepted",
            decided_at="2026-06-14T00:00:00Z",
        )
        superseding = decision_service.create(
            decision="replacement",
            reason="new reason",
            decision_status="accepted",
            decided_at="2026-06-15T00:00:00Z",
            supersedes_id=base.decision_id,
        )
        assert superseding.supersedes_id == base.decision_id


def test_read_only_update_and_archive_are_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = ProjectService(repository).create(
            name="project",
            description="description",
            project_status="active",
            started_at="2026-06-14T00:00:00Z",
        )
        decision = DecisionService(repository).create(
            decision="decision",
            reason="reason",
            decision_status="accepted",
            decided_at="2026-06-14T00:00:00Z",
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            ProjectService(repository).update(
                project.project_id,
                expected_revision=1,
                name=project.name,
                description=project.description,
                project_status=project.project_status,
                started_at=project.started_at,
            )
        with pytest.raises(state.ReadOnlyStateError):
            DecisionService(repository).archive(
                decision.decision_id,
                expected_revision=1,
            )


def test_update_database_failure_rolls_back_record(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ProjectService(repository)
        project = service.create(
            name="project",
            description="before",
            project_status="active",
            started_at="2026-06-14T00:00:00Z",
        )
        repository.connection.execute("DROP TABLE audit_events")

        with pytest.raises(state.StateCorruptError):
            service.update(
                project.project_id,
                expected_revision=1,
                name=project.name,
                description="after",
                project_status=project.project_status,
                started_at=project.started_at,
            )

        restored = service.get(project.project_id)
        assert restored.description == "before"
        assert restored.revision == 1
        assert repository.status().state_revision == 1


def test_project_decision_remaining_validation_helpers() -> None:
    with pytest.raises(ProjectDecisionValidationError):
        _validate_text_items("items", ["x"] * 101)
    with pytest.raises(ProjectDecisionValidationError):
        _validate_reference_ids(
            "ids",
            [str(uuid4()) for _ in range(101)],
        )
    with pytest.raises(ProjectDecisionValidationError):
        _validate_reference_ids("ids", ["not-a-uuid"])
    with pytest.raises(ProjectDecisionValidationError):
        _optional_string({"x": ""}, "x")
    with pytest.raises(ProjectDecisionValidationError):
        _metadata_reference_ids({"x": [1]}, "x")
    with pytest.raises(ProjectDecisionValidationError):
        _metadata_text_items({"x": [1]}, "x")
    with pytest.raises(ValueError):
        _deterministic_json({"value": float("nan")})
