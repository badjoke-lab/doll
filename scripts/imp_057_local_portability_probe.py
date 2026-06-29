"""Run the integrated IMP-057 local-portability migration scenario."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import cast
from uuid import NAMESPACE_URL, uuid5

import doll.backup as backup
import doll.restore as restore
import doll.state_package as state_package
from doll import state, workspace
from doll.generic_export import GenericExportBuilder
from doll.generic_import_publication import (
    GenericImportPublicationError,
    GenericImportPublisher,
)
from doll.ollama_adapter import (
    OLLAMA_LOOPBACK_HOST,
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaTransport,
    ollama_model_id,
)
from doll.ollama_chat_capture import (
    OllamaChatCaptureRequest,
    OllamaChatCaptureService,
)
from doll.ollama_session_import import OllamaSessionSourceAdapter
from doll.runtime_adapter import (
    RuntimeAdapterContext,
    RuntimeCancellationToken,
)

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "imp_057_state_inspector.py"
SYNTHETIC_MODEL = "doll-test-portability:latest"
SYNTHETIC_RESPONSE = "DOLL_PORTABLE_OK"
ENVIRONMENT_ID = "57000000-0000-4000-8000-000000000001"
CONVERSATION_SOURCE_ID = "imp057-conversation"
USER_SOURCE_ID = "imp057-user"
ASSISTANT_SOURCE_ID = "imp057-assistant"
_FIRST_BATCH_ID = "57000000-0000-4000-8000-000000000002"
_SECOND_BATCH_ID = "57000000-0000-4000-8000-000000000003"
_CHANGED_BATCH_ID = "57000000-0000-4000-8000-000000000004"
_ALLOWED_PATHS = frozenset({"/api/tags", "/api/version", "/api/chat"})
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


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ci", "real-machine"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--ollama-port", type=int, default=11434)
    return parser.parse_args()


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class DeterministicOllamaTransport:
    """In-memory Ollama transport for CI; it performs no socket operation."""

    endpoint: OllamaEndpoint = field(default_factory=OllamaEndpoint)
    model_name: str = SYNTHETIC_MODEL

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        del context, maximum_bytes
        if method == "GET" and path == "/api/version" and body is None:
            return OllamaHttpResponse(200, b'{"version":"0.0.0-test"}')
        if method == "GET" and path == "/api/tags" and body is None:
            payload = {
                "models": [
                    {
                        "name": self.model_name,
                        "model": self.model_name,
                        "digest": "5" * 64,
                    }
                ]
            }
            return OllamaHttpResponse(
                200,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            )
        if method == "POST" and path == "/api/chat" and body is not None:
            request = json.loads(body)
            if request.get("model") != self.model_name or request.get("stream") is not False:
                return OllamaHttpResponse(400, b"{}")
            payload = {
                "model": self.model_name,
                "created_at": "2026-06-29T03:00:01Z",
                "message": {"role": "assistant", "content": SYNTHETIC_RESPONSE},
                "done": True,
                "done_reason": "stop",
            }
            return OllamaHttpResponse(
                200,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            )
        return OllamaHttpResponse(404, b"{}")

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del path, body, context, maximum_bytes, maximum_line_bytes
        raise RuntimeError("streaming is outside IMP-057")


@dataclass(slots=True)
class ObservedOllamaTransport:
    """Permit only the fixed loopback endpoint and IMP-057 Ollama paths."""

    delegate: OllamaTransport
    endpoint: OllamaEndpoint = field(init=False)
    request_count: int = 0
    rejected_request_count: int = 0
    runtime_version: str | None = None

    def __post_init__(self) -> None:
        self.endpoint = self.delegate.endpoint
        if self.endpoint.host != OLLAMA_LOOPBACK_HOST:
            raise RuntimeError("Ollama transport is not fixed to IPv4 loopback")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        if path not in _ALLOWED_PATHS:
            self.rejected_request_count += 1
            raise RuntimeError("undeclared Ollama API path")
        self.request_count += 1
        response = self.delegate.request_json(
            method,
            path,
            body=body,
            context=context,
            maximum_bytes=maximum_bytes,
        )
        if path == "/api/version" and response.status_code == 200:
            try:
                document = json.loads(response.body)
                version = document.get("version")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                version = None
            if isinstance(version, str) and len(version) <= 128:
                self.runtime_version = version
        return response

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del path, body, context, maximum_bytes, maximum_line_bytes
        self.rejected_request_count += 1
        raise RuntimeError("streaming is outside IMP-057")


class SocketDestinationGuard:
    """Reject every socket destination except one declared Ollama loopback port."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.allowed_attempts = 0
        self.rejected_attempts = 0
        self._connect: Callable[..., object] | None = None
        self._connect_ex: Callable[..., int] | None = None

    def __enter__(self) -> SocketDestinationGuard:
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex
        guard = self

        def guarded_connect(sock: socket.socket, address: object) -> object:
            if not guard._allowed(sock, address):
                guard.rejected_attempts += 1
                raise OSError("non-loopback socket destination rejected")
            guard.allowed_attempts += 1
            if guard._connect is None:
                raise RuntimeError("socket guard is not initialized")
            return guard._connect(sock, address)

        def guarded_connect_ex(sock: socket.socket, address: object) -> int:
            if not guard._allowed(sock, address):
                guard.rejected_attempts += 1
                return 13
            guard.allowed_attempts += 1
            if guard._connect_ex is None:
                raise RuntimeError("socket guard is not initialized")
            return guard._connect_ex(sock, address)

        socket.socket.connect = guarded_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        if self._connect is not None:
            socket.socket.connect = self._connect  # type: ignore[method-assign]
        if self._connect_ex is not None:
            socket.socket.connect_ex = self._connect_ex  # type: ignore[method-assign]

    def _allowed(self, sock: socket.socket, address: object) -> bool:
        return (
            sock.family == socket.AF_INET
            and isinstance(address, tuple)
            and len(address) >= 2
            and address[0] == OLLAMA_LOOPBACK_HOST
            and address[1] == self.port
        )


def _initialize_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _context(operation_id: str) -> RuntimeAdapterContext:
    return RuntimeAdapterContext(
        operation_id=operation_id,
        deadline_monotonic=time.monotonic() + 120,
        cancellation=RuntimeCancellationToken(),
    )


def _changed_source(source_bytes: bytes) -> bytes:
    document = json.loads(source_bytes)
    conversations = document.get("conversations")
    if not isinstance(conversations, list) or len(conversations) != 1:
        raise RuntimeError("captured source shape is invalid")
    conversation = conversations[0]
    if not isinstance(conversation, dict):
        raise RuntimeError("captured conversation shape is invalid")
    messages = conversation.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise RuntimeError("captured message shape is invalid")
    message = messages[0]
    if not isinstance(message, dict):
        raise RuntimeError("captured user message shape is invalid")
    message["content"] = "Synthetic changed-source conflict fixture."
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _record_counts(repository: state.StateRepository) -> dict[str, int]:
    rows = repository.connection.execute(
        "SELECT record_type, COUNT(*) FROM records GROUP BY record_type ORDER BY record_type"
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _authority_count(repository: state.StateRepository) -> int:
    placeholders = ",".join("?" for _ in _AUTHORITY_TYPES)
    row = repository.connection.execute(
        f"SELECT COUNT(*) FROM records WHERE record_type IN ({placeholders})",
        _AUTHORITY_TYPES,
    ).fetchone()
    if row is None:
        raise RuntimeError("authority count query failed")
    return int(row[0])


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fresh_inspection(
    workspace_root: Path,
    descriptor_path: Path,
) -> tuple[dict[str, bool], dict[str, int]]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    result = subprocess.run(
        [sys.executable, str(INSPECTOR), str(workspace_root), str(descriptor_path)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    checks = payload.get("checks")
    counts = payload.get("counts")
    if (
        result.returncode
        or payload.get("result") != "pass"
        or not isinstance(checks, dict)
        or not isinstance(counts, dict)
    ):
        raise RuntimeError("fresh local-portability inspection failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("fresh inspection checks are invalid")
    if not all(isinstance(key, str) and isinstance(value, int) for key, value in counts.items()):
        raise RuntimeError("fresh inspection counts are invalid")
    return cast(dict[str, bool], checks), cast(dict[str, int], counts)


def _hash_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def run(
    root: Path,
    *,
    mode: str,
    model_name: str,
    ollama_port: int,
) -> tuple[dict[str, bool], dict[str, object]]:
    endpoint = OllamaEndpoint(port=ollama_port)
    raw_transport: OllamaTransport = (
        DeterministicOllamaTransport(endpoint=endpoint, model_name=model_name)
        if mode == "ci"
        else LoopbackOllamaTransport(endpoint)
    )
    observed_transport = ObservedOllamaTransport(raw_transport)
    capture = OllamaChatCaptureService(
        OllamaAdapterConfig(endpoint=endpoint, local_only_confirmed=True),
        transport=observed_transport,
    )
    source = _initialize_workspace(root / "source")
    now = datetime(2026, 6, 29, 3, 0, tzinfo=UTC) if mode == "ci" else datetime.now(UTC)
    user_at = _timestamp(now)
    exported_at = _timestamp(now + timedelta(seconds=2))
    completed_at = _timestamp(now + timedelta(seconds=3))
    model_id = ollama_model_id(model_name)

    with SocketDestinationGuard(ollama_port) as socket_guard:
        captured = capture.capture(
            OllamaChatCaptureRequest(
                model_id=model_id,
                source_environment_id=ENVIRONMENT_ID,
                conversation_id=CONVERSATION_SOURCE_ID,
                user_message_id=USER_SOURCE_ID,
                assistant_message_id=ASSISTANT_SOURCE_ID,
                user_text="Return a short plain-text acknowledgement for a portability drill.",
                user_created_at=user_at,
                exported_at=exported_at,
                title="IMP-057 synthetic local portability drill",
                conversation_created_at=user_at,
                max_output_chars=4096,
            ),
            _context("imp057.capture"),
        )
        adapter = OllamaSessionSourceAdapter()
        first_stage = adapter.stage(
            captured.bundle_bytes,
            import_batch_id=_FIRST_BATCH_ID,
            started_at=exported_at,
        )

        with state.open_state_repository(source.root) as repository:
            publisher = GenericImportPublisher(repository, first_stage.source_environment)
            before_preview = repository.status()
            first_preview = publisher.preview(
                first_stage.stage_result,
                captured.bundle_bytes,
                preserve_source=True,
            )
            preview_side_effect_free = repository.status() == before_preview
            first_result = publisher.publish(
                first_preview,
                captured.bundle_bytes,
                approved_plan_hash=first_preview.plan_hash,
                completed_at=completed_at,
            )
            conversations = repository.list_conversations()
            if len(conversations) != 1:
                raise RuntimeError("captured conversation publication failed")
            conversation = conversations[0]
            events = repository.list_conversation_events(conversation.conversation_id)
            authority_count = _authority_count(repository)

            second_stage = adapter.stage(
                captured.bundle_bytes,
                import_batch_id=_SECOND_BATCH_ID,
                started_at=_timestamp(now + timedelta(seconds=4)),
            )
            second_preview = publisher.preview(
                second_stage.stage_result,
                captured.bundle_bytes,
                preserve_source=False,
            )
            second_result = publisher.publish(
                second_preview,
                captured.bundle_bytes,
                approved_plan_hash=second_preview.plan_hash,
                completed_at=_timestamp(now + timedelta(seconds=5)),
            )

            changed_bytes = _changed_source(captured.bundle_bytes)
            changed_stage = adapter.stage(
                changed_bytes,
                import_batch_id=_CHANGED_BATCH_ID,
                started_at=_timestamp(now + timedelta(seconds=6)),
            )
            changed_preview = publisher.preview(
                changed_stage.stage_result,
                changed_bytes,
                preserve_source=False,
            )
            changed_publish_blocked = False
            try:
                publisher.publish(
                    changed_preview,
                    changed_bytes,
                    approved_plan_hash=changed_preview.plan_hash,
                    completed_at=_timestamp(now + timedelta(seconds=7)),
                )
            except GenericImportPublicationError:
                changed_publish_blocked = True

            export_batch_id = str(uuid5(NAMESPACE_URL, captured.source_root_hash))
            builder = GenericExportBuilder()
            generic_bundle = builder.build(
                conversations,
                events,
                export_batch_id=export_batch_id,
                started_at=_timestamp(now + timedelta(seconds=8)),
                completed_at=_timestamp(now + timedelta(seconds=9)),
            )
            managed_export = builder.publish(
                generic_bundle,
                artifacts_root=source.root / "artifacts",
                managed_prefix=f"exports/{export_batch_id}",
            )
            source_counts_before_transfer = _record_counts(repository)
            descriptor = {
                "conversation_id": conversation.conversation_id,
                "expected_event_count": len(events),
                "source_environment_id": ENVIRONMENT_ID,
                "snapshot_record_id": first_result.source_snapshot.snapshot_record_id,
                "source_root_hash": captured.source_root_hash,
                "export_batch_id": export_batch_id,
                "generic_manifest_hash": generic_bundle.export_batch.manifest_hash,
                "generic_export_prefix": managed_export.managed_prefix,
            }

        package_path = root / "state-package.zip"
        with state.open_state_repository(source.root, read_only=True) as repository:
            package_inspection = state_package.export_state_package(repository, package_path)
        package_target = root / "package-target"
        state_package.import_state_package(package_path, package_target)

        backup_path = root / "state-backup.zip"
        backup.create_state_backup(source.root, backup_path)
        backup_target = root / "backup-target"
        restore_result = restore.restore_state_backup(backup_path, backup_target)

        request_count = observed_transport.request_count
        rejected_request_count = observed_transport.rejected_request_count
        runtime_version = observed_transport.runtime_version or "unknown"
        allowed_socket_attempts = socket_guard.allowed_attempts
        rejected_socket_attempts = socket_guard.rejected_attempts

    descriptor_path = root / "descriptor.json"
    descriptor_path.write_text(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    del capture, observed_transport, raw_transport, adapter, publisher
    gc.collect()

    source_checks, source_counts = _fresh_inspection(source.root, descriptor_path)
    package_checks, package_counts = _fresh_inspection(package_target, descriptor_path)
    backup_checks, backup_counts = _fresh_inspection(backup_target, descriptor_path)

    checks = {
        "capture_bundle_valid": (
            captured.conversation_count == 1
            and captured.message_count == 2
            and captured.source_root_hash == first_stage.inventory.source_root_hash
        ),
        "preview_side_effect_free": preview_side_effect_free,
        "reviewed_import_published": (
            first_result.import_batch.status == "published"
            and len(first_result.created_canonical_record_ids) == 3
            and len(events) == 2
        ),
        "source_preserved_with_exact_hash": (
            first_result.source_snapshot.preservation_state == "managed_snapshot"
            and first_result.source_snapshot.source_root_hash == captured.source_root_hash
        ),
        "imported_events_remain_data_only": (
            all(event.origin_class == "imported_data" for event in events) and authority_count == 0
        ),
        "unchanged_reimport_idempotent": (
            second_result.created_canonical_record_ids == ()
            and len(second_result.reused_canonical_record_ids) == 3
        ),
        "changed_source_conflict_blocks_overwrite": (
            changed_publish_blocked
            and {item.reason for item in changed_preview.conflicts} == {"changed-source-object"}
        ),
        "generic_export_completed": (
            generic_bundle.export_batch.status == "completed"
            and generic_bundle.export_batch.exported_object_count == 3
            and len(managed_export.files) == 5
        ),
        "state_package_v2_exported": package_inspection.package_format_version == 2,
        "state_backup_restored": restore_result.fresh_process_validated is True,
        "capture_component_removed_before_inspection": True,
        "source_fresh_process_alternate_retrieval": all(source_checks.values()),
        "package_fresh_process_alternate_retrieval": all(package_checks.values()),
        "backup_fresh_process_alternate_retrieval": all(backup_checks.values()),
        "fresh_process_record_counts_match": (
            source_counts == package_counts == backup_counts == source_counts_before_transfer
        ),
        "only_declared_ollama_paths_used": rejected_request_count == 0,
        "no_non_loopback_socket_attempt": rejected_socket_attempts == 0,
        "real_mode_used_loopback_socket": mode != "real-machine" or allowed_socket_attempts > 0,
        "ci_mode_used_no_socket": mode != "ci" or allowed_socket_attempts == 0,
        "runtime_requests_exercised": request_count == 3,
    }
    evidence: dict[str, object] = {
        "source_environment_class": first_stage.source_environment.environment_class,
        "source_format": first_stage.source_environment.export_format,
        "source_format_version": first_stage.source_environment.export_version,
        "source_adapter_id": "ollama-api-session",
        "source_adapter_version": "1.0.0",
        "capture_component_id": "ollama-chat-capture",
        "alternate_component_id": "doll-generic-export",
        "runtime_mode": "synthetic" if mode == "ci" else "real-local",
        "runtime_version": runtime_version,
        "model_id_hash": _hash_text(model_id),
        "source_root_hash": captured.source_root_hash,
        "source_object_counts": {
            "conversation": 1,
            "conversation_event": 2,
            "total": 3,
        },
        "published_object_counts": {
            "conversation": 1,
            "conversation_event": 2,
            "total": 3,
        },
        "duplicate_counts": {"unchanged_reimport_canonical_duplicates": 0},
        "quarantine_counts": {"captured_source": len(first_stage.stage_result.quarantined_objects)},
        "loss_counts_by_severity": {
            "material": first_stage.stage_result.mapping_report.material_loss_count
        },
        "mapping_report_reference": first_stage.stage_result.mapping_report.mapping_report_id,
        "generic_export_manifest_hash": generic_bundle.export_batch.manifest_hash,
        "state_package_sha256": _file_hash(package_path),
        "backup_sha256": _file_hash(backup_path),
        "fresh_record_counts": source_counts,
        "ollama_request_count": request_count,
        "allowed_loopback_socket_attempts": allowed_socket_attempts,
        "rejected_socket_attempts": rejected_socket_attempts,
    }
    return checks, evidence


def main() -> int:
    arguments = _arguments()
    try:
        model_name = arguments.model or SYNTHETIC_MODEL
        if arguments.mode == "real-machine" and not arguments.model:
            raise RuntimeError("real-machine mode requires one explicit model name")
        with tempfile.TemporaryDirectory(prefix="doll-imp057-") as directory:
            checks, evidence = run(
                Path(directory),
                mode=arguments.mode,
                model_name=model_name,
                ollama_port=arguments.ollama_port,
            )
        if not all(checks.values()):
            raise RuntimeError("local-portability migration probe failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "evidence": evidence,
        }
    except BaseException as exc:
        payload = {
            "result": "fail",
            "error_stage": "local_portability_probe",
            "error_class": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
