"""Management CLI for durable projects and explicit decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer

from doll.project_state import (
    DecisionService,
    DecisionStatus,
    ProjectDecisionError,
    ProjectService,
    ProjectStatus,
)
from doll.state import RecordSensitivity, StateError, open_state_repository
from doll.workspace import WorkspaceError

project_app = typer.Typer(
    help="Manage durable user-controlled project records.",
    no_args_is_help=True,
)
decision_app = typer.Typer(
    help="Manage explicit user-confirmed decision records.",
    no_args_is_help=True,
)


def _fail(prefix: str, exc: BaseException) -> NoReturn:
    typer.echo(f"{prefix}: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2)


def _items(values: list[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


@project_app.command("create")
def project_create(
    name: Annotated[str, typer.Argument()],
    description: Annotated[str, typer.Option("--description")],
    project_status: Annotated[str, typer.Option("--status")],
    started_at: Annotated[str, typer.Option("--started-at")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    ended_at: Annotated[str | None, typer.Option("--ended-at")] = None,
    decision_id: Annotated[list[str] | None, typer.Option("--decision-id")] = None,
    memory_id: Annotated[list[str] | None, typer.Option("--memory-id")] = None,
    artifact_id: Annotated[list[str] | None, typer.Option("--artifact-id")] = None,
    sensitivity: Annotated[str, typer.Option("--sensitivity")] = "personal",
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ProjectService(repository).create(
                name=name,
                description=description,
                project_status=cast(ProjectStatus, project_status),
                started_at=started_at,
                ended_at=ended_at,
                decision_ids=_items(decision_id),
                memory_ids=_items(memory_id),
                artifact_ids=_items(artifact_id),
                sensitivity=cast(RecordSensitivity, sensitivity),
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("project creation failed", exc)

    typer.echo("Project created.")
    typer.echo(f"Record ID: {info.project_id}")
    typer.echo(f"Name: {info.name}")
    typer.echo(f"Revision: {info.revision}")


@project_app.command("update")
def project_update(
    project_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
    project_status: Annotated[str, typer.Option("--status")],
    started_at: Annotated[str, typer.Option("--started-at")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    ended_at: Annotated[str | None, typer.Option("--ended-at")] = None,
    decision_id: Annotated[list[str] | None, typer.Option("--decision-id")] = None,
    memory_id: Annotated[list[str] | None, typer.Option("--memory-id")] = None,
    artifact_id: Annotated[list[str] | None, typer.Option("--artifact-id")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ProjectService(repository).update(
                project_id,
                expected_revision=revision,
                name=name,
                description=description,
                project_status=cast(ProjectStatus, project_status),
                started_at=started_at,
                ended_at=ended_at,
                decision_ids=_items(decision_id),
                memory_ids=_items(memory_id),
                artifact_ids=_items(artifact_id),
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("project update failed", exc)

    typer.echo("Project updated.")
    typer.echo(f"Record ID: {info.project_id}")
    typer.echo(f"Revision: {info.revision}")


@project_app.command("get")
def project_get(
    project_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            info = ProjectService(repository).get(project_id)
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("project inspection failed", exc)

    typer.echo(f"Record ID: {info.project_id}")
    typer.echo(f"Name: {info.name}")
    typer.echo(f"Status: {info.project_status}")
    typer.echo(f"Lifecycle: {info.lifecycle_status}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Description: {info.description}")


@project_app.command("list")
def project_list(
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived"),
    ] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            items = ProjectService(repository).list(
                include_archived=include_archived,
                limit=limit,
            )
    except (WorkspaceError, StateError, ProjectDecisionError) as exc:
        _fail("project listing failed", exc)

    if not items:
        typer.echo("No projects.")
        return
    for item in items:
        typer.echo(
            f"{item.project_id} name={item.name} "
            f"status={item.project_status} lifecycle={item.lifecycle_status} "
            f"revision={item.revision}"
        )


@project_app.command("archive")
def project_archive(
    project_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ProjectService(repository).archive(
                project_id,
                expected_revision=revision,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("project archive failed", exc)

    typer.echo(f"Project archived: {info.project_id} revision={info.revision}")


@project_app.command("export")
def project_export(
    project_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            payload = ProjectService(repository).export_json(project_id)
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("project export failed", exc)

    typer.echo(payload, nl=False)


@decision_app.command("create")
def decision_create(
    decision: Annotated[str, typer.Argument()],
    reason: Annotated[str, typer.Option("--reason")],
    decision_status: Annotated[str, typer.Option("--status")],
    decided_at: Annotated[str, typer.Option("--decided-at")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    alternative: Annotated[list[str] | None, typer.Option("--alternative")] = None,
    constraint: Annotated[list[str] | None, typer.Option("--constraint")] = None,
    review_after: Annotated[str | None, typer.Option("--review-after")] = None,
    supersedes_id: Annotated[str | None, typer.Option("--supersedes-id")] = None,
    project_id: Annotated[str | None, typer.Option("--project-id")] = None,
    memory_id: Annotated[list[str] | None, typer.Option("--memory-id")] = None,
    artifact_id: Annotated[list[str] | None, typer.Option("--artifact-id")] = None,
    sensitivity: Annotated[str, typer.Option("--sensitivity")] = "personal",
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = DecisionService(repository).create(
                decision=decision,
                reason=reason,
                decision_status=cast(DecisionStatus, decision_status),
                decided_at=decided_at,
                alternatives=_items(alternative),
                constraints=_items(constraint),
                review_after=review_after,
                supersedes_id=supersedes_id,
                project_id=project_id,
                memory_ids=_items(memory_id),
                artifact_ids=_items(artifact_id),
                sensitivity=cast(RecordSensitivity, sensitivity),
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("decision creation failed", exc)

    typer.echo("Decision created.")
    typer.echo(f"Record ID: {info.decision_id}")
    typer.echo(f"Status: {info.decision_status}")
    typer.echo(f"Revision: {info.revision}")


@decision_app.command("update")
def decision_update(
    decision_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    decision: Annotated[str, typer.Option("--decision")],
    reason: Annotated[str, typer.Option("--reason")],
    decision_status: Annotated[str, typer.Option("--status")],
    decided_at: Annotated[str, typer.Option("--decided-at")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    alternative: Annotated[list[str] | None, typer.Option("--alternative")] = None,
    constraint: Annotated[list[str] | None, typer.Option("--constraint")] = None,
    review_after: Annotated[str | None, typer.Option("--review-after")] = None,
    supersedes_id: Annotated[str | None, typer.Option("--supersedes-id")] = None,
    project_id: Annotated[str | None, typer.Option("--project-id")] = None,
    memory_id: Annotated[list[str] | None, typer.Option("--memory-id")] = None,
    artifact_id: Annotated[list[str] | None, typer.Option("--artifact-id")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = DecisionService(repository).update(
                decision_id,
                expected_revision=revision,
                decision=decision,
                reason=reason,
                decision_status=cast(DecisionStatus, decision_status),
                decided_at=decided_at,
                alternatives=_items(alternative),
                constraints=_items(constraint),
                review_after=review_after,
                supersedes_id=supersedes_id,
                project_id=project_id,
                memory_ids=_items(memory_id),
                artifact_ids=_items(artifact_id),
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("decision update failed", exc)

    typer.echo("Decision updated.")
    typer.echo(f"Record ID: {info.decision_id}")
    typer.echo(f"Revision: {info.revision}")


@decision_app.command("get")
def decision_get(
    decision_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            info = DecisionService(repository).get(decision_id)
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("decision inspection failed", exc)

    typer.echo(f"Record ID: {info.decision_id}")
    typer.echo(f"Decision: {info.decision}")
    typer.echo(f"Status: {info.decision_status}")
    typer.echo(f"Lifecycle: {info.lifecycle_status}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Reason: {info.reason}")


@decision_app.command("list")
def decision_list(
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived"),
    ] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            items = DecisionService(repository).list(
                include_archived=include_archived,
                limit=limit,
            )
    except (WorkspaceError, StateError, ProjectDecisionError) as exc:
        _fail("decision listing failed", exc)

    if not items:
        typer.echo("No decisions.")
        return
    for item in items:
        typer.echo(
            f"{item.decision_id} status={item.decision_status} "
            f"lifecycle={item.lifecycle_status} revision={item.revision}"
        )


@decision_app.command("archive")
def decision_archive(
    decision_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = DecisionService(repository).archive(
                decision_id,
                expected_revision=revision,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("decision archive failed", exc)

    typer.echo(f"Decision archived: {info.decision_id} revision={info.revision}")


@decision_app.command("export")
def decision_export(
    decision_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            payload = DecisionService(repository).export_json(decision_id)
    except (WorkspaceError, StateError, ProjectDecisionError, KeyError) as exc:
        _fail("decision export failed", exc)

    typer.echo(payload, nl=False)
