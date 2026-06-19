"""Command-line entry point for doll."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from doll import __version__
from doll.artifact import ArtifactError, ArtifactValidationError, WorkspaceFileService
from doll.audit import AuditActorType, AuditResult, AuditService
from doll.backup_cli import backup_app
from doll.diagnostics import redact_exception_text
from doll.memory_cli import memory_app
from doll.project_cli import decision_app, project_app
from doll.settings_cli import permission_app, policy_app, preference_app
from doll.state import StateError, initialize_state_repository, open_state_repository
from doll.state_package_cli import state_package_app
from doll.workspace import ProfilePreference, WorkspaceError, initialize_workspace
from doll.workspace_files import WorkspaceFileError

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
audit_app = typer.Typer(
    help="Inspect append-oriented local audit events.",
    no_args_is_help=True,
)
artifact_app = typer.Typer(
    help="Create and inspect confined authoritative workspace artifacts.",
    no_args_is_help=True,
)
app.add_typer(state_app, name="state")
app.add_typer(audit_app, name="audit")
app.add_typer(artifact_app, name="artifact")
app.add_typer(preference_app, name="preference")
app.add_typer(policy_app, name="policy")
app.add_typer(permission_app, name="permission")
app.add_typer(memory_app, name="memory")
app.add_typer(project_app, name="project")
app.add_typer(decision_app, name="decision")
app.add_typer(state_package_app, name="state-package")
app.add_typer(backup_app, name="backup")


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
        detail = redact_exception_text(exc)
        typer.echo(f"workspace initialization failed: {detail}", err=True)
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
        detail = redact_exception_text(exc)
        typer.echo(f"state initialization failed: {detail}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("State database initialized.")
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
        detail = redact_exception_text(exc)
        typer.echo(f"state inspection failed: {detail}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("State database: ready")
    typer.echo(f"Schema version: {status.schema_version}")
    typer.echo(f"State revision: {status.state_revision}")
    typer.echo(f"Record count: {status.record_count}")
    typer.echo("Mode: read-only")


@audit_app.command("list")
def audit_list_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Initialized workspace path. Uses the platform data directory by default."
        ),
    ] = None,
    operation_id: Annotated[
        str | None,
        typer.Option("--operation-id", help="Filter by exact operation ID."),
    ] = None,
    action: Annotated[
        str | None,
        typer.Option("--action", help="Filter by exact audit action."),
    ] = None,
    actor_type: Annotated[
        str | None,
        typer.Option("--actor-type", help="Filter by actor type."),
    ] = None,
    result: Annotated[
        str | None,
        typer.Option("--result", help="Filter by operation result."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=200, help="Maximum events to display."),
    ] = 50,
) -> None:
    """List audit events through a read-only state connection."""

    try:
        with open_state_repository(path, read_only=True) as repository:
            events = AuditService(repository).list(
                operation_id=operation_id,
                action=action,
                actor_type=cast(AuditActorType | None, actor_type),
                result=cast(AuditResult | None, result),
                limit=limit,
            )
    except (WorkspaceError, StateError) as exc:
        typer.echo(f"audit listing failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    if not events:
        typer.echo("No audit events.")
        return

    for event in events:
        target = event.target_type or "-"
        summary = event.summary or "-"
        error_class = event.error_class or "-"
        typer.echo(
            f"{event.occurred_at} {event.result} {event.actor_type} {event.action} "
            f"operation={event.operation_id} target={target} "
            f"error={error_class} summary={summary}"
        )


@artifact_app.command("create")
def artifact_create_command(
    managed_path: Annotated[
        str,
        typer.Argument(help="Portable path relative to workspace artifacts/ using / separators."),
    ],
    title: Annotated[str, typer.Option("--title", help="Artifact title.")],
    workspace_path: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            help="Initialized workspace path. Uses the platform data directory by default.",
        ),
    ] = None,
    artifact_type: Annotated[
        str,
        typer.Option("--artifact-type", help="Stable artifact type identifier."),
    ] = "text",
    operation_id: Annotated[
        str | None,
        typer.Option("--operation-id", help="Operation ID for record and audit attribution."),
    ] = None,
    format: Annotated[
        str | None,
        typer.Option("--format", help="Optional portable format identifier."),
    ] = "txt",
    media_type: Annotated[
        str | None,
        typer.Option("--media-type", help="Optional media type."),
    ] = "text/plain",
    max_bytes: Annotated[
        int | None,
        typer.Option("--max-bytes", min=1, help="Optional lower per-artifact byte limit."),
    ] = None,
) -> None:
    """Read UTF-8 text from stdin and create one new managed artifact."""

    text = typer.get_text_stream("stdin").read()
    try:
        with open_state_repository(workspace_path) as repository:
            artifact = WorkspaceFileService(repository).create_text(
                managed_path=managed_path,
                text=text,
                title=title,
                artifact_type=artifact_type,
                operation_id=operation_id,
                format=format,
                media_type=media_type,
                max_bytes=max_bytes,
            )
    except (ArtifactValidationError, WorkspaceFileError) as exc:
        detail = redact_exception_text(exc)
        typer.echo(f"artifact creation rejected: {detail}", err=True)
        raise typer.Exit(code=2) from exc
    except (WorkspaceError, StateError, ArtifactError) as exc:
        typer.echo(f"artifact creation failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("Artifact created.")
    typer.echo(f"Artifact ID: {artifact.artifact_id}")
    typer.echo(f"Managed path: {artifact.managed_path}")
    typer.echo(f"Content hash: {artifact.content_hash}")
    typer.echo(f"Size bytes: {artifact.size_bytes}")
    typer.echo(f"Operation ID: {artifact.operation_id}")


@artifact_app.command("list")
def artifact_list_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Initialized workspace path. Uses the platform data directory by default."
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=200, help="Maximum artifacts to display."),
    ] = 50,
) -> None:
    """List artifact records through a read-only state connection."""

    try:
        with open_state_repository(path, read_only=True) as repository:
            artifacts = WorkspaceFileService(repository).list(limit=limit)
    except (WorkspaceError, StateError, ArtifactError) as exc:
        typer.echo(f"artifact listing failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    if not artifacts:
        typer.echo("No artifacts.")
        return

    for artifact in artifacts:
        typer.echo(
            f"{artifact.artifact_id} path={artifact.managed_path} "
            f"size={artifact.size_bytes} hash={artifact.content_hash} "
            f"operation={artifact.operation_id}"
        )


@artifact_app.command("verify")
def artifact_verify_command(
    artifact_id: Annotated[str, typer.Argument(help="Artifact record ID to verify.")],
    path: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            help="Initialized workspace path. Uses the platform data directory by default.",
        ),
    ] = None,
) -> None:
    """Verify a managed artifact against its authoritative hash and size."""

    try:
        with open_state_repository(path, read_only=True) as repository:
            verification = WorkspaceFileService(repository).verify(artifact_id)
    except (WorkspaceError, StateError, ArtifactError, KeyError) as exc:
        typer.echo(f"artifact verification failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("Artifact verified.")
    typer.echo(f"Artifact ID: {verification.artifact.artifact_id}")
    typer.echo(f"Managed path: {verification.artifact.managed_path}")
    typer.echo(f"Content hash: {verification.actual_hash}")
    typer.echo(f"Size bytes: {verification.actual_size_bytes}")


@app.command("version")
def version_command() -> None:
    """Print the installed doll version."""

    typer.echo(__version__)


def main() -> None:  # pragma: no cover - exercised through installed entry points.
    """Run the doll command-line application."""

    app(prog_name="doll")
