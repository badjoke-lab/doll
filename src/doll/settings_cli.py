"""Management CLI groups for preferences, policies, and permissions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer

from doll.settings import (
    PermissionMode,
    PermissionService,
    PolicyService,
    PreferenceService,
    SettingsError,
)
from doll.state import RecordSensitivity, StateError, open_state_repository
from doll.workspace import WorkspaceError

preference_app = typer.Typer(help="Manage authoritative user preferences.", no_args_is_help=True)
policy_app = typer.Typer(help="Manage authoritative durable policies.", no_args_is_help=True)
permission_app = typer.Typer(help="Manage scoped capability permissions.", no_args_is_help=True)


def _json_value(raw: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("value must be valid JSON") from exc


def _json_object(raw: str) -> dict[str, object]:
    value = _json_value(raw)
    if not isinstance(value, dict):
        raise typer.BadParameter("scope must be a JSON object")
    return cast(dict[str, object], value)


def _fail(prefix: str, exc: BaseException) -> None:
    typer.echo(f"{prefix}: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2)


@preference_app.command("create")
def preference_create(
    key: Annotated[str, typer.Argument(help="Stable preference key.")],
    value_json: Annotated[str, typer.Option("--value-json", help="JSON preference value.")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
    sensitivity: Annotated[str, typer.Option("--sensitivity")] = "personal",
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PreferenceService(repository).create(
                key=key,
                value=_json_value(value_json),
                description=description,
                operation_id=operation_id,
                sensitivity=cast(RecordSensitivity, sensitivity),
            )
    except (WorkspaceError, StateError, SettingsError, typer.BadParameter) as exc:
        _fail("preference creation failed", exc)
    typer.echo("Preference created.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Key: {info.key}")
    typer.echo(f"Revision: {info.revision}")


@preference_app.command("update")
def preference_update(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    value_json: Annotated[str, typer.Option("--value-json")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PreferenceService(repository).update(
                record_id,
                expected_revision=revision,
                value=_json_value(value_json),
                description=description,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, SettingsError, typer.BadParameter, KeyError) as exc:
        _fail("preference update failed", exc)
    typer.echo("Preference updated.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Revision: {info.revision}")


@preference_app.command("get")
def preference_get(
    record_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            info = PreferenceService(repository).get(record_id)
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("preference inspection failed", exc)
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Key: {info.key}")
    typer.echo(f"Status: {info.status}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Value JSON: {json.dumps(info.value, ensure_ascii=False, sort_keys=True)}")


@preference_app.command("list")
def preference_list(
    workspace: Annotated[Path | None, typer.Argument()] = None,
    include_archived: Annotated[bool, typer.Option("--include-archived")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            items = PreferenceService(repository).list(
                include_archived=include_archived, limit=limit
            )
    except (WorkspaceError, StateError, SettingsError) as exc:
        _fail("preference listing failed", exc)
    if not items:
        typer.echo("No preferences.")
        return
    for item in items:
        typer.echo(f"{item.record_id} key={item.key} status={item.status} revision={item.revision}")


@preference_app.command("archive")
def preference_archive(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PreferenceService(repository).archive(
                record_id, expected_revision=revision, operation_id=operation_id
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("preference archive failed", exc)
    typer.echo(f"Preference archived: {info.record_id} revision={info.revision}")


@policy_app.command("create")
def policy_create(
    key: Annotated[str, typer.Argument()],
    rule: Annotated[str, typer.Option("--rule")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PolicyService(repository).create(
                key=key,
                rule=rule,
                enabled=enabled,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, SettingsError) as exc:
        _fail("policy creation failed", exc)
    typer.echo("Policy created.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Key: {info.key}")
    typer.echo(f"Revision: {info.revision}")


@policy_app.command("update")
def policy_update(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    rule: Annotated[str, typer.Option("--rule")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PolicyService(repository).update(
                record_id,
                expected_revision=revision,
                rule=rule,
                enabled=enabled,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("policy update failed", exc)
    typer.echo(f"Policy updated: {info.record_id} revision={info.revision}")


@policy_app.command("get")
def policy_get(
    record_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            info = PolicyService(repository).get(record_id)
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("policy inspection failed", exc)
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Key: {info.key}")
    typer.echo(f"Status: {info.status}")
    typer.echo(f"Enabled: {str(info.enabled).lower()}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Rule: {info.rule}")


@policy_app.command("list")
def policy_list(
    workspace: Annotated[Path | None, typer.Argument()] = None,
    include_archived: Annotated[bool, typer.Option("--include-archived")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            items = PolicyService(repository).list(include_archived=include_archived, limit=limit)
    except (WorkspaceError, StateError, SettingsError) as exc:
        _fail("policy listing failed", exc)
    if not items:
        typer.echo("No policies.")
        return
    for item in items:
        typer.echo(
            f"{item.record_id} key={item.key} enabled={str(item.enabled).lower()} "
            f"status={item.status} revision={item.revision}"
        )


@policy_app.command("archive")
def policy_archive(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PolicyService(repository).archive(
                record_id, expected_revision=revision, operation_id=operation_id
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("policy archive failed", exc)
    typer.echo(f"Policy archived: {info.record_id} revision={info.revision}")


@permission_app.command("create")
def permission_create(
    capability_id: Annotated[str, typer.Argument()],
    mode: Annotated[str, typer.Option("--mode")],
    scope_json: Annotated[str, typer.Option("--scope-json")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    expires_at: Annotated[str | None, typer.Option("--expires-at")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PermissionService(repository).create(
                capability_id=capability_id,
                scope=_json_object(scope_json),
                mode=cast(PermissionMode, mode),
                expires_at=expires_at,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, SettingsError, typer.BadParameter) as exc:
        _fail("permission creation failed", exc)
    typer.echo("Permission created.")
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Capability ID: {info.capability_id}")
    typer.echo(f"Mode: {info.mode}")
    typer.echo(f"Scope kind: {info.scope['kind']}")
    typer.echo(f"Revision: {info.revision}")


@permission_app.command("update")
def permission_update(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    mode: Annotated[str, typer.Option("--mode")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    expires_at: Annotated[str | None, typer.Option("--expires-at")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PermissionService(repository).update(
                record_id,
                expected_revision=revision,
                mode=cast(PermissionMode, mode),
                expires_at=expires_at,
                operation_id=operation_id,
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("permission update failed", exc)
    typer.echo(f"Permission updated: {info.record_id} mode={info.mode} revision={info.revision}")


@permission_app.command("get")
def permission_get(
    record_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            service = PermissionService(repository)
            info = service.get(record_id)
            decision = service.effective(record_id)
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("permission inspection failed", exc)
    typer.echo(f"Record ID: {info.record_id}")
    typer.echo(f"Capability ID: {info.capability_id}")
    typer.echo(f"Status: {info.status}")
    typer.echo(f"Mode: {info.mode}")
    typer.echo(f"Effective mode: {decision.effective_mode}")
    typer.echo(f"Reason: {decision.reason}")
    typer.echo(f"Revision: {info.revision}")
    typer.echo(f"Scope JSON: {json.dumps(info.scope, ensure_ascii=False, sort_keys=True)}")


@permission_app.command("list")
def permission_list(
    workspace: Annotated[Path | None, typer.Argument()] = None,
    include_archived: Annotated[bool, typer.Option("--include-archived")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            service = PermissionService(repository)
            items = service.list(include_archived=include_archived, limit=limit)
    except (WorkspaceError, StateError, SettingsError) as exc:
        _fail("permission listing failed", exc)
    if not items:
        typer.echo("No permissions.")
        return
    for item in items:
        typer.echo(
            f"{item.record_id} capability={item.capability_id} mode={item.mode} "
            f"scope_kind={item.scope['kind']} status={item.status} revision={item.revision}"
        )


@permission_app.command("resolve")
def permission_resolve(
    capability_id: Annotated[str, typer.Argument()],
    scope_json: Annotated[str, typer.Option("--scope-json")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace, read_only=True) as repository:
            decision = PermissionService(repository).resolve(
                capability_id=capability_id, scope=_json_object(scope_json)
            )
    except (WorkspaceError, StateError, SettingsError, typer.BadParameter) as exc:
        _fail("permission resolution failed", exc)
    typer.echo(f"Effective mode: {decision.effective_mode}")
    typer.echo(f"Reason: {decision.reason}")
    if decision.record_id is not None:
        typer.echo(f"Record ID: {decision.record_id}")


@permission_app.command("consume-once")
def permission_consume_once(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    operation_id: Annotated[str, typer.Option("--operation-id")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PermissionService(repository).consume_allow_once(
                record_id,
                expected_revision=revision,
                operation_id=operation_id,
                actor_type="capability",
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("permission consumption failed", exc)
    typer.echo(f"Allow-once permission consumed: {info.record_id} revision={info.revision}")


@permission_app.command("archive")
def permission_archive(
    record_id: Annotated[str, typer.Argument()],
    revision: Annotated[int, typer.Option("--revision", min=1)],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    operation_id: Annotated[str | None, typer.Option("--operation-id")] = None,
) -> None:
    try:
        with open_state_repository(workspace) as repository:
            info = PermissionService(repository).archive(
                record_id, expected_revision=revision, operation_id=operation_id
            )
    except (WorkspaceError, StateError, SettingsError, KeyError) as exc:
        _fail("permission archive failed", exc)
    typer.echo(f"Permission archived: {info.record_id} revision={info.revision}")
