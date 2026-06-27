"""Run the integrated IMP-054 local-runtime continuity scenario."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import cast
from uuid import uuid4

from tests.project_continuity_support import create_project_continuity_fixture

import doll.backup as backup
import doll.restore as restore
import doll.state_package as state_package
from doll import state, workspace
from doll.local_conversation import LocalConversationService
from doll.memory import ConfirmedMemoryService
from doll.model_manifest import ModelManifestService
from doll.model_switch import ModelSwitchService
from doll.ollama_adapter import (
    OLLAMA_ADAPTER_ID,
    OLLAMA_ADAPTER_VERSION,
    OLLAMA_LOOPBACK_HOST,
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaRuntimeAdapter,
    OllamaTransport,
)
from doll.portability import PortabilityState, SourceEnvironmentRecord
from doll.runtime_adapter import (
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterFailure,
    RuntimeAdapterRegistry,
    RuntimeAdapterResponse,
    RuntimeGenerationRequest,
    RuntimeHealth,
    RuntimeInventorySnapshot,
    RuntimeModelInfo,
    RuntimeStreamEvent,
)
from doll.state import ConversationRecord
from doll.state_repository import StateRepository
from doll.streaming_conversation import LocalStreamingConversationService

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "imp_054_state_inspector.py"
PRIMARY_SYNTHETIC_MODEL = "doll-test-primary:latest"
FALLBACK_SYNTHETIC_MODEL = "doll-test-fallback:latest"
SWITCH_RESPONSE = "DOLL_SWITCH_OK"
SWITCH_INPUT = json.dumps(
    {
        "expected_response": SWITCH_RESPONSE,
        "purpose": "local_model_switch_smoke_test",
        "schema_version": 1,
    },
    sort_keys=True,
    separators=(",", ":"),
)
_ALLOWED_PATHS = frozenset({"/api/version", "/api/tags", "/api/generate"})


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ci", "real-machine"), required=True)
    parser.add_argument("--primary-model")
    parser.add_argument("--fallback-model")
    parser.add_argument("--ollama-port", type=int, default=11434)
    return parser.parse_args()


@dataclass(slots=True)
class DeterministicOllamaTransport:
    """In-memory Ollama transport for CI; it performs no socket operation."""

    endpoint: OllamaEndpoint = field(default_factory=OllamaEndpoint)
    primary_name: str = PRIMARY_SYNTHETIC_MODEL
    fallback_name: str = FALLBACK_SYNTHETIC_MODEL

    def _inventory(self) -> bytes:
        payload = {
            "models": [
                {
                    "name": self.primary_name,
                    "model": self.primary_name,
                    "digest": "1" * 64,
                },
                {
                    "name": self.fallback_name,
                    "model": self.fallback_name,
                    "digest": "2" * 64,
                },
            ]
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

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
            return OllamaHttpResponse(200, self._inventory())
        if method != "POST" or path != "/api/generate" or body is None:
            return OllamaHttpResponse(404, b"{}")
        request = json.loads(body)
        prompt = request.get("prompt")
        response = SWITCH_RESPONSE if prompt == SWITCH_INPUT else "DOLL_LOCAL_OK"
        payload = {
            "model": request.get("model"),
            "response": response,
            "done": True,
            "done_reason": "stop",
        }
        return OllamaHttpResponse(
            200,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        )

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del context, maximum_bytes, maximum_line_bytes
        if path != "/api/generate":
            raise RuntimeError("unexpected synthetic Ollama path")
        request = json.loads(body)
        model = request.get("model")
        for response, done in (("DOLL_", False), ("STREAM_OK", True)):
            payload: dict[str, object] = {
                "model": model,
                "response": response,
                "done": done,
            }
            if done:
                payload["done_reason"] = "stop"
            yield json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


@dataclass(slots=True)
class ObservedOllamaTransport:
    """Permit only the fixed loopback endpoint and accepted Ollama paths."""

    delegate: OllamaTransport
    endpoint: OllamaEndpoint = field(init=False)
    request_count: int = 0
    stream_count: int = 0
    rejected_request_count: int = 0
    runtime_version: str | None = None

    def __post_init__(self) -> None:
        self.endpoint = self.delegate.endpoint
        if self.endpoint.host != OLLAMA_LOOPBACK_HOST:
            raise RuntimeError("Ollama transport is not fixed to IPv4 loopback")

    def _require_path(self, path: str) -> None:
        if path not in _ALLOWED_PATHS:
            self.rejected_request_count += 1
            raise RuntimeError("undeclared Ollama API path")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        self._require_path(path)
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
        self._require_path(path)
        self.stream_count += 1
        return self.delegate.stream_ndjson(
            path,
            body=body,
            context=context,
            maximum_bytes=maximum_bytes,
            maximum_line_bytes=maximum_line_bytes,
        )


class SocketDestinationGuard:
    """Reject every current-process socket destination except one Ollama loopback port."""

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


@dataclass(slots=True)
class PostActivationFailureAdapter:
    """Delegate one real preflight, then force the post-activation rollback path."""

    delegate: OllamaRuntimeAdapter
    adapter_id: str = OLLAMA_ADAPTER_ID
    probe_calls: int = 0

    def declaration(self) -> RuntimeAdapterDeclaration:
        return self.delegate.declaration()

    def health(self) -> RuntimeHealth:
        return self.delegate.health()

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        return self.delegate.inventory(context)

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        if request.input_text == SWITCH_INPUT:
            self.probe_calls += 1
            if self.probe_calls == 2:
                raise RuntimeAdapterFailure("invalid_response")
        return self.delegate.generate(request, context)

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        return self.delegate.stream(request, context)


def _initialize_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _probe_model(boundary: LocalRuntimeBoundary, model_id: str, operation_id: str) -> bool:
    result = boundary.generate(
        OLLAMA_ADAPTER_ID,
        RuntimeGenerationRequest(
            operation_id=operation_id,
            model_id=model_id,
            input_text=SWITCH_INPUT,
            max_output_chars=64,
            timeout_seconds=60,
        ),
    )
    return result.outcome == "completed" and result.output_text == SWITCH_RESPONSE


def _select_models(
    boundary: LocalRuntimeBoundary,
    primary_name: str,
    fallback_name: str,
) -> tuple[RuntimeModelInfo, RuntimeModelInfo]:
    inventory = boundary.inventory(
        OLLAMA_ADAPTER_ID,
        operation_id="imp054.inventory",
        timeout_seconds=60,
    )
    if not inventory.succeeded:
        raise RuntimeError("Ollama inventory is unavailable")
    by_name = {item.display_name: item for item in inventory.models}
    primary = by_name.get(primary_name)
    fallback = by_name.get(fallback_name)
    if primary is None or fallback is None or primary.model_id == fallback.model_id:
        raise RuntimeError("two distinct requested local models are required")
    if primary.revision is None or fallback.revision is None:
        raise RuntimeError("selected local models require exact inventory digests")
    return primary, fallback


def _create_manifests(
    repository: StateRepository,
    boundary: LocalRuntimeBoundary,
    primary: RuntimeModelInfo,
    fallback: RuntimeModelInfo,
) -> dict[str, str]:
    manifests = ModelManifestService(repository)
    declaration = boundary.declaration(OLLAMA_ADAPTER_ID)
    if declaration is None:
        raise RuntimeError("Ollama declaration is unavailable")
    operations = tuple(sorted({*declaration.supported_operations, "health", "cancel"}))
    system_name = platform.system().lower() or "unknown"
    runtime = manifests.create_runtime(
        label="Local Ollama runtime",
        adapter_id=declaration.adapter_id,
        adapter_version=declaration.adapter_version,
        runtime_class=declaration.runtime_class,
        connection_kind=declaration.connection_kind,
        operations=operations,
        offline_capable=True,
        cloud_fallback=False,
        automatic_download=False,
        platforms=(system_name,),
        operation_id="imp054.runtime.create",
    )
    runtime = manifests.verify_runtime(
        runtime.runtime_manifest_id,
        expected_revision=runtime.revision,
        operation_id="imp054.runtime.verify",
    )

    created: dict[str, str] = {"runtime_manifest_id": runtime.runtime_manifest_id}
    for role, selected in (("primary", primary), ("fallback", fallback)):
        revision = cast(str, selected.revision)
        model = manifests.create_model(
            runtime_manifest_id=runtime.runtime_manifest_id,
            runtime_private_locator=selected.model_id,
            display_name=f"{role.title()} local model",
            exact_revision=revision,
            checksums={"sha256": revision.removeprefix("sha256-")},
            license_id="local-user-confirmed",
            model_format="ollama",
            capabilities=selected.features,
            platforms=(system_name,),
            operation_id=f"imp054.{role}.model.create",
        )
        model = manifests.review_model_license(
            model.model_manifest_id,
            expected_revision=model.revision,
            review_state="reviewed_compatible",
            operation_id=f"imp054.{role}.model.license",
        )
        model = manifests.verify_model(
            model.model_manifest_id,
            expected_revision=model.revision,
            operation_id=f"imp054.{role}.model.verify",
        )
        binding = manifests.create_binding(
            scope_type="conversation",
            scope_key="imp054",
            runtime_manifest_id=runtime.runtime_manifest_id,
            model_manifest_id=model.model_manifest_id,
            operation_id=f"imp054.{role}.binding.create",
        )
        if not _probe_model(
            boundary,
            selected.model_id,
            f"imp054.{role}.initial-probe",
        ):
            raise RuntimeError("selected local model failed the exact smoke response")
        binding = manifests.set_smoke_test(
            binding.binding_id,
            expected_revision=binding.revision,
            status="passed",
            operation_id=f"imp054.{role}.binding.smoke",
        )
        if role == "primary":
            binding = manifests.activate_binding(
                binding.binding_id,
                expected_revision=binding.revision,
                operation_id="imp054.primary.binding.activate",
            )
        else:
            binding = manifests.set_fallback(
                binding.binding_id,
                expected_revision=binding.revision,
                priority=10,
                operation_id="imp054.fallback.binding.configure",
            )
        created[f"{role}_model_manifest_id"] = model.model_manifest_id
        created[f"{role}_binding_id"] = binding.binding_id
    return created


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
        raise RuntimeError("fresh runtime-continuity inspection failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("fresh inspection checks are invalid")
    if not all(isinstance(key, str) and isinstance(value, int) for key, value in counts.items()):
        raise RuntimeError("fresh inspection counts are invalid")
    return cast(dict[str, bool], checks), cast(dict[str, int], counts)


def _hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def run(
    root: Path,
    *,
    mode: str,
    primary_name: str,
    fallback_name: str,
    ollama_port: int,
) -> tuple[dict[str, bool], dict[str, object]]:
    endpoint = OllamaEndpoint(port=ollama_port)
    raw_transport: OllamaTransport = (
        DeterministicOllamaTransport(
            endpoint=endpoint,
            primary_name=primary_name,
            fallback_name=fallback_name,
        )
        if mode == "ci"
        else LoopbackOllamaTransport(endpoint)
    )
    observed_transport = ObservedOllamaTransport(raw_transport)
    adapter = OllamaRuntimeAdapter(
        OllamaAdapterConfig(endpoint=endpoint, local_only_confirmed=True),
        transport=observed_transport,
    )
    boundary = LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,)))
    source = _initialize_workspace(root / "source")

    with SocketDestinationGuard(ollama_port) as socket_guard:
        health = boundary.health(OLLAMA_ADAPTER_ID)
        if health.state != "ready":
            raise RuntimeError("local Ollama runtime is not ready")
        primary, fallback = _select_models(boundary, primary_name, fallback_name)

        conversation_id = str(uuid4())
        environment_id = str(uuid4())
        with state.open_state_repository(source.root) as repository:
            fixture = create_project_continuity_fixture(repository, include_secret=False)
            memory = ConfirmedMemoryService(repository).create(
                subject="Local runtime continuity",
                content="Canonical memory remains independent of the selected local model.",
                operation_id="imp054.memory.create",
            )
            environment = PortabilityState(repository).save_source_environment(
                SourceEnvironmentRecord(
                    environment_id=environment_id,
                    environment_class="local-ai-runtime",
                    application_id="doll-runtime-drill",
                    runtime_id="ollama-local",
                    observed_at="2026-06-27T00:00:00Z",
                ),
                provenance="user-created",
            )
            repository.save_conversation(
                ConversationRecord(
                    conversation_id=conversation_id,
                    title="IMP-054 local runtime continuity",
                )
            )
            project_revision = repository.get_record(fixture.project_id).revision
            environment_revision = repository.get_record(environment.environment_id).revision
            identifiers = _create_manifests(repository, boundary, primary, fallback)

            non_streaming = LocalConversationService(repository, boundary)
            first = non_streaming.execute_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp054",
                user_text="Reply with a brief plain-text acknowledgement.",
                operation_id="imp054.turn.primary.nonstream",
            )
            streaming = LocalStreamingConversationService(repository, boundary)
            second = streaming.execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp054",
                user_text="Reply briefly through the streaming path.",
                operation_id="imp054.turn.primary.stream",
            )
            switch = ModelSwitchService(repository, boundary).switch_to_fallback(
                scope_type="conversation",
                scope_key="imp054",
                target_binding_id=identifiers["fallback_binding_id"],
                operation_id="imp054.switch.to-fallback",
            )
            third = non_streaming.execute_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp054",
                user_text="Confirm the explicitly selected fallback model is usable.",
                operation_id="imp054.turn.fallback.nonstream",
            )

            rollback_adapter = PostActivationFailureAdapter(adapter)
            rollback_boundary = LocalRuntimeBoundary(RuntimeAdapterRegistry((rollback_adapter,)))
            rollback = ModelSwitchService(repository, rollback_boundary).switch_binding(
                scope_type="conversation",
                scope_key="imp054",
                target_binding_id=identifiers["primary_binding_id"],
                operation_id="imp054.switch.forced-rollback",
            )
            rollback_probe_calls = rollback_adapter.probe_calls
            fourth = LocalConversationService(repository, boundary).execute_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp054",
                user_text="Confirm conversation continues after exact rollback.",
                operation_id="imp054.turn.after-rollback",
            )

            descriptor = {
                "memory_id": memory.record_id,
                "memory_revision": memory.revision,
                "project_id": fixture.project_id,
                "project_revision": project_revision,
                "source_environment_id": environment.environment_id,
                "source_environment_revision": environment_revision,
                "conversation_id": conversation_id,
                "expected_event_count": 12,
                "scope_type": "conversation",
                "scope_key": "imp054",
                **identifiers,
            }
            descriptor_path = root / "descriptor.json"
            descriptor_path.write_text(
                json.dumps(descriptor, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            unrelated_preserved = (
                ConfirmedMemoryService(repository).get(memory.record_id).revision == memory.revision
                and repository.get_record(fixture.project_id).revision == project_revision
                and repository.get_record(environment.environment_id).revision
                == environment_revision
            )
            events = repository.list_conversation_events(conversation_id)

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
        stream_count = observed_transport.stream_count
        rejected_request_count = observed_transport.rejected_request_count
        runtime_version = observed_transport.runtime_version or "unknown"
        allowed_socket_attempts = socket_guard.allowed_attempts
        rejected_socket_attempts = socket_guard.rejected_attempts

    del rollback_boundary, rollback_adapter, streaming, non_streaming, boundary, adapter
    gc.collect()

    source_checks, source_counts = _fresh_inspection(source.root, descriptor_path)
    package_checks, package_counts = _fresh_inspection(package_target, descriptor_path)
    backup_checks, backup_counts = _fresh_inspection(backup_target, descriptor_path)

    turn_results = (first, second.turn, third, fourth)
    checks = {
        "ollama_health_ready": health.state == "ready",
        "two_exact_local_models_selected": (
            primary.model_id != fallback.model_id
            and primary.revision is not None
            and fallback.revision is not None
        ),
        "primary_nonstream_completed": first.outcome == "completed",
        "primary_stream_completed": (
            second.turn.outcome == "completed"
            and any(event.kind == "delta" for event in second.display_events)
        ),
        "explicit_fallback_switch_completed": (
            switch.outcome == "switched"
            and switch.active_binding_id == identifiers["fallback_binding_id"]
            and switch.fallback_selected is True
        ),
        "fallback_conversation_completed": third.outcome == "completed",
        "forced_post_activation_failure_rolled_back": (
            rollback.outcome == "rolled_back"
            and rollback.active_binding_id == identifiers["fallback_binding_id"]
            and rollback.previous_binding_id == identifiers["fallback_binding_id"]
            and rollback_probe_calls == 2
        ),
        "post_rollback_conversation_completed": fourth.outcome == "completed",
        "all_canonical_turns_completed": all(item.outcome == "completed" for item in turn_results),
        "canonical_event_count": len(events) == 12,
        "unrelated_state_revisions_preserved": unrelated_preserved,
        "state_package_v2_exported": package_inspection.package_format_version == 2,
        "state_package_runtime_records_present": all(
            package_inspection.record_counts.get(record_type) == expected
            for record_type, expected in {
                "runtime_manifest": 1,
                "model_manifest": 2,
                "model_binding": 2,
            }.items()
        ),
        "state_backup_restored": restore_result.fresh_process_validated is True,
        "source_fresh_process_without_adapter": all(source_checks.values()),
        "package_fresh_process_without_adapter": all(package_checks.values()),
        "backup_fresh_process_without_adapter": all(backup_checks.values()),
        "fresh_process_counts_match": source_counts == package_counts == backup_counts,
        "only_declared_ollama_paths_used": rejected_request_count == 0,
        "no_non_loopback_socket_attempt": rejected_socket_attempts == 0,
        "real_mode_used_loopback_socket": mode != "real-machine" or allowed_socket_attempts > 0,
        "ci_mode_used_no_socket": mode != "ci" or allowed_socket_attempts == 0,
        "stream_transport_exercised": stream_count >= 1,
        "runtime_requests_exercised": request_count >= 1,
        "adapter_declaration_unchanged": (
            OLLAMA_ADAPTER_VERSION == "1.0.0" and OLLAMA_ADAPTER_ID == "ollama.local"
        ),
    }
    evidence: dict[str, object] = {
        "runtime_adapter_id": OLLAMA_ADAPTER_ID,
        "runtime_adapter_version": OLLAMA_ADAPTER_VERSION,
        "runtime_version": runtime_version,
        "runtime_mode": "synthetic" if mode == "ci" else "real-local",
        "model_count": 2,
        "model_revision_hashes": sorted(
            (_hash(cast(str, primary.revision)), _hash(cast(str, fallback.revision)))
        ),
        "canonical_turn_count": len(turn_results),
        "canonical_event_count": len(events),
        "package_format_version": package_inspection.package_format_version,
        "backup_fresh_process_validated": restore_result.fresh_process_validated,
        "fresh_inspection_count": 3,
        "fresh_record_counts": source_counts,
        "ollama_request_count": request_count,
        "ollama_stream_count": stream_count,
        "allowed_loopback_socket_attempts": allowed_socket_attempts,
        "rejected_socket_attempts": rejected_socket_attempts,
        "active_binding_hash": _hash(identifiers["fallback_binding_id"]),
    }
    return checks, evidence


def main() -> int:
    arguments = _arguments()
    try:
        primary_name = arguments.primary_model or PRIMARY_SYNTHETIC_MODEL
        fallback_name = arguments.fallback_model or FALLBACK_SYNTHETIC_MODEL
        if arguments.mode == "real-machine" and (
            not arguments.primary_model or not arguments.fallback_model
        ):
            raise RuntimeError("real-machine mode requires two explicit model names")
        with tempfile.TemporaryDirectory(prefix="doll-imp054-") as directory:
            checks, evidence = run(
                Path(directory),
                mode=arguments.mode,
                primary_name=primary_name,
                fallback_name=fallback_name,
                ollama_port=arguments.ollama_port,
            )
        if not all(checks.values()):
            raise RuntimeError("local runtime continuity probe failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "evidence": evidence,
        }
    except BaseException as exc:
        payload = {"result": "fail", "error_class": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
