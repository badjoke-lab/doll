"""Management CLI for portable Doll State packages."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from doll.state import StateError, open_state_repository
from doll.state_package import (
    StatePackageError,
    export_state_package,
    import_state_package,
    inspect_state_package,
    verify_state_package,
)
from doll.workspace import WorkspaceError

state_package_app = typer.Typer(
    help="Export, inspect, verify, and import portable Doll State packages.",
    no_args_is_help=True,
)


def _fail(prefix: str, exc: BaseException) -> NoReturn:
    typer.echo(f"{prefix}: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2)


@state_package_app.command("export")
def export_command(
    output: Annotated[Path, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            inspection = export_state_package(repository, output)
    except (WorkspaceError, StateError, StatePackageError) as exc:
        _fail("state package export failed", exc)
    typer.echo("State package exported and verified.")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"State revision: {inspection.state_revision}")
    typer.echo(f"Record count: {sum(inspection.record_counts.values())}")
    typer.echo(f"File count: {inspection.authoritative_file_count}")


@state_package_app.command("inspect")
def inspect_command(package: Annotated[Path, typer.Argument()]) -> None:
    try:
        inspection = inspect_state_package(package)
    except StatePackageError as exc:
        _fail("state package inspection failed", exc)
    typer.echo("State package: verified")
    typer.echo(f"Format version: {inspection.package_format_version}")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"Schema version: {inspection.schema_version}")
    typer.echo(f"State revision: {inspection.state_revision}")
    typer.echo(f"Record count: {sum(inspection.record_counts.values())}")
    typer.echo(f"File count: {inspection.authoritative_file_count}")


@state_package_app.command("verify")
def verify_command(package: Annotated[Path, typer.Argument()]) -> None:
    try:
        inspection = verify_state_package(package)
    except StatePackageError as exc:
        _fail("state package verification failed", exc)
    typer.echo("State package verification: passed")
    typer.echo(f"Workspace ID: {inspection.workspace_id}")
    typer.echo(f"Members: {inspection.member_count}")


@state_package_app.command("import")
def import_command(
    package: Annotated[Path, typer.Argument()],
    target: Annotated[Path, typer.Option("--target")],
) -> None:
    try:
        result = import_state_package(package, target)
    except StatePackageError as exc:
        _fail("state package import failed", exc)
    typer.echo("State package imported and verified.")
    typer.echo(f"Workspace ID: {result.workspace_id}")
    typer.echo(f"Source revision: {result.source_state_revision}")
    typer.echo(f"Imported revision: {result.imported_state_revision}")
    typer.echo(f"Record count: {result.imported_record_count}")
    typer.echo(f"File count: {result.imported_file_count}")
