from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.settings import (
    DuplicateSettingError,
    ForbiddenPermissionMutationError,
    PermissionService,
    PolicyService,
    PreferenceService,
    SettingsCorruptError,
    SettingsValidationError,
    _optional_string,
    _permission_metadata,
    _required_string,
    _validate_approval_source,
    _validate_json_value,
    _validate_key,
    _validate_nested_json,
    _validate_optional_utc,
    _validate_permission_mode,
    _validate_scope,
    _validate_text,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


@pytest.mark.parametrize(
    "value",
    ["", " bad key", "bad key", "bad/key", "x" * 121],
)
def test_key_validation_rejects_unsupported_values(value: str) -> None:
    with pytest.raises(SettingsValidationError):
        _validate_key("key", value)


def test_key_and_text_type_validation() -> None:
    with pytest.raises(SettingsValidationError):
        _validate_key("key", cast(str, 123))
    with pytest.raises(SettingsValidationError):
        _validate_text("text", cast(str, 123), 20)
    with pytest.raises(SettingsValidationError):
        _validate_text("text", "", 20)
    with pytest.raises(SettingsValidationError):
        _validate_text("text", "x" * 21, 20)
    with pytest.raises(SettingsValidationError):
        _validate_text("text", "bad\x00text", 20)


def test_json_validation_defensive_branches() -> None:
    with pytest.raises(SettingsValidationError):
        _validate_json_value({"secret": "synthetic"}, maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value({1: "bad"}, maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value("/private/path", maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value("C:\\private\\path", maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value("bad\x00text", maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value("x" * 501, maximum=1000)
    with pytest.raises(SettingsValidationError):
        _validate_json_value(object(), maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value(float("nan"), maximum=100)
    with pytest.raises(SettingsValidationError):
        _validate_json_value({"value": "x" * 100}, maximum=10)

    nested: object = "leaf"
    for _ in range(10):
        nested = [nested]
    with pytest.raises(SettingsValidationError):
        _validate_nested_json(nested, depth=0, scope=False)


def test_scope_mode_approval_and_timestamp_validation() -> None:
    with pytest.raises(SettingsValidationError):
        _validate_scope(cast(dict[str, object], []))
    with pytest.raises(SettingsValidationError):
        _validate_scope({})
    with pytest.raises(SettingsValidationError):
        _validate_scope({"kind": 1})
    with pytest.raises(SettingsValidationError):
        _validate_permission_mode("allow_all", {"kind": "global"})
    with pytest.raises(SettingsValidationError):
        _validate_permission_mode("scoped", {"kind": "global"})
    with pytest.raises(SettingsValidationError):
        _validate_permission_mode("scoped", {"kind": "project"})

    assert _validate_permission_mode("scoped", {"kind": "project", "project_id": "p-1"}) == "scoped"

    with pytest.raises(ForbiddenPermissionMutationError):
        _validate_approval_source("model-output")
    with pytest.raises(SettingsValidationError):
        _validate_optional_utc("time", "2026-06-14T00:00:00")
    with pytest.raises(SettingsValidationError):
        _validate_optional_utc("time", "not-a-timeZ")

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    assert _validate_optional_utc("time", now) == now
    assert _validate_optional_utc("time", None) is None


def test_permission_metadata_and_string_extractors() -> None:
    metadata = _permission_metadata(
        capability_id="artifact.create",
        scope={"kind": "global"},
        mode="allow_once",
        expires_at=None,
        approval_source="management-cli",
        last_changed_at="2026-06-14T00:00:00Z",
        last_used_at=None,
    )
    assert metadata["remaining_uses"] == 1

    explicit = _permission_metadata(
        capability_id="artifact.create",
        scope={"kind": "global"},
        mode="denied",
        expires_at=None,
        approval_source="management-cli",
        last_changed_at="2026-06-14T00:00:00Z",
        last_used_at=None,
        remaining_uses=0,
    )
    assert explicit["remaining_uses"] == 0

    with pytest.raises(SettingsValidationError):
        _required_string({}, "missing")
    with pytest.raises(SettingsValidationError):
        _required_string({"value": 1}, "value")
    assert _optional_string({}, "value") is None
    with pytest.raises(SettingsValidationError):
        _optional_string({"value": 1}, "value")


def test_duplicate_scan_tolerates_unrelated_corrupt_identity(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.create_record(record_type="preference", metadata={})
        created = PreferenceService(repository).create(key="valid.key", value=True)
        assert created.key == "valid.key"


def test_service_limits_wrong_types_and_forbidden_actors(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        preference = PreferenceService(repository)
        policy = PolicyService(repository)
        permission = PermissionService(repository)

        with pytest.raises(SettingsValidationError):
            preference.list(limit=0)
        with pytest.raises(SettingsValidationError):
            policy.list(limit=201)
        with pytest.raises(SettingsValidationError):
            permission.list(limit=0)

        raw = repository.create_record(record_type="other", metadata={})
        with pytest.raises(KeyError):
            preference.get(raw.id)
        with pytest.raises(KeyError):
            policy.get(raw.id)
        with pytest.raises(KeyError):
            permission.get(raw.id)

        with pytest.raises(ForbiddenPermissionMutationError):
            preference.create(key="x", value=True, actor_type="model")
        with pytest.raises(ForbiddenPermissionMutationError):
            policy.create(key="x", rule="rule", actor_type="runtime")
        with pytest.raises(ForbiddenPermissionMutationError):
            permission.consume_allow_once(
                raw.id,
                expected_revision=1,
                operation_id="bad-consumer",
                actor_type=cast(object, "user"),  # type: ignore[arg-type]
            )


def test_duplicate_active_permission_records_are_corrupt(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    scope: dict[str, object] = {"kind": "global"}
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        created = service.create(
            capability_id="artifact.create",
            scope=scope,
            mode="ask",
        )
        repository.create_record(
            record_type="permission",
            title="artifact.create",
            metadata={
                "capability_id": "artifact.create",
                "scope": scope,
                "mode": "ask",
                "expires_at": None,
                "approval_source": "management-cli",
                "last_changed_at": created.last_changed_at,
                "last_used_at": None,
                "remaining_uses": None,
                "permission_identity": created.capability_id + "\0" + '{"kind":"global"}',
            },
        )
        with pytest.raises(state.StateCorruptError):
            service.resolve(capability_id="artifact.create", scope=scope)


@pytest.mark.parametrize(
    "metadata",
    [
        {
            "capability_id": "x",
            "scope": {"kind": "global"},
            "mode": "ask",
            "expires_at": None,
            "approval_source": "bad-source",
            "last_changed_at": "2026-06-14T00:00:00Z",
            "last_used_at": None,
            "remaining_uses": None,
            "permission_identity": 'x\0{"kind":"global"}',
        },
        {
            "capability_id": "x",
            "scope": {"kind": "global"},
            "mode": "ask",
            "expires_at": None,
            "approval_source": "management-cli",
            "last_changed_at": "bad",
            "last_used_at": None,
            "remaining_uses": None,
            "permission_identity": 'x\0{"kind":"global"}',
        },
        {
            "capability_id": "x",
            "scope": {"kind": "global"},
            "mode": "ask",
            "expires_at": None,
            "approval_source": "management-cli",
            "last_changed_at": "2026-06-14T00:00:00Z",
            "last_used_at": None,
            "remaining_uses": 2,
            "permission_identity": 'x\0{"kind":"global"}',
        },
    ],
)
def test_additional_corrupt_permission_variants(
    tmp_path: Path, metadata: dict[str, object]
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        record = repository.create_record(
            record_type="permission",
            metadata=metadata,
        )
        with pytest.raises(SettingsCorruptError):
            PermissionService(repository).get(record.id)


def _insert_raw_permission(
    repository: state.StateRepository,
    *,
    capability_id: str,
    scope: dict[str, object],
    created_at: str,
) -> str:
    import json
    from uuid import uuid4

    record_id = str(uuid4())
    identity = (
        capability_id
        + "\0"
        + json.dumps(
            scope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    metadata = {
        "capability_id": capability_id,
        "scope": scope,
        "mode": "ask",
        "expires_at": None,
        "approval_source": "management-cli",
        "last_changed_at": created_at,
        "last_used_at": None,
        "remaining_uses": None,
        "permission_identity": identity,
    }
    repository.connection.execute(
        """
        INSERT INTO records (
            id, record_type, schema_version, created_at, updated_at, revision,
            status, provenance, sensitivity, title, metadata_json
        ) VALUES (?, 'permission', 1, ?, ?, 1, 'active', 'user-created', 'personal', ?, ?)
        """,
        (
            record_id,
            created_at,
            created_at,
            capability_id,
            json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ),
    )
    return record_id


def test_permission_resolution_has_no_public_list_limit(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    target_scope: dict[str, object] = {"kind": "project", "project_id": "target"}
    with state.open_state_repository(initialized.root) as repository:
        target_id = _insert_raw_permission(
            repository,
            capability_id="artifact.create",
            scope=target_scope,
            created_at="2026-06-14T00:00:00Z",
        )
        for index in range(60):
            _insert_raw_permission(
                repository,
                capability_id=f"unrelated.{index}",
                scope={"kind": "global"},
                created_at=f"2026-06-14T00:{index % 60:02d}:30Z",
            )

        decision = PermissionService(repository).resolve(
            capability_id="artifact.create",
            scope=target_scope,
        )
        assert decision.record_id == target_id
        assert decision.effective_mode == "ask"


def test_duplicate_scan_has_no_internal_record_cap(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    target_scope: dict[str, object] = {"kind": "project", "project_id": "oldest"}
    with state.open_state_repository(initialized.root) as repository:
        _insert_raw_permission(
            repository,
            capability_id="artifact.create",
            scope=target_scope,
            created_at="2026-06-14T00:00:00Z",
        )
        for index in range(205):
            _insert_raw_permission(
                repository,
                capability_id=f"unrelated.{index}",
                scope={"kind": "global"},
                created_at=f"2026-06-15T{index % 24:02d}:{index % 60:02d}:00Z",
            )

        with pytest.raises(DuplicateSettingError):
            PermissionService(repository).create(
                capability_id="artifact.create",
                scope=target_scope,
                mode="denied",
            )


def test_archived_typed_records_are_immutable(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        preferences = PreferenceService(repository)
        preference = preferences.create(key="display.mode", value="normal")
        preference = preferences.archive(preference.record_id, expected_revision=1)
        with pytest.raises(SettingsValidationError):
            preferences.update(
                preference.record_id,
                expected_revision=2,
                value="changed",
            )
        with pytest.raises(SettingsValidationError):
            preferences.archive(preference.record_id, expected_revision=2)

        policies = PolicyService(repository)
        policy = policies.create(key="network.no-post", rule="No external POST")
        policy = policies.archive(policy.record_id, expected_revision=1)
        with pytest.raises(SettingsValidationError):
            policies.update(
                policy.record_id,
                expected_revision=2,
                rule="Changed",
                enabled=False,
            )
        with pytest.raises(SettingsValidationError):
            policies.archive(policy.record_id, expected_revision=2)

        permissions = PermissionService(repository)
        permission = permissions.create(
            capability_id="artifact.create",
            scope={"kind": "global"},
            mode="ask",
        )
        permission = permissions.archive(permission.record_id, expected_revision=1)
        with pytest.raises(SettingsValidationError):
            permissions.update(
                permission.record_id,
                expected_revision=2,
                mode="denied",
            )
        with pytest.raises(SettingsValidationError):
            permissions.archive(permission.record_id, expected_revision=2)


def test_sqlite_mutation_failure_is_normalized_and_rolled_back(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE audit_events")

        with pytest.raises(state.StateCorruptError):
            PreferenceService(repository).create(
                key="display.mode",
                value="normal",
            )

        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'preference'"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert repository.connection.in_transaction is False
