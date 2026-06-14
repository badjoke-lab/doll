from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.audit import AuditService, AuditValidationError


def test_private_key_jwt_and_bearer_values_are_rejected(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    private_key_marker = f"-----BEGIN {'PRIVATE'} KEY----- abc -----END PRIVATE KEY-----"
    jwt_like = "eyJ" + "abcdefghijk.abcdefghijk.abcdefghijk"
    bearer_like = "Bearer " + "abcdefghijk12345"

    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        for unsafe_value in (private_key_marker, jwt_like, bearer_like):
            with pytest.raises(AuditValidationError):
                service.append(
                    action="audit.secret",
                    result="denied",
                    metadata={"note": unsafe_value},
                )


def test_composite_secret_keys_and_identifier_paths_are_rejected(
    tmp_path: Path,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        for secret_key in ("db_password", "service_api_key", "auth_access_token"):
            with pytest.raises(AuditValidationError):
                service.append(
                    action="audit.secret-key",
                    result="denied",
                    metadata={secret_key: "synthetic"},
                )

        with pytest.raises(AuditValidationError):
            service.append(
                action="audit.actor",
                result="denied",
                actor_id="password=synthetic-value",
            )
        with pytest.raises(AuditValidationError):
            service.append(
                action="audit.target",
                result="denied",
                target_id="/tmp/private-target",
            )
        with pytest.raises(AuditValidationError):
            service.append(
                action="audit.summary",
                result="denied",
                summary="opened /var/private-target",
            )
