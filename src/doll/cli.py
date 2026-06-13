"""Command-line entry point for doll."""

from __future__ import annotations

import typer

from doll import __version__

app = typer.Typer(
    name="doll",
    help="Local management interface for the doll personal AI continuity system.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("version")
def version_command() -> None:
    """Print the installed doll version."""

    typer.echo(__version__)


def main() -> None:  # pragma: no cover - exercised through the installed console entry point.
    """Run the doll command-line application."""

    app(prog_name="doll")
