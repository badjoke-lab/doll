"""Management CLI for confirmed long-term memory."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer

from doll.memory import (
    ConfirmedMemoryError,
    ConfirmedMemoryService,
    MemorySourceType,
)
from doll.state import RecordSensitivity, StateError, open_state_repository
from doll.workspace import WorkspaceError

memory_app = typer.Typer(
    help="Manage authoritative user-confirmed long-term memory.",
    no_args_is_help=True,
)


def _fail(prefix: str, exc: BaseException) -> NoReturn:
    typer.echo(f"{prefix}: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2)


def _references(values: list[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


@memory_app.command("create")
def memory_create(
    subject: Annotated[str, typer.Argument(help="Short memory subject.")],
    content: Annotated[str, typer.Option("--content", help="Confirmed memory content.")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    source_type: Annotated[str, typer.Option("--source-type")] = "user_statement",
    valid_from: Annotated[str | None, typer.Option("--valid-from")] = None,
    valid_until: Annotated[str | None, typer.Option("--valid-until")] = None,
    confidence: Annotated[float, typer.Option("--confidence", min=0.0, max=1.0)] = 1.0,
    related_id: Annotated[list[str] | None, typer.Option("--related-id")] = None,
    contradicts_id: Annotated[
        list[str] | None,
        typer.Option("--contradicts-id"),
    ] = None,
    source_reference: Annotated[
        str | None,
        typer.Option("--source-reference"),
    ] = None,
    model_manifest_id: Annotated[
        str | None,
        typer.Option("--model-manifest-id"),
    ] = None,
    runtime_adapter_id: Annotated[
        str | None,
        typer.Option("--runtime-adapter-id"),
    ] = None,
    session_id: Annotated[str | None, typer.Option("--session-id")] = None,
    origin_operation_id: Annotated[
        str | None,
        typer.Option("--origin-operation-id"),
    ] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
    sensitivity: Annotated[str, typer.Option("--sensitivity")] = "personal",
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ConfirmedMemoryService(repository).create(
                subject=subject,
                content=content,
                source_type=cast(MemorySourceType, source_type),
                valid_from=valid_from,
                valid_until=valid_until,
                confidence=confidence,
                related_memory_ids=_references(related_id),
                contradicts_memory_ids=_references(contradicts_id),
                source_reference=source_reference,
                model_manifest_id=model_manifest_id,
                runtime_adapter_id=runtime_adapter_id,
                session_id=session_id,
                origin_operation_id=origin_operation_id,
                operation_id=operation_id,
                sensitivity=cast(RecordSensitivity, sensitivity),
            )
    except (WorkspaceError, StateError, ConfirmedMemoryError) as exc:
        _fail("memory creation failed", exc)

    typer.echo("Confirmed memory created.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Subject: {info.subject}")
    typer.echo(f"Revision: {info.revision}")


@memory_app.command("update")
def memory_update(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    subject: Annotated[str, typer.Option("--subject")],
    content: Annotated[str, typer.Option("--content")],
    source_type: Annotated[str, typer.Option("--source-type")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    valid_from: Annotated[str | None, typer.Option("--valid-from")] = None,
    valid_until: Annotated[str | None, typer.Option("--valid-until")] = None,
    confidence: Annotated[float, typer.Option("--confidence", min=0.0, max=1.0)] = 1.0,
    related_id: Annotated[list[str] | None, typer.Option("--related-id")] = None,
    contradicts_id: Annotated[
        list[str] | None,
        typer.Option("--contradicts-id"),
    ] = None,
    source_reference: Annotated[
        str | None,
        typer.Option("--source-reference"),
    ] = None,
    model_manifest_id: Annotated[
        str | None,
        typer.Option("--model-manifest-id"),
    ] = None,
    runtime_adapter_id: Annotated[
        str | None,
        typer.Option("--runtime-adapter-id"),
    ] = None,
    session_id: Annotated[str | None, typer.Option("--session-id")] = None,
    origin_operation_id: Annotated[
        str | None,
        typer.Option("--origin-operation-id"),
    ] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ConfirmedMemoryService(repository).update(
                record_id,
                expected_revision=revision,
                subject=subject,
                content=content,
                source_type=cast(MemorySourceType, source_type),
                valid_from=valid_from,
                valid_until=valid_until,
                confidence=confidence,
                related_memory_ids=_references(related_id),
                contradicts_memory_ids=_references(contradicts_id),
                source_reference=source_reference,
                model_manifest_id=model_manifest_id,
                runtime_adapter_id=runtime_adapter_id,
                session_id=session_id,
                origin_operation_id=origin_operation_id,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ConfirmedMemoryError, KeyError) as exc:
        _fail("memory update failed", exc)

    typer.echo("Confirmed memory updated.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Revision: {info.revision}")


@memory_app.command("get")
def memory_get(
    record_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            info = ConfirmedMemoryService(repository).get(record_id)
    except (WorkspaceError, StateError, ConfirmedMemoryError, KeyError) as exc:
        _fail("memory inspection failed", exc)

    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Subject: {info.subject}")
    typer.echo(f"Status: {info.status}")
    typer.echo(f"Source type: {info.source_type}")
    typer.echo(f"Confidence: {info.confidence:.6g}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Content: {info.content}")


@memory_app.command("list")
def memory_list(
    workspace: Annotated[Path | None, typer.Argument()] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived"),
    ] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            items = ConfirmedMemoryService(repository).list(
                include_archived=include_archived,
                limit=limit,
            )
    except (WorkspaceError, StateError, ConfirmedMemoryError) as exc:
        _fail("memory listing failed", exc)

    if not items:
        typer.echo("No confirmed memories.")
        return
    for item in items:
        typer.echo(
            f"{item.record_id} subject={item.subject} status={item.status} revision={item.revision}"
        )


@memory_app.command("archive")
def memory_archive(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = ConfirmedMemoryService(repository).archive(
                record_id,
                expected_revision=revision,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, ConfirmedMemoryError, KeyError) as exc:
        _fail("memory archive failed", exc)

    typer.echo(f"Confirmed memory archived: {info.record_id} revision={info.revision}")


@memory_app.command("export")
def memory_export(
    record_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            payload = ConfirmedMemoryService(repository).export_json(record_id)
    except (WorkspaceError, StateError, ConfirmedMemoryError, KeyError) as exc:
        _fail("memory export failed", exc)

    typer.echo(payload, nl=False)
