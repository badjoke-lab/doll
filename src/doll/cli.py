"""Command-line entry point for doll."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from doll import __version__
from doll.state import StateError, initialize_state_repository, open_state_repository
from doll.workspace import ProfilePreference, WorkspaceError, initialize_workspace

app = typer.Typer(
    name="doll",
    help="Local management interface for the doll personal AI continuity system.",
    no_args_is_help=True,
    add_completion=False,
)
state_app = typer.Typer(
    help="Initialize and inspect the local authoritative state repository.",
    no_args_is_help=True,
)
app.add_typer(state_app, name="state")


@app.callback()
def root() -> None:
    """Local management interface for doll."""


@app.command("init")
def init_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Optional workspace path. Uses the platform data directory by default."
        ),
    ] = None,
    instance_label: Annotated[
        str,
        typer.Option("--instance-label", help="Human-readable label for this local instance."),
    ] = "primary",
    profile: Annotated[
        str,
        typer.Option("--profile", help="Initial execution profile: lite, heavy, or auto."),
    ] = "lite",
) -> None:
    """Initialize a new private doll workspace."""

    if profile not in {"lite", "heavy", "auto"}:
        typer.echo("profile must be one of: lite, heavy, auto", err=True)
        raise typer.Exit(code=2)

    try:
        initialized = initialize_workspace(
            path,
            instance_label=instance_label,
            profile_preference=cast(ProfilePreference, profile),
        )
    except WorkspaceError as exc:
        typer.echo(f"workspace initialization failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Workspace initialized: {initialized.root}")
    typer.echo(f"Workspace ID: {initialized.record.workspace_id}")


@state_app.command("init")
def state_init_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Initialized workspace path. Uses the platform data directory by default."
        ),
    ] = None,
) -> None:
    """Initialize the SQLite authoritative state repository."""

    try:
        with initialize_state_repository(path) as repository:
            status = repository.status()
    except (WorkspaceError, StateError) as exc:
        typer.echo(f"state initialization failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"State database initialized: {status.database_path}")
    typer.echo(f"Schema version: {status.schema_version}")
    typer.echo(f"State revision: {status.state_revision}")


@state_app.command("status")
def state_status_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Initialized workspace path. Uses the platform data directory by default."
        ),
    ] = None,
) -> None:
    """Inspect state metadata through a read-only connection."""

    try:
        with open_state_repository(path, read_only=True) as repository:
            status = repository.status()
    except (WorkspaceError, StateError) as exc:
        typer.echo(f"state inspection failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("State database: ready")
    typer.echo(f"Schema version: {status.schema_version}")
    typer.echo(f"State revision: {status.state_revision}")
    typer.echo(f"Record count: {status.record_count}")
    typer.echo("Mode: read-only")


@app.command("version")
def version_command() -> None:
    """Print the installed doll version."""

    typer.echo(__version__)


def main() -> None:  # pragma: no cover - exercised through installed entry points.
    """Run the doll command-line application."""

    app(prog_name="doll")
