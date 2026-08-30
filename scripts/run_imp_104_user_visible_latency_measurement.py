"""Run the bounded IMP-104 user-visible local-writing latency measurement."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import cast
from uuid import uuid4

from imp_064_local_writing_probe import (
    DRAFT_REQUEST,
    REVISE_REQUEST,
    REVISE_SOURCE,
    SUMMARIZE_REQUEST,
    SUMMARIZE_SOURCE,
    SYNTHETIC_MODEL,
    TARGET_SCOPE_KEY,
    DeterministicWritingTransport,
    ObservedWritingTransport,
    SocketDestinationGuard,
    _activate_binding,
    _context,
)

from doll import state, workspace
from doll.local_conversation import LocalConversationService
from doll.local_writing import LocalWritingWorkflowResult, LocalWritingWorkflowService, WritingMode
from doll.ollama_adapter import (
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaRuntimeAdapter,
    is_ollama_cloud_model,
    ollama_model_id,
)
from doll.runtime_adapter import LocalRuntimeBoundary, RuntimeAdapterRegistry
from doll.state import ConversationRecord

TEST_ID = "IMP-104-USER-VISIBLE-LOCAL-WRITING-LATENCY-MEASUREMENT"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
OPAQUE_MODEL_ID = re.compile(r"^ollama\.model\.[0-9a-f]{64}$")
WORKFLOW_ORDER = ("draft", "revise", "summarize")
TIMEOUT_SECONDS = 120.0


class Imp104MeasurementError(RuntimeError):
    """Raised when the bounded IMP-104 measurement cannot produce evidence."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--local-only-confirmed", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--ollama-port", type=int, default=11434)
    return parser.parse_args()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_diff_is_clean(*arguments: str) -> bool:
    completed = subprocess.run(
        ["git", "diff", "--quiet", "--ignore-submodules=none", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise Imp104MeasurementError("git tracked-state check failed")


def _require_clean_tracked_checkout() -> None:
    if not _git_diff_is_clean("--cached", "HEAD", "--"):
        raise Imp104MeasurementError("tracked index differs from HEAD")
    if not _git_diff_is_clean("--"):
        raise Imp104MeasurementError("tracked working tree differs from index")


def _validate_environment(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise Imp104MeasurementError("commit mismatch")
    _require_clean_tracked_checkout()
    if (
        isinstance(arguments.ollama_port, bool)
        or not isinstance(arguments.ollama_port, int)
        or not 1 <= arguments.ollama_port <= 65535
    ):
        raise Imp104MeasurementError("invalid Ollama port")
    machine = cast(str, arguments.evidence_level) == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().casefold() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
            or not isinstance(arguments.model, str)
            or not arguments.model
            or is_ollama_cloud_model(arguments.model)
        ):
            raise Imp104MeasurementError("real-machine evidence rejected")
    elif any(
        (
            arguments.offline_confirmed,
            arguments.local_only_confirmed,
            arguments.model,
        )
    ):
        raise Imp104MeasurementError("CI evidence cannot accept real-machine confirmations")
    return machine


def _measure(
    workflow: LocalWritingWorkflowService,
    *,
    mode: WritingMode,
    conversation_id: str,
    operation_id: str,
    request_text: str,
    source_text: str | None = None,
    parent_event_id: str | None = None,
) -> tuple[LocalWritingWorkflowResult, int]:
    started = time.perf_counter_ns()
    result = workflow.execute(
        mode=mode,
        conversation_id=conversation_id,
        scope_type="conversation",
        scope_key=TARGET_SCOPE_KEY,
        request_text=request_text,
        source_text=source_text,
        operation_id=operation_id,
        parent_event_id=parent_event_id,
        timeout_seconds=TIMEOUT_SECONDS,
    )
    duration = time.perf_counter_ns() - started
    if duration <= 0:
        raise Imp104MeasurementError("non-positive workflow duration")
    if result.outcome != "completed" or result.assistant_event_id is None:
        raise Imp104MeasurementError("local-writing workflow did not complete")
    return result, duration


def _observation(
    *,
    machine: bool,
    model_name: str,
    ollama_port: int,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="doll-imp104-") as temporary:
        root = Path(temporary)
        initialized = workspace.initialize_workspace(root / "workspace")
        with state.initialize_state_repository(initialized.root):
            pass

        endpoint = OllamaEndpoint(port=ollama_port)
        raw_transport = (
            LoopbackOllamaTransport(endpoint)
            if machine
            else DeterministicWritingTransport(endpoint=endpoint, model_name=model_name)
        )
        observed = ObservedWritingTransport(raw_transport)
        adapter = OllamaRuntimeAdapter(
            OllamaAdapterConfig(endpoint=endpoint, local_only_confirmed=True),
            transport=observed,
        )

        with SocketDestinationGuard(ollama_port) as sockets:
            with state.open_state_repository(initialized.root) as repository:
                conversation = ConversationRecord(
                    conversation_id=str(uuid4()),
                    title="IMP-104 bounded latency target",
                )
                repository.save_conversation(conversation)
                _activate_binding(
                    repository,
                    adapter,
                    model_name,
                    observed.runtime_version,
                )
                model_id = ollama_model_id(model_name)
                inventory = adapter.inventory(_context("imp104.inventory.identity"))
                selected = [item for item in inventory.models if item.model_id == model_id]
                if len(selected) != 1:
                    raise Imp104MeasurementError("selected model identity is unavailable")
                revision = selected[0].revision
                if not isinstance(revision, str) or not revision:
                    raise Imp104MeasurementError("selected model revision is unavailable")
                if OPAQUE_MODEL_ID.fullmatch(model_id) is None:
                    raise Imp104MeasurementError("selected model identity is not opaque")

                workflow = LocalWritingWorkflowService(
                    repository,
                    LocalConversationService(
                        repository,
                        LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
                    ),
                )
                draft, draft_ns = _measure(
                    workflow,
                    mode="draft",
                    conversation_id=conversation.conversation_id,
                    operation_id="imp104.writing.draft",
                    request_text=DRAFT_REQUEST,
                )
                revise, revise_ns = _measure(
                    workflow,
                    mode="revise",
                    conversation_id=conversation.conversation_id,
                    operation_id="imp104.writing.revise",
                    request_text=REVISE_REQUEST,
                    source_text=REVISE_SOURCE,
                    parent_event_id=draft.assistant_event_id,
                )
                summarize, summarize_ns = _measure(
                    workflow,
                    mode="summarize",
                    conversation_id=conversation.conversation_id,
                    operation_id="imp104.writing.summarize",
                    request_text=SUMMARIZE_REQUEST,
                    source_text=SUMMARIZE_SOURCE,
                    parent_event_id=revise.assistant_event_id,
                )
                results = (draft, revise, summarize)
                events = repository.list_conversation_events(conversation.conversation_id)

        runtime_version = observed.runtime_version
        if not isinstance(runtime_version, str) or not runtime_version:
            raise Imp104MeasurementError("runtime version is unavailable")
        durations = {
            "draft": draft_ns,
            "revise": revise_ns,
            "summarize": summarize_ns,
        }
        return {
            "runtime_version": runtime_version,
            "model": {
                "model_id": model_id,
                "revision": revision,
            },
            "workflow_order": list(WORKFLOW_ORDER),
            "completed_response_duration_ns": durations,
            "completed_workflow_count": sum(item.outcome == "completed" for item in results),
            "assistant_event_count": sum(item.assistant_event_id is not None for item in results),
            "canonical_event_count": len(events),
            "prompt_injection_finding_count": sum(
                item.prompt_injection_finding_count for item in results
            ),
            "secret_redaction_count": sum(item.secret_redaction_count for item in results),
            "runtime_request_count": observed.request_count,
            "allowed_loopback_socket_attempts": sockets.allowed_attempts,
            "rejected_socket_attempts": sockets.rejected_attempts,
        }


def _checks(observation: dict[str, object], *, machine: bool) -> dict[str, bool]:
    durations = observation.get("completed_response_duration_ns")
    model = observation.get("model")
    return {
        "measurement_scope_is_bounded_local_writing": True,
        "workflow_order_is_exact": observation.get("workflow_order") == list(WORKFLOW_ORDER),
        "three_workflows_completed": observation.get("completed_workflow_count") == 3,
        "three_assistant_events_created": observation.get("assistant_event_count") == 3,
        "canonical_event_count_is_nine": observation.get("canonical_event_count") == 9,
        "durations_are_positive": isinstance(durations, dict)
        and set(durations) == set(WORKFLOW_ORDER)
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in durations.values()
        ),
        "selected_model_identity_is_opaque": isinstance(model, dict)
        and isinstance(model.get("model_id"), str)
        and OPAQUE_MODEL_ID.fullmatch(cast(str, model["model_id"])) is not None,
        "runtime_requests_are_bounded": isinstance(observation.get("runtime_request_count"), int)
        and cast(int, observation["runtime_request_count"]) > 0,
        "no_rejected_socket_attempt": observation.get("rejected_socket_attempts") == 0,
        "ci_uses_no_socket": machine
        or observation.get("allowed_loopback_socket_attempts") == 0,
        "real_machine_uses_loopback": (not machine)
        or (
            isinstance(observation.get("allowed_loopback_socket_attempts"), int)
            and cast(int, observation["allowed_loopback_socket_attempts"]) > 0
        ),
    }


def _claims() -> dict[str, bool]:
    return {
        "final_user_visible_latency_requirement_defined": False,
        "first_token_latency_measured": False,
        "streaming_latency_measured": False,
        "cold_start_latency_measured": False,
        "cold_start_classified": False,
        "generation_throughput_requirement_defined": False,
        "supported_or_default_model_selected": False,
        "cross_machine_performance_supported": False,
        "full_lite_performance_thresholds_defined": False,
        "lite_performance_gate_complete": False,
        "accessibility_gate_complete": False,
        "release_candidate_soak_complete": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
    }


def _privacy() -> dict[str, bool]:
    return {
        "absolute_paths_in_report": False,
        "usernames_in_report": False,
        "hostnames_in_report": False,
        "native_model_names_in_report": False,
        "source_identifiers_in_report": False,
        "request_text_in_report": False,
        "source_text_in_report": False,
        "prompt_text_in_report": False,
        "response_text_in_report": False,
        "process_ids_in_report": False,
        "process_command_lines_in_report": False,
        "credentials_in_report": False,
        "secret_values_in_report": False,
        "workspace_identifiers_in_report": False,
        "urls_in_report": False,
        "email_addresses_in_report": False,
    }


def main() -> int:
    arguments = _arguments()
    try:
        machine = _validate_environment(arguments)
        model_name = cast(str, arguments.model) if machine else SYNTHETIC_MODEL
        observation = _observation(
            machine=machine,
            model_name=model_name,
            ollama_port=arguments.ollama_port,
        )
        checks = _checks(observation, machine=machine)
        if not all(checks.values()):
            raise Imp104MeasurementError("bounded latency measurement checks failed")
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "synthetic-no-network",
            "measurement_scope": "doll-local-writing-completed-response-latency",
            "timing_clock": "time.perf_counter_ns",
            "timing_boundary": "local-writing-execute-to-completed-result",
            "runtime_preflight_included_in_duration": False,
            "workspace_setup_included_in_duration": False,
            "binding_setup_included_in_duration": False,
            "loopback_runtime_request_used": machine,
            "external_network_request_used": False,
            "cloud_credentials_used": False,
            "automatic_model_download_used": False,
            "runtime_install_or_start_used": False,
            "synthetic_observations": not machine,
            "real_machine_measurement_collected": machine,
            "real_machine_measurement_accepted": False,
            "observation": observation,
            "checks": checks,
            "claims": _claims(),
            "privacy": _privacy(),
        }
    except BaseException as exc:
        payload = {
            "result": "fail",
            "error_class": type(exc).__name__,
            "message": str(exc),
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
