"""Exercise the bounded IMP-058 shutdown escape flow with synthetic state."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID, uuid5

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.settings import PreferenceService
from doll.shutdown_escape import (
    ROOT,
    ShutdownEscapeExportError,
    ShutdownEscapeIntegrityError,
    export_shutdown_escape_bundle,
    verify_shutdown_escape_bundle,
)
from doll.state import ConversationEventRecord, ConversationRecord

EXPORTED_AT = "2026-07-02T02:00:00Z"
NAMESPACE = UUID("9ed2a3ba-bcea-4ed7-aabe-42d7098ee2b9")


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE, name))


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ci", "real-machine"), required=True)
    return parser.parse_args()


def _populate(workspace_root: Path) -> None:
    with state.open_state_repository(workspace_root) as repository:
        PreferenceService(repository).create(
            key="private.shutdown-escape-probe",
            value="synthetic-secret-value",
            sensitivity="secret",
            operation_id="imp058-probe-secret",
        )
        memory = ConfirmedMemoryService(repository).create(
            subject="Synthetic continuity rule",
            content="Preserve local synthetic state.",
            operation_id="imp058-probe-memory",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="imp058/synthetic-recovery.txt",
            text="synthetic recovery artifact\n",
            title="Synthetic recovery artifact",
            operation_id="imp058-probe-artifact",
        )
        project = ProjectService(repository).create(
            name="Synthetic shutdown escape project",
            description="Bounded IMP-058 acceptance fixture.",
            project_status="active",
            started_at="2026-07-02T01:00:00Z",
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="imp058-probe-project",
        )
        decision = DecisionService(repository).create(
            decision="Keep a verified generic exit",
            reason="Synthetic service shutdown must remain recoverable.",
            decision_status="accepted",
            decided_at="2026-07-02T01:10:00Z",
            project_id=project.project_id,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="imp058-probe-decision",
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
            operation_id="imp058-probe-project-link",
        )
        conversation = ConversationRecord(
            conversation_id=_id("conversation"),
            title="Synthetic portable conversation",
        )
        repository.save_conversation(conversation)
        user_event = ConversationEventRecord(
            event_id=_id("event:user"),
            conversation_id=conversation.conversation_id,
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
            parent_event_ids=(),
            sequence_hint=0,
            content_reference=f"artifact:{artifact.artifact_id}",
            occurred_at="2026-07-02T01:20:00Z",
        )
        repository.save_conversation_event(user_event)
        repository.save_conversation_event(
            ConversationEventRecord(
                event_id=_id("event:assistant"),
                conversation_id=conversation.conversation_id,
                event_kind="assistant_message",
                actor_type="assistant",
                origin_class="model_proposal",
                parent_event_ids=(user_event.event_id,),
                sequence_hint=1,
                content_reference=f"artifact:{artifact.artifact_id}",
                occurred_at="2026-07-02T01:21:00Z",
            )
        )


def _standalone_imports(script: Path) -> set[str]:
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.split(".", 1)[0])
    return imports


def _tampered_copy(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source, "r") as current, zipfile.ZipFile(target, "w") as rewritten:
        for info in current.infolist():
            content = current.read(info)
            if info.filename == f"{ROOT}/manifest.json":
                content += b"x"
            rewritten.writestr(info, content)


def _run(mode: str) -> tuple[dict[str, bool], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="doll-imp058-probe-") as raw_root:
        root = Path(raw_root)
        initialized = workspace.initialize_workspace(root / "workspace")
        with state.initialize_state_repository(initialized.root):
            pass
        _populate(initialized.root)

        first = root / "first.shutdown-escape.zip"
        second = root / "second.shutdown-escape.zip"
        with state.open_state_repository(initialized.root, read_only=True) as repository:
            status_before = repository.status()
            audit_before = len(AuditService(repository).list(limit=200))
            first_inspection = export_shutdown_escape_bundle(
                repository,
                first,
                exported_at=EXPORTED_AT,
            )
            second_inspection = export_shutdown_escape_bundle(
                repository,
                second,
                exported_at=EXPORTED_AT,
            )
            status_after = repository.status()
            audit_after = len(AuditService(repository).list(limit=200))

            existing = root / "existing.shutdown-escape.zip"
            existing.write_bytes(b"preserve-me")
            existing_rejected = False
            try:
                export_shutdown_escape_bundle(repository, existing, exported_at=EXPORTED_AT)
            except ShutdownEscapeExportError:
                existing_rejected = existing.read_bytes() == b"preserve-me"

        verified = verify_shutdown_escape_bundle(first)
        with zipfile.ZipFile(first, "r") as archive:
            member_names = tuple(sorted(archive.namelist()))
            inspector = root / "inspect_escape.py"
            inspector.write_bytes(archive.read(f"{ROOT}/inspect_escape.py"))

        imports = _standalone_imports(inspector)
        stdlib_only = bool(imports) and imports <= sys.stdlib_module_names and "doll" not in imports
        shutil.rmtree(initialized.root)
        source_removed = not initialized.root.exists()

        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["NO_PROXY"] = "*"
        environment["HTTP_PROXY"] = "http://127.0.0.1:9"
        environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
        completed = subprocess.run(
            [sys.executable, "-I", str(inspector), str(first)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        standalone = json.loads(completed.stdout)

        tampered = root / "tampered.shutdown-escape.zip"
        _tampered_copy(first, tampered)
        tamper_rejected = False
        try:
            verify_shutdown_escape_bundle(tampered)
        except ShutdownEscapeIntegrityError:
            tamper_rejected = True

        expected_surfaces = {
            "artifacts",
            "confirmed_memory",
            "conversations",
            "decisions",
            "projects",
            "state_package",
        }
        checks = {
            "bundle_exported": first.is_file() and first.stat().st_size > 0,
            "deterministic_bytes": first.read_bytes() == second.read_bytes(),
            "deterministic_inspection": first_inspection == second_inspection == verified,
            "workspace_status_unchanged": status_before == status_after,
            "workspace_audit_unchanged": audit_before == audit_after,
            "state_package_present": f"{ROOT}/state/state-package.doll.zip" in member_names,
            "generic_conversation_export_present": (
                f"{ROOT}/conversations/manifest.json" in member_names
            ),
            "project_resume_bundle_present": any(
                name.startswith(f"{ROOT}/projects/") and name.endswith(".resume.zip")
                for name in member_names
            ),
            "standalone_inspector_stdlib_only": stdlib_only,
            "source_workspace_removed_before_inspection": source_removed,
            "standalone_fresh_process_pass": (
                completed.returncode == 0
                and standalone.get("result") == "pass"
                and standalone.get("top_level_sha256") == first_inspection.top_level_sha256
            ),
            "secret_omission_visible": first_inspection.omitted_secret_counts.get("preference")
            == 1,
            "required_recovery_surfaces_visible": expected_surfaces
            <= {key for key, value in first_inspection.recoverable_surfaces.items() if value},
            "tampering_rejected": tamper_rejected,
            "existing_destination_preserved": existing_rejected,
            "no_model_network_ui_or_cloud_dependency": mode in {"ci", "real-machine"},
        }
        evidence: dict[str, object] = {
            "format": "doll-shutdown-escape",
            "format_version": first_inspection.format_version,
            "bundle_sha256": first_inspection.top_level_sha256,
            "member_count": first_inspection.member_count,
            "record_type_count": len(first_inspection.record_counts),
            "record_count_total": sum(first_inspection.record_counts.values()),
            "omitted_secret_total": sum(first_inspection.omitted_secret_counts.values()),
            "recoverable_surface_count": sum(first_inspection.recoverable_surfaces.values()),
            "generic_conversation_export": first_inspection.generic_conversation_export,
            "resume_bundle_count": first_inspection.resume_bundle_count,
            "standalone_import_count": len(imports),
            "runtime_mode": "real-local" if mode == "real-machine" else "synthetic",
            "source_workspace_removed": source_removed,
        }
        return checks, evidence


def main() -> int:
    arguments = _arguments()
    try:
        checks, evidence = _run(arguments.mode)
        if not all(checks.values()):
            raise RuntimeError("shutdown escape probe checks failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "evidence": evidence,
        }
        status = 0
    except BaseException as exc:
        payload = {
            "result": "fail",
            "error_class": type(exc).__name__,
            "error_stage": "shutdown_escape_probe",
        }
        status = 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
