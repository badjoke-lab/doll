"""Command-line entry point for doll."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from doll import __version__
from doll.workspace import ProfilePreference, WorkspaceInitError, create_workspace

app = typer.Typer(
    name="doll",
    help="Local management interface for the doll personal AI continuity system.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def root() -> None:
    """Local management interface for doll."""


@app.command("init")
def init_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Workspace directory to initialize; defaults to the platform data directory."
        ),
    ] = None,
    instance_label: Annotated[
        str,
        typer.Option(
            "--instance-label",
            help="Human-readable label stored in the workspace identity.",
        ),
    ] = "default",
    profile: Annotated[
        ProfilePreference,
        typer.Option("--profile", help="Workspace profile preference."),
    ] = ProfilePreference.LITE,
) -> None:
    """Initialize a private doll workspace."""

    try:
        result = create_workspace(path, instance_label=instance_label, profile=profile)
    except WorkspaceInitError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"initialized workspace {result.record.workspace_id} at {result.path}")


@app.command("version")
def version_command() -> None:
    """Print the installed doll version."""

    typer.echo(__version__)


def main() -> None:  # pragma: no cover - exercised through installed entry points.
    """Run the doll command-line application."""

    app(prog_name="doll")
