"""Synthetic fixtures and refusal checks for IMP-012."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.backup import BackupError
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.restore import RestoreError, restore_workspace_backup
from doll.settings import PermissionService, PolicyService, PreferenceService
from doll.state_package import StatePackageError, export_state_package
from imp_012_common import ARTIFACT_TEXT, TIMESTAMP, tamper_archive


def seed(root: Path) -> dict[str, Any]:
    workspace_record = workspace.initialize_workspace(root)
    with state.initialize_state_repository(workspace_record.root):
        pass
    with state.open_state_repository(workspace_record.root) as repository:
        preference = PreferenceService(repository).create(
            key="output.language",
            value={"language": "日本語", "mode": "continuity"},
            description="IMP-012 synthetic preference",
            operation_id="imp-012-preference",
        )
        policy = PolicyService(repository).create(
            key="continuity.offline",
            rule="Continuity remains available without a model or network.",
            enabled=True,
            operation_id="imp-012-policy",
        )
        permission = PermissionService(repository).create(
            capability_id="artifact.create",
            scope={"kind": "project", "project_id": "imp-012", "max_bytes": 4096},
            mode="scoped",
            operation_id="imp-012-permission",
        )
        memory = ConfirmedMemoryService(repository).create(
            subject="IMP-012 continuity",
            content="State survives restart, export, backup, and restore.",
            operation_id="imp-012-memory",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="acceptance/continuity-日本語.txt",
            text=ARTIFACT_TEXT,
            title="IMP-012 continuity artifact",
            operation_id="imp-012-artifact",
        )
        project = ProjectService(repository).create(
            name="IMP-012 continuity project",
            description="Synthetic continuity acceptance project.",
            project_status="active",
            started_at=TIMESTAMP,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="imp-012-project",
        )
        decision = DecisionService(repository).create(
            decision="Require continuity before Phase 3.",
            reason="Safety work depends on recoverable state.",
            decision_status="accepted",
            decided_at=TIMESTAMP,
            alternatives=("Proceed without a continuity gate",),
            constraints=("No model runtime", "No cloud credentials"),
            project_id=project.project_id,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="imp-012-decision",
        )
        project = ProjectService(repository).update(
            project.project_id,
            expected_revision=project.revision,
            name=project.name,
            description=project.description,
            project_status=project.project_status,
            started_at=project.started_at,
            decision_ids=(decision.decision_id,),
            memory_ids=project.memory_ids,
            artifact_ids=project.artifact_ids,
            operation_id="imp-012-project-link",
        )
        status = repository.status()
        audit_count = len(AuditService(repository).list(limit=200))
    return {
        "workspace": workspace_record,
        "preference": preference,
        "policy": policy,
        "permission": permission,
        "memory": memory,
        "artifact": artifact,
        "project": project,
        "decision": decision,
        "status": status,
        "audit_count": audit_count,
    }


def restart_checks(
    source: dict[str, Any],
) -> tuple[dict[str, bool], bool, Path, object]:
    root = source["workspace"].root
    package = root.parent / "state-package.zip"
    with state.open_state_repository(root, read_only=True) as repository:
        artifact_check = WorkspaceFileService(repository).verify(source["artifact"].artifact_id)
        checks = {
            "preference": PreferenceService(repository).get(source["preference"].record_id).value
            == source["preference"].value,
            "policy": PolicyService(repository).get(source["policy"].record_id).rule
            == source["policy"].rule,
            "permission": PermissionService(repository).get(source["permission"].record_id).scope
            == source["permission"].scope,
            "memory": ConfirmedMemoryService(repository).get(source["memory"].record_id).content
            == source["memory"].content,
            "project": ProjectService(repository).get(source["project"].project_id).decision_ids
            == (source["decision"].decision_id,),
            "decision": DecisionService(repository).get(source["decision"].decision_id).project_id
            == source["project"].project_id,
            "artifact": artifact_check.actual_hash == source["artifact"].content_hash,
            "audit": len(AuditService(repository).list(limit=200)) == source["audit_count"],
        }
        try:
            PreferenceService(repository).create(key="forbidden", value=True)
        except state.ReadOnlyStateError:
            denied = True
        else:
            denied = False
        exported = export_state_package(repository, package, exported_at=TIMESTAMP)
    return checks, denied, package, exported


def refusal_checks(backup: Path, root: Path) -> tuple[bool, bool, bool]:
    populated = root / "last-known-good"
    populated.mkdir()
    sentinel = populated / "sentinel.txt"
    sentinel.write_text("last-known-good\n", encoding="utf-8")
    try:
        restore_workspace_backup(backup, populated)
    except RestoreError:
        populated_refused = True
    else:
        populated_refused = False

    tampered = root / "tampered.zip"
    tamper_archive(backup, tampered)
    target = root / "tampered-target"
    try:
        restore_workspace_backup(tampered, target)
    except (BackupError, RestoreError, StatePackageError):
        tampered_refused = True
    else:
        tampered_refused = False
    preserved = sentinel.read_text(encoding="utf-8") == "last-known-good\n"
    return populated_refused, tampered_refused, preserved and not target.exists()
