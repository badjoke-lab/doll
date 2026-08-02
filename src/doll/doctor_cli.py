"""CLI rendering for deterministic read-only doctor diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from doll.doctor import DoctorReport, run_doctor


def doctor_command(
    workspace_path: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            help="Initialized workspace path. Uses the platform data directory by default.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit one deterministic machine-readable JSON report."),
    ] = False,
) -> None:
    """Inspect local workspace and state health without repair or mutation."""

    report = run_doctor(workspace_path)
    if json_output:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        _render_human(report)
    if not report.passed:
        raise typer.Exit(code=2)


def _render_human(report: DoctorReport) -> None:
    typer.echo(f"Doctor status: {report.overall_status.upper()}")
    for check in report.checks:
        typer.echo(f"[{check.status.upper()}] {check.check_id}: {check.summary}")
        for guidance in check.guidance:
            typer.echo(f"  - {guidance}")
    if report.state_schema_version is not None:
        typer.echo(f"State schema version: {report.state_schema_version}")
    if report.state_revision is not None:
        typer.echo(f"State revision: {report.state_revision}")
    if report.record_count is not None:
        typer.echo(f"Record count: {report.record_count}")
    if report.read_only is not None:
        typer.echo(f"Read-only: {'yes' if report.read_only else 'no'}")


__all__ = ["doctor_command"]
