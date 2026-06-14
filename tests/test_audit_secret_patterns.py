from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.audit import AuditService, AuditValidationError


def test_private_key_and_jwt_like_values_are_rejected(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        with pytest.raises(AuditValidationError):
            service.append(
                action="audit.secret",
                result="denied",
                metadata={
                    "note": "-----BEGIN PRIVATE KEY----- abc -----END PRIVATE KEY-----"
                },
            )
        with pytest.raises(AuditValidationError):
            service.append(
                action="audit.secret",
                result="denied",
                metadata={
                    "note": "eyJabcdefghijk.abcdefghijk.abcdefghijk"
                },
            )
