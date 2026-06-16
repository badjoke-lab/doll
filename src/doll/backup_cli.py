"""Command-line management for verified local Doll backups."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from doll.backup import (
    BackupCreationResult,
    BackupError,
    create_state_backup,
    create_workspace_backup,
    inspect_backup,
    verify_backup,
)
from doll.backup_manifest import BackupManifestError, BackupManifestService
from doll.state import StateError, open_state_repository
from doll.workspace import WorkspaceError

backup_app = typer.Typer(
    help="Create, inspect, verify, and list verified local backups.",
    no_args_is_help=True,
)


def _fail(prefix: str, exc: BaseException) -> NoReturn:
    typer.echo(f"{prefix}: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2)


def _show_created(kind: str, result: BackupCreationResult) -> None:
    inspection = result.inspection
    inventory = result.inventory
    typer.echo(f"{kind} backup created, verified, and registered.")
    typer.echo(f"Backup ID: {inventory.backup_id}")
    typer.echo(f"File name: {inventory.file_name}")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"Source revision: {inspection.source_state_revision}")
    typer.echo(f"Format version: {inspection.backup_format_version}")
    typer.echo(f"Members: {inspection.member_count}")
    typer.echo(f"Size bytes: {inspection.file_size_bytes}")
    typer.echo(f"SHA-256: {inspection.file_sha256}")


@backup_app.command("create-state")
def create_state_command(
    output: Annotated[Path, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    """Create a verified state backup and register it in the source workspace."""

    try:
        result = create_state_backup(
            workspace,
            output,
            operation_id=operation_id,
        )
    except (WorkspaceError, StateError, BackupError, BackupManifestError) as exc:
        _fail("state backup creation failed", exc)
    _show_created("State", result)


@backup_app.command("create-workspace")
def create_workspace_command(
    output: Annotated[Path, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    """Create a verified durable-workspace backup without unencrypted secrets."""

    try:
        result = create_workspace_backup(
            workspace,
            output,
            operation_id=operation_id,
        )
    except (WorkspaceError, StateError, BackupError, BackupManifestError) as exc:
        _fail("workspace backup creation failed", exc)
    _show_created("Workspace", result)


@backup_app.command("inspect")
def inspect_command(backup: Annotated[Path, typer.Argument()]) -> None:
    """Inspect a backup after complete verification."""

    try:
        inspection = inspect_backup(backup)
    except BackupError as exc:
        _fail("backup inspection failed", exc)
    typer.echo("Backup: verified")
    typer.echo(f"Kind: {inspection.backup_kind}")
    typer.echo(f"Format version: {inspection.backup_format_version}")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"Source revision: {inspection.source_state_revision}")
    typer.echo(f"Members: {inspection.member_count}")
    typer.echo(f"Payload files: {inspection.payload_file_count}")
    typer.echo(f"Size bytes: {inspection.file_size_bytes}")
    typer.echo(f"SHA-256: {inspection.file_sha256}")


@backup_app.command("verify")
def verify_command(backup: Annotated[Path, typer.Argument()]) -> None:
    """Verify a backup archive and all nested authoritative payloads."""

    try:
        inspection = verify_backup(backup)
    except BackupError as exc:
        _fail("backup verification failed", exc)
    typer.echo("Backup verification: passed")
    typer.echo(f"Kind: {inspection.backup_kind}")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"Members: {inspection.member_count}")
    typer.echo(f"SHA-256: {inspection.file_sha256}")


@backup_app.command("list")
def list_command(
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=200, help="Maximum backups to display."),
    ] = 50,
) -> None:
    """List authoritative backup inventory records without accessing backup files."""

    try:
        with open_state_repository(workspace, read_only=True) as repository:
            backups = BackupManifestService(repository).list(limit=limit)
    except (WorkspaceError, StateError, BackupManifestError) as exc:
        _fail("backup listing failed", exc)
    if not backups:
        typer.echo("No registered backups.")
        return
    for backup in backups:
        typer.echo(
            f"{backup.backup_id} kind={backup.backup_kind} file={backup.file_name} "
            f"revision={backup.source_state_revision} size={backup.file_size_bytes} "
            f"status={backup.verification_status}"
        )
