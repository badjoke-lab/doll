from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import doll.restore as restore
from doll import state
from doll.audit import AuditService
from doll.backup import create_state_backup
from doll.capabilities import CapabilityRegistry, OutboundNetworkPolicy
from doll.confirmation import (
    ConfirmationConsumeActor,
    ConfirmationService,
    ForbiddenConfirmationMutationError,
)
from doll.confirmation_preflight import ConfirmedCapabilityPreflightService
from tests.confirmation_support import (
    FakePermissionResolver,
    MutableClock,
    initialized_workspace,
    preflight_service,
    preview,
    release_tier3_registry,
    tier3_request,
)


def test_confirmation_survives_state_backup_restore_and_fresh_process_validation(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    registry = release_tier3_registry()
    with state.open_state_repository(initialized.root) as repository:
        confirmations = ConfirmationService(repository, clock=clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )

    backup_path = tmp_path / "confirmation-state.zip"
    create_state_backup(
        initialized.root,
        backup_path,
        operation_id="confirmation-backup",
    )
    target = tmp_path / "restored-confirmation"
    result = restore.restore_state_backup(backup_path, target)
    assert result.fresh_process_validated is True

    with state.open_state_repository(target, read_only=True) as repository:
        resolution = ConfirmationService(repository, clock=clock).resolve(
            info.confirmation_id,
            request,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=None,
        )
        assert resolution.reason == "approved"
        assert resolution.info is not None
        assert resolution.info.request_fingerprint == info.request_fingerprint
        assert AuditService(repository).list(action="confirmation.issue", limit=50)


def test_repeated_preview_does_not_pollute_confirmation_lifecycle(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, service = preflight_service(repository, clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        for _ in range(40):
            assert service.preflight(
                request, confirmation_id=info.confirmation_id
            ).authorized
        resolution = confirmations.resolve(
            info.confirmation_id,
            request,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=None,
        )
        assert resolution.reason == "approved"


def test_confirmation_binds_credential_class_and_registry_fingerprint(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, service = preflight_service(repository, clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=replace(preview(), credential_class="api_key"),
            decision="approved",
        )
        missing_credential = service.preflight(
            request,
            confirmation_id=info.confirmation_id,
        )
        assert missing_credential.authorized is False
        assert missing_credential.confirmation_reason == "mismatch"
        exact = service.preflight(
            request,
            confirmation_id=info.confirmation_id,
            credential_class="api_key",
        )
        assert exact.authorized is True

        changed_definitions = tuple(
            replace(definition, description=f"{definition.description} changed")
            if definition.capability_id == "compute.transform"
            else definition
            for definition in registry.definitions()
        )
        changed_registry = CapabilityRegistry(changed_definitions)
        changed_service = ConfirmedCapabilityPreflightService(
            registry=changed_registry,
            permissions=FakePermissionResolver(),
            audit=AuditService(repository),
            network_policy=OutboundNetworkPolicy(enabled=False),
            confirmations=confirmations,
        )
        changed = changed_service.preflight(
            request,
            confirmation_id=info.confirmation_id,
            credential_class="api_key",
        )
        assert changed.authorized is False
        assert changed.confirmation_reason == "mismatch"


def test_confirmation_insert_failure_rolls_back_state_revision(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, _ = preflight_service(repository, clock)
        before = repository.status().state_revision
        repository.connection.execute(
            """
            CREATE TEMP TRIGGER fail_confirmation_issue
            BEFORE INSERT ON audit_events
            WHEN NEW.action = 'confirmation.issue'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic confirmation audit failure');
            END
            """
        )
        with pytest.raises(state.StateCorruptError):
            confirmations.issue(
                request,
                registry=registry,
                preview=preview(),
                decision="approved",
            )
        assert repository.status().state_revision == before
        assert not AuditService(repository).list(action="confirmation.issue", limit=50)


def test_confirmation_consume_rejects_untrusted_actor(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, _ = preflight_service(repository, clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        with pytest.raises(ForbiddenConfirmationMutationError):
            confirmations.consume(
                info.confirmation_id,
                request,
                registry_fingerprint=registry.fingerprint,
                normalized_destination=None,
                actor_type=cast(ConfirmationConsumeActor, "model"),
            )
