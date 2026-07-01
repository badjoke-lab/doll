from __future__ import annotations

import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.settings import PreferenceService
from doll.shutdown_escape import (
    ROOT,
    ShutdownEscapeExportError,
    ShutdownEscapeIntegrityError,
    ShutdownEscapeValidationError,
    export_shutdown_escape_bundle,
    inspect_shutdown_escape_bundle,
    verify_shutdown_escape_bundle,
)
from doll.state import ConversationEventRecord, ConversationRecord

EXPORTED_AT = "2026-07-02T01:00:00Z"
NAMESPACE = UUID("b89336d0-b3a0-42d1-98ab-963315c1fe3e")


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE, name))


def _initialized(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _populated(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        PreferenceService(repository).create(
            key="private.shutdown-escape",
            value="must-not-export",
            sensitivity="secret",
            operation_id="escape-secret",
        )
        memory = ConfirmedMemoryService(repository).create(
            subject="継続方針",
            content="ローカル状態を保持する。",
            operation_id="escape-memory",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="escape/recovery.txt",
            text="recoverable artifact\n",
            title="Recovery artifact",
            operation_id="escape-artifact",
        )
        project = ProjectService(repository).create(
            name="Shutdown escape",
            description="Verify user-owned recovery.",
            project_status="active",
            started_at="2026-07-02T00:00:00Z",
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="escape-project",
        )
        decision = DecisionService(repository).create(
            decision="Keep a generic exit",
            reason="The service may disappear.",
            decision_status="accepted",
            decided_at="2026-07-02T00:10:00Z",
            project_id=project.project_id,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="escape-decision",
        )
        ProjectService(repository).update(
            project.project_id,
            expected_revision=1,
            name=project.name,
            description=project.description,
            project_status=project.project_status,
            started_at=project.started_at,
            decision_ids=(decision.decision_id,),
            memory_ids=project.memory_ids,
            artifact_ids=project.artifact_ids,
            operation_id="escape-project-link",
        )
        conversation = ConversationRecord(
            conversation_id=_id("conversation"),
            title="Portable conversation",
            source_environment_id=None,
            source_conversation_id=None,
        )
        repository.save_conversation(conversation)
        user = ConversationEventRecord(
            event_id=_id("event:user"),
            conversation_id=conversation.conversation_id,
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
            parent_event_ids=(),
            sequence_hint=0,
            content_reference=f"artifact:{artifact.artifact_id}",
            occurred_at="2026-07-02T00:20:00Z",
        )
        repository.save_conversation_event(user)
        repository.save_conversation_event(
            ConversationEventRecord(
                event_id=_id("event:assistant"),
                conversation_id=conversation.conversation_id,
                event_kind="assistant_message",
                actor_type="assistant",
                origin_class="model_proposal",
                parent_event_ids=(user.event_id,),
                sequence_hint=1,
                content_reference=f"artifact:{artifact.artifact_id}",
                occurred_at="2026-07-02T00:21:00Z",
            )
        )
    return initialized


def test_export_is_deterministic_and_standalone_inspectable(tmp_path: Path) -> None:
    initialized = _populated(tmp_path)
    first = tmp_path / "first.escape.zip"
    second = tmp_path / "second.escape.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        before = repository.status()
        inspection = export_shutdown_escape_bundle(
            repository,
            first,
            exported_at=EXPORTED_AT,
        )
        assert repository.status() == before
        second_inspection = export_shutdown_escape_bundle(
            repository,
            second,
            exported_at=EXPORTED_AT,
        )
        assert repository.status() == before

    assert first.read_bytes() == second.read_bytes()
    assert inspection == second_inspection
    assert inspection.record_counts["memory"] == 1
    assert inspection.record_counts["project"] == 1
    assert inspection.record_counts["decision"] == 1
    assert inspection.record_counts["artifact"] == 1
    assert inspection.record_counts["conversation"] == 1
    assert inspection.record_counts["conversation_event"] == 2
    assert inspection.omitted_secret_counts["preference"] == 1
    assert inspection.generic_conversation_export is True
    assert inspection.resume_bundle_count == 1
    assert all(
        inspection.recoverable_surfaces[item]
        for item in (
            "artifacts",
            "confirmed_memory",
            "conversations",
            "decisions",
            "projects",
            "state_package",
        )
    )
    assert verify_shutdown_escape_bundle(first) == inspection
    assert inspect_shutdown_escape_bundle(first) == inspection

    with zipfile.ZipFile(first, "r") as archive:
        names = set(archive.namelist())
        script = tmp_path / "inspect_escape.py"
        script.write_bytes(archive.read(f"{ROOT}/inspect_escape.py"))
        assert f"{ROOT}/state/state-package.doll.zip" in names
        assert f"{ROOT}/conversations/transcript.md" in names
        assert len([name for name in names if name.startswith(f"{ROOT}/projects/")]) == 1
        manifest = json.loads(archive.read(f"{ROOT}/manifest.json"))
        assert manifest["inspection_requirements"] == {
            "cloud_credentials": False,
            "doll_service": False,
            "model_execution": False,
            "network_access": False,
            "preferred_ui": False,
            "python_standard_library": True,
        }

    completed = subprocess.run(
        [sys.executable, "-I", str(script), str(first)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    standalone = json.loads(completed.stdout)
    assert standalone["result"] == "pass"
    assert standalone["record_counts"] == inspection.record_counts
    assert standalone["resume_bundle_count"] == 1


def test_empty_workspace_has_only_state_recovery_surface(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    output = tmp_path / "empty.escape.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        inspection = export_shutdown_escape_bundle(
            repository,
            output,
            exported_at=EXPORTED_AT,
        )

    assert inspection.generic_conversation_export is False
    assert inspection.resume_bundle_count == 0
    assert inspection.recoverable_surfaces["state_package"] is True
    assert inspection.recoverable_surfaces["conversations"] is False
    with zipfile.ZipFile(output, "r") as archive:
        assert not any(name.startswith(f"{ROOT}/conversations/") for name in archive.namelist())
        assert not any(name.startswith(f"{ROOT}/projects/") for name in archive.namelist())


def test_export_rejects_write_repository_and_unsafe_destinations(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(ShutdownEscapeValidationError):
            export_shutdown_escape_bundle(
                repository, tmp_path / "write.zip", exported_at=EXPORTED_AT
            )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ShutdownEscapeValidationError):
            export_shutdown_escape_bundle(
                repository,
                initialized.root / "inside.zip",
                exported_at=EXPORTED_AT,
            )
        existing = tmp_path / "existing.zip"
        existing.write_bytes(b"existing")
        with pytest.raises(ShutdownEscapeExportError):
            export_shutdown_escape_bundle(repository, existing, exported_at=EXPORTED_AT)
        assert existing.read_bytes() == b"existing"


def _rewrite_zip(source: Path, target: Path, *, mutate: str | None = None) -> None:
    with zipfile.ZipFile(source, "r") as current, zipfile.ZipFile(target, "w") as rewritten:
        for info in current.infolist():
            content = current.read(info)
            if info.filename == mutate:
                content += b"x"
            rewritten.writestr(info, content)


def test_verifier_rejects_tampering_and_unsafe_members(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        export_shutdown_escape_bundle(repository, source, exported_at=EXPORTED_AT)

    tampered = tmp_path / "tampered.zip"
    _rewrite_zip(source, tampered, mutate=f"{ROOT}/manifest.json")
    with pytest.raises(ShutdownEscapeIntegrityError):
        verify_shutdown_escape_bundle(tampered)

    unsafe = tmp_path / "unsafe.zip"
    info = zipfile.ZipInfo("../escape")
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr(info, b"x")
    with pytest.raises(ShutdownEscapeIntegrityError):
        verify_shutdown_escape_bundle(unsafe)
