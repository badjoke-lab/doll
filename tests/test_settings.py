from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.audit import AuditService
from doll.settings import (
    DuplicateSettingError,
    ForbiddenPermissionMutationError,
    PermissionDeniedError,
    PermissionMode,
    PermissionService,
    PolicyService,
    PreferenceService,
    SettingsCorruptError,
    SettingsValidationError,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_preference_lifecycle_revision_audit_and_restart(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PreferenceService(repository)
        created = service.create(
            key="output.language",
            value={"language": "日本語", "verbose": False},
            description="表示言語",
            operation_id="preference-create",
        )
        assert created.revision == 1
        assert created.value == {"language": "日本語", "verbose": False}
        assert repository.status().state_revision == 1

        updated = service.update(
            created.record_id,
            expected_revision=1,
            value={"language": "日本語", "verbose": True},
            description="更新済み",
            operation_id="preference-update",
        )
        assert updated.revision == 2
        assert updated.value == {"language": "日本語", "verbose": True}

        with pytest.raises(state.StaleRevisionError):
            service.update(
                created.record_id,
                expected_revision=1,
                value={"language": "en"},
            )

        archived = service.archive(
            created.record_id,
            expected_revision=2,
            operation_id="preference-archive",
        )
        assert archived.status == "archived"
        assert service.list() == ()
        assert service.list(include_archived=True) == (archived,)
        assert repository.status().state_revision == 3

        events = AuditService(repository).list(limit=10)
        assert [event.action for event in reversed(events)] == [
            "preference.create",
            "preference.update",
            "preference.archive",
        ]

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        restored = PreferenceService(repository).get(created.record_id)
        assert restored.status == "archived"
        assert restored.value == {"language": "日本語", "verbose": True}


def test_preference_duplicate_and_invalid_json_have_no_side_effect(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PreferenceService(repository)
        service.create(key="verbosity", value="normal")
        revision = repository.status().state_revision
        with pytest.raises(DuplicateSettingError):
            service.create(key="verbosity", value="high")
        with pytest.raises(SettingsValidationError):
            service.create(key="bad", value={"secret": "not-a-credential-fixture"})
        assert repository.status().state_revision == revision
        assert len(service.list()) == 1
        assert len(AuditService(repository).list()) == 1


def test_policy_lifecycle_and_model_mutation_rejection(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PolicyService(repository)
        created = service.create(
            key="network.no-post",
            rule="外部POSTリクエストを実行しない",
            enabled=True,
            operation_id="policy-create",
        )
        assert created.enabled is True
        updated = service.update(
            created.record_id,
            expected_revision=1,
            rule="外部の状態変更リクエストは明示承認なしに実行しない",
            enabled=True,
        )
        assert updated.revision == 2
        with pytest.raises(ForbiddenPermissionMutationError):
            service.update(
                created.record_id,
                expected_revision=2,
                rule="モデルが変更した規則",
                enabled=False,
                actor_type="model",
            )
        archived = service.archive(created.record_id, expected_revision=2)
        assert archived.status == "archived"


@pytest.mark.parametrize("mode", ["allow_all", "allow-all", "global_allow", "yes"])
def test_permission_rejects_allow_all_equivalents(tmp_path: Path, mode: str) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(SettingsValidationError):
            PermissionService(repository).create(
                capability_id="artifact.create",
                scope={"kind": "global"},
                mode=cast(PermissionMode, mode),
            )
        assert repository.status().state_revision == 0


def test_scoped_permission_requires_non_global_constraints(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        with pytest.raises(SettingsValidationError):
            service.create(
                capability_id="artifact.create",
                scope={"kind": "global"},
                mode="scoped",
            )
        with pytest.raises(SettingsValidationError):
            service.create(
                capability_id="artifact.create",
                scope={"kind": "project"},
                mode="scoped",
            )
        created = service.create(
            capability_id="artifact.create",
            scope={"kind": "project", "project_id": "project-1", "max_bytes": 1024},
            mode="scoped",
            operation_id="permission-scoped",
        )
        assert service.effective(created.record_id).effective_mode == "scoped"


def test_permission_default_deny_expiration_and_duplicate_identity(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    scope: dict[str, object] = {"kind": "project", "project_id": "project-1"}
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        missing = service.resolve(capability_id="artifact.create", scope=scope)
        assert missing.effective_mode == "denied"
        assert missing.reason == "no_record"

        expired = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        created = service.create(
            capability_id="artifact.create",
            scope=scope,
            mode="ask",
            expires_at=expired,
        )
        decision = service.effective(created.record_id)
        assert decision.effective_mode == "denied"
        assert decision.reason == "expired"

        with pytest.raises(DuplicateSettingError):
            service.create(
                capability_id="artifact.create",
                scope={"project_id": "project-1", "kind": "project"},
                mode="denied",
            )


def test_permission_creation_and_widening_require_user_actor(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        for actor in ("model", "runtime", "capability", "system"):
            with pytest.raises(ForbiddenPermissionMutationError):
                service.create(
                    capability_id="artifact.create",
                    scope={"kind": "global"},
                    mode="ask",
                    actor_type=cast(object, actor),  # type: ignore[arg-type]
                )
        created = service.create(
            capability_id="artifact.create",
            scope={"kind": "global"},
            mode="denied",
        )
        with pytest.raises(ForbiddenPermissionMutationError):
            service.update(
                created.record_id,
                expected_revision=1,
                mode="ask",
                actor_type="model",
            )
        assert service.get(created.record_id).mode == "denied"
        assert repository.status().state_revision == 1


def test_allow_once_is_consumed_atomically_and_cannot_be_reused(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        created = service.create(
            capability_id="artifact.create",
            scope={"kind": "global"},
            mode="allow_once",
            operation_id="permission-create-once",
        )
        assert created.remaining_uses == 1
        consumed = service.consume_allow_once(
            created.record_id,
            expected_revision=1,
            operation_id="permission-consume-once",
        )
        assert consumed.mode == "denied"
        assert consumed.remaining_uses == 0
        assert consumed.last_used_at is not None
        with pytest.raises(PermissionDeniedError):
            service.consume_allow_once(
                created.record_id,
                expected_revision=2,
                operation_id="permission-consume-again",
            )
        assert repository.status().state_revision == 2
        events = AuditService(repository).list(limit=10)
        assert {event.action for event in events} == {
            "permission.create",
            "permission.consume_once",
        }


def test_permission_update_archive_and_read_only_rejection(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = PermissionService(repository)
        created = service.create(
            capability_id="web.fetch",
            scope={"kind": "host", "host": "example.invalid"},
            mode="ask",
        )
        updated = service.update(
            created.record_id,
            expected_revision=1,
            mode="scoped",
        )
        assert updated.mode == "scoped"
        archived = service.archive(updated.record_id, expected_revision=2)
        assert service.effective(archived.record_id).reason == "archived"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            PreferenceService(repository).create(key="x", value=True)
        with pytest.raises(state.ReadOnlyStateError):
            PolicyService(repository).create(key="x", rule="x")
        with pytest.raises(state.ReadOnlyStateError):
            PermissionService(repository).create(
                capability_id="x", scope={"kind": "global"}, mode="denied"
            )


def test_corrupt_typed_records_are_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        preference = repository.create_record(
            record_type="preference",
            metadata={"preference_key": "x"},
        )
        policy = repository.create_record(
            record_type="policy",
            metadata={"policy_key": "x", "rule": "x", "enabled": "yes"},
        )
        permission = repository.create_record(
            record_type="permission",
            metadata={
                "capability_id": "x",
                "scope": {"kind": "global"},
                "mode": "allow_once",
                "approval_source": "management-cli",
                "last_changed_at": "2026-06-14T00:00:00Z",
                "remaining_uses": 0,
                "permission_identity": "bad",
            },
        )
        with pytest.raises(SettingsCorruptError):
            PreferenceService(repository).get(preference.id)
        with pytest.raises(SettingsCorruptError):
            PolicyService(repository).get(policy.id)
        with pytest.raises(SettingsCorruptError):
            PermissionService(repository).get(permission.id)
