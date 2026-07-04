"""Run the privacy-safe IMP-059 private manual ChatGPT history check."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from doll import state, workspace
from doll.chatgpt_export_import import ChatGPTExportSourceAdapter
from doll.generic_export import GenericExportBuilder
from doll.generic_import_publication import GenericImportPublisher
from doll.shutdown_escape import export_shutdown_escape_bundle

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_COMMIT = "67f6acfe2291bf892b93d9367cacf764367fe30f"
TEST_ID = "IMP-059-CHATGPT-HISTORY-PRIVATE-MANUAL"
_CRITICAL_BLOBS = {
    "src/doll/chatgpt_export_import.py": "ad75f90f087e593bd265e2ca7953a7f8fbcffc36",
    "src/doll/generic_import.py": "bd6a9da65da8b3c72fd2157db46ad75e364baa11",
    "src/doll/generic_import_publication.py": "5154a96cdfd0ec29d319791ef94a994091d85640",
    "src/doll/generic_export.py": "ae22265cedf64e3a6753bf9f3bd5c533aa605d6b",
    "src/doll/shutdown_escape.py": "6fcb97ec3cb0955b7153f690e20a33c79941eb4e",
    "src/doll/state.py": "0a5b30ca6323a913304b97d3b0aaec7b4de1fb2c",
    "src/doll/workspace.py": "7f2724700790f9bde5d071e8b4f7d052f8d53d96",
}
_AUTHORITY_TYPES = (
    "capability",
    "confirmation",
    "credential",
    "memory",
    "permission",
    "policy",
    "procedure",
    "project_checkpoint",
    "work_item",
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("review", "complete"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selection-file", type=Path, required=True)
    parser.add_argument("--source-environment-id", required=True)
    parser.add_argument("--import-batch-id", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--runner-commit", required=True)
    parser.add_argument("--confirm-network-disabled", action="store_true")
    parser.add_argument("--confirm-reviewed", action="store_true")
    return parser.parse_args()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _head() -> str:
    return _git("rev-parse", "HEAD")


def _tracked_blob(commit: str, relative: str) -> str:
    return _git("rev-parse", f"{commit}:{relative}")


def _working_blob(relative: str) -> str:
    return _git("hash-object", relative)


def _verify_commit_binding(runner_commit: str) -> dict[str, bool]:
    if runner_commit != _head():
        raise RuntimeError("runner commit mismatch")
    runner_path = "scripts/run_imp_059_private_manual.py"
    runner_exact = _working_blob(runner_path) == _tracked_blob(runner_commit, runner_path)
    surfaces_exact = all(
        _working_blob(relative) == expected_blob
        for relative, expected_blob in _CRITICAL_BLOBS.items()
    )
    return {
        "implementation_commit_blob_manifest_bound": True,
        "runner_matches_bound_commit": runner_exact,
        "portability_surfaces_match_implementation_commit": surfaces_exact,
    }


def _outside_repository(path: Path) -> bool:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return True
    return False


def _read_private_inputs(
    source: Path,
    selection_file: Path,
) -> tuple[bytes, tuple[str, ...]]:
    if not _outside_repository(source) or not _outside_repository(selection_file):
        raise RuntimeError("private input paths must remain outside the repository")
    source_bytes = source.read_bytes()
    selected = tuple(
        line.strip()
        for line in selection_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not selected:
        raise RuntimeError("selection file is empty")
    return source_bytes, selected


def _initialize_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _authority_count(repository: state.StateRepository) -> int:
    placeholders = ",".join("?" for _ in _AUTHORITY_TYPES)
    row = repository.connection.execute(
        f"SELECT COUNT(*) FROM records WHERE record_type IN ({placeholders})",
        _AUTHORITY_TYPES,
    ).fetchone()
    if row is None:
        raise RuntimeError("authority count query failed")
    return int(row[0])


def _privacy_block() -> dict[str, bool]:
    return {
        "absolute_paths_in_report": False,
        "usernames_in_report": False,
        "hostnames_in_report": False,
        "provider_account_ids_in_report": False,
        "conversation_ids_in_report": False,
        "titles_in_report": False,
        "prompt_or_response_text_in_report": False,
        "native_model_names_in_report": False,
        "secret_values_in_report": False,
        "credentials_in_report": False,
        "private_fixture_content_in_report": False,
    }


def _review_payload(
    *,
    runner_commit: str,
    commit_checks: dict[str, bool],
    staged: Any,
    contract_offline: bool,
) -> dict[str, object]:
    inventory = staged.inventory
    stage_result = staged.stage_result
    checks = {
        **commit_checks,
        "contract_is_offline": contract_offline,
        "selection_is_explicit_and_nonempty": inventory.selected_conversation_count > 0,
        "content_free_review_surface_only": True,
    }
    return {
        "test_id": TEST_ID,
        "specification_version": "0.1",
        "mode": "review",
        "result": "review-ready" if all(checks.values()) else "fail",
        "implementation_commit_sha": IMPLEMENTATION_COMMIT,
        "runner_commit_sha": runner_commit,
        "checks": checks,
        "review": {
            "source_root_hash": inventory.source_root_hash,
            "conversation_count": inventory.conversation_count,
            "selected_conversation_count": inventory.selected_conversation_count,
            "selected_message_count": inventory.selected_message_count,
            "supported_message_count": inventory.supported_message_count,
            "unsupported_message_count": inventory.unsupported_message_count,
            "attachment_reference_count": inventory.attachment_reference_count,
            "malformed_object_count": inventory.malformed_object_count,
            "unknown_field_count": inventory.unknown_field_count,
            "duplicate_object_count": stage_result.duplicate_object_count,
            "quarantine_count": len(stage_result.quarantined_objects),
            "material_loss_count": stage_result.mapping_report.material_loss_count,
            "mapping_report_reference": stage_result.mapping_report.mapping_report_id,
        },
        "privacy": _privacy_block(),
    }


def _complete(
    *,
    runner_commit: str,
    commit_checks: dict[str, bool],
    source_bytes: bytes,
    staged: Any,
    contract_offline: bool,
    network_confirmed: bool,
    reviewed_confirmed: bool,
) -> dict[str, object]:
    if not network_confirmed:
        raise RuntimeError("network-disabled confirmation is required")
    if not reviewed_confirmed:
        raise RuntimeError("review confirmation is required")

    started_at = _now()
    with tempfile.TemporaryDirectory(prefix="doll-imp059-private-") as raw:
        root = Path(raw)
        initialized = _initialize_workspace(root / "workspace")
        with state.open_state_repository(initialized.root) as repository:
            publisher = GenericImportPublisher(repository, staged.source_environment)
            before_preview = repository.status()
            preview = publisher.preview(
                staged.stage_result,
                source_bytes,
                preserve_source=True,
            )
            preview_side_effect_free = repository.status() == before_preview
            published = publisher.publish(
                preview,
                source_bytes,
                approved_plan_hash=preview.plan_hash,
                completed_at=_now(),
            )
            conversations = repository.list_conversations()
            events = tuple(
                event
                for conversation in conversations
                for event in repository.list_conversation_events(
                    conversation.conversation_id
                )
            )
            authority_count = _authority_count(repository)
            export_batch_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"imp059-private:{staged.inventory.source_root_hash}",
                )
            )
            generic = GenericExportBuilder().build(
                conversations,
                events,
                export_batch_id=export_batch_id,
                started_at=_now(),
                completed_at=_now(),
            )

        escape_path = root / "shutdown-escape.zip"
        with state.open_state_repository(initialized.root, read_only=True) as repository:
            escape = export_shutdown_escape_bundle(
                repository,
                escape_path,
                exported_at=_now(),
            )

        checks = {
            **commit_checks,
            "operator_confirmed_network_disabled": network_confirmed,
            "operator_confirmed_review_complete": reviewed_confirmed,
            "contract_is_offline": contract_offline,
            "preview_is_side_effect_free": preview_side_effect_free,
            "selected_history_published": (
                published.import_batch.status == "published"
                and len(conversations) == staged.inventory.selected_conversation_count
                and len(events) == staged.inventory.supported_message_count
            ),
            "exact_source_preserved": (
                published.source_snapshot.preservation_state == "managed_snapshot"
                and published.source_snapshot.source_root_hash
                == hashlib.sha256(source_bytes).hexdigest()
            ),
            "imported_content_remains_data_only": (
                authority_count == 0
                and all(event.origin_class == "imported_data" for event in events)
            ),
            "generic_export_available": generic.export_batch.status == "completed",
            "shutdown_escape_preserves_imported_history": (
                bool(escape.generic_conversation_export)
                and escape.recoverable_surfaces.get("conversations") is True
            ),
        }
        if not all(checks.values()):
            raise RuntimeError("private manual acceptance check failed")

        completed_at = _now()
        return {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "mode": "complete",
            "result": "pass",
            "started_at": started_at,
            "completed_at": completed_at,
            "evidence_level": "private-manual",
            "implementation_commit_sha": IMPLEMENTATION_COMMIT,
            "runner_commit_sha": runner_commit,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "operator-confirmed-disabled",
            "checks": checks,
            "real_machine_used": True,
            "private_source_used": True,
            "real_runtime_used": False,
            "model_execution_used": False,
            "model_download_used": False,
            "runtime_installation_used": False,
            "cloud_credentials_used": False,
            "external_network_request_used": False,
            "preferred_interface_required": False,
            "port014_foundation_complete": True,
            "chatgpt_history_gate_complete": False,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
            "evidence": {
                "source_environment_class": staged.source_environment.environment_class,
                "source_format": staged.source_environment.export_format,
                "source_format_version": staged.source_environment.export_version,
                "source_adapter_id": staged.stage_result.import_batch.adapter_id,
                "source_adapter_version": staged.stage_result.import_batch.adapter_version,
                "source_root_hash": staged.inventory.source_root_hash,
                "conversation_count": staged.inventory.conversation_count,
                "selected_conversation_count": staged.inventory.selected_conversation_count,
                "selected_message_count": staged.inventory.selected_message_count,
                "supported_message_count": staged.inventory.supported_message_count,
                "unsupported_message_count": staged.inventory.unsupported_message_count,
                "source_object_count": staged.inventory.source_object_count,
                "published_object_count": len(published.created_canonical_record_ids),
                "duplicate_object_count": staged.stage_result.duplicate_object_count,
                "quarantine_count": len(staged.stage_result.quarantined_objects),
                "material_loss_count": staged.stage_result.mapping_report.material_loss_count,
                "mapping_report_reference": (
                    staged.stage_result.mapping_report.mapping_report_id
                ),
                "generic_export_manifest_hash": generic.export_batch.manifest_hash,
                "shutdown_escape_sha256": escape.top_level_sha256,
                "runtime_mode": "private-manual",
            },
            "privacy": _privacy_block(),
            "limitations": [
                (
                    "The result proves only a bounded selected-history migration drill "
                    "from one caller-extracted conversations.json file."
                ),
                (
                    "ZIP ingestion, numbered-file aggregation, attachment-byte recovery, "
                    "account restoration, memory migration, GPT migration, settings migration, "
                    "file restoration, and target-specific round-trip fidelity remain outside "
                    "this result."
                ),
                "The complete Phase 6 gate and stable general anti-lock-in remain incomplete.",
            ],
        }


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        commit_checks = _verify_commit_binding(arguments.runner_commit)
        if not all(commit_checks.values()):
            raise RuntimeError("commit binding failed")
        stage = "private_input"
        source_bytes, selected = _read_private_inputs(
            arguments.source,
            arguments.selection_file,
        )
        adapter = ChatGPTExportSourceAdapter()
        contract_offline = adapter.contract.network_behavior == "none"
        stage = "source_adapter"
        staged = adapter.stage(
            source_bytes,
            source_environment_id=arguments.source_environment_id,
            selected_conversation_ids=selected,
            import_batch_id=arguments.import_batch_id,
            started_at=_now(),
            observed_at=arguments.observed_at,
        )
        if arguments.mode == "review":
            payload = _review_payload(
                runner_commit=arguments.runner_commit,
                commit_checks=commit_checks,
                staged=staged,
                contract_offline=contract_offline,
            )
        else:
            stage = "private_manual_completion"
            payload = _complete(
                runner_commit=arguments.runner_commit,
                commit_checks=commit_checks,
                source_bytes=source_bytes,
                staged=staged,
                contract_offline=contract_offline,
                network_confirmed=arguments.confirm_network_disabled,
                reviewed_confirmed=arguments.confirm_reviewed,
            )
        status = 0 if payload.get("result") in {"review-ready", "pass"} else 1
    except BaseException as exc:
        payload = {
            "test_id": TEST_ID,
            "result": "fail",
            "error_stage": stage,
            "error_class": type(exc).__name__,
            "implementation_commit_sha": IMPLEMENTATION_COMMIT,
            "runner_commit_sha": arguments.runner_commit,
            "chatgpt_history_gate_complete": False,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
        }
        status = 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
