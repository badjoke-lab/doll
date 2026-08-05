"""CLI surface for explicit local full-text state search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from doll.local_search import LocalSearchError, LocalSearchReport, search_workspace
from doll.state import StateError
from doll.workspace import WorkspaceError


def search_command(
    query: Annotated[
        str,
        typer.Argument(help="Explicit local full-text query."),
    ],
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            help="Initialized workspace path. Uses the platform data directory by default.",
        ),
    ] = None,
    record_type: Annotated[
        str | None,
        typer.Option(
            "--record-type",
            help="Optional exact authoritative record-type filter.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum matching records."),
    ] = 20,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
) -> None:
    """Search active non-secret local records without models or network access."""

    try:
        report = search_workspace(
            workspace,
            query,
            record_type=record_type,
            limit=limit,
        )
    except (WorkspaceError, StateError, LocalSearchError, OSError) as exc:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "error": "local_search_failed",
                        "error_class": type(exc).__name__,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            typer.echo(f"local search failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    if json_output:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
        return
    _render_human(report)


def _render_human(report: LocalSearchReport) -> None:
    if not report.hits:
        typer.echo("No local records matched.")
        if report.scan_truncated:
            typer.echo("Search scan reached its bounded record limit.")
        return

    typer.echo(f"Local search results: {report.result_count}")
    for hit in report.hits:
        title = hit.title or "(untitled)"
        typer.echo(f"[{hit.record_type}] {title} id={hit.record_id} sensitivity={hit.sensitivity}")
        for match in hit.matches:
            typer.echo(f"  {match.field_path}: {match.snippet}")
    if report.scan_truncated:
        typer.echo("Search scan reached its bounded record limit.")


__all__ = ["search_command"]
