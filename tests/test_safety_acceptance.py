from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state

SCRIPT = Path("scripts/run_imp_023_safety_acceptance.py")


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_023_ci_evidence_preserves_accepted_machine_gate() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_id"] == "IMP-023-SAFETY-ACCEPTANCE"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "no-network-path-in-probe"
    assert payload["security_test_count"] == 23
    assert payload["executable_security_test_count"] == 22
    assert payload["not_applicable_security_test_ids"] == ["SEC-007"]
    assert payload["primary_intel_mac_gate"] == "pass"
    assert payload["phase3_gate_complete"] is True
    assert payload["model_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["live_side_effect_used"] is False
    assert payload["checks"]["stored_machine_evidence_valid"] is True
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())


def test_imp_023_failure_report_is_bounded_and_secret_safe() -> None:
    result = _run(
        "--commit-sha",
        "0123456789abcdef0123456789abcdef01234567",
        "--evidence-level",
        "ci",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "commit_sha",
        "completed_at",
        "error_class",
        "error_stage",
        "result",
        "test_id",
    }
    assert payload["result"] == "fail"
    assert payload["error_class"] == "RuntimeError"
    assert payload["error_stage"] == "environment"
    assert "path" not in result.stdout.lower()
    assert "secret" not in result.stdout.lower()


def test_canonical_conversation_contract_normalizes_source_identity() -> None:
    conversation = state.ConversationRecord(
        conversation_id=str(uuid4()),
        title="  Portable conversation  ",
        source_environment_id="local-app:alpha",
        source_conversation_id="conversation-42",
    )

    assert conversation.title == "Portable conversation"
    assert conversation.canonical_metadata() == {
        "source_environment_id": "local-app:alpha",
        "source_conversation_id": "conversation-42",
    }


def test_canonical_event_contract_preserves_graph_and_environment_fields() -> None:
    parent_id = str(uuid4())
    event = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=str(uuid4()),
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        parent_event_ids=(parent_id,),
        sequence_hint=8,
        content_reference="artifact:message-8",
        occurred_at="2026-06-23T10:00:00Z",
        provider_id="provider-a",
        application_id="application-b",
        interface_id="interface-c",
        model_manifest_id="model-d",
        runtime_adapter_id="runtime-e",
        extensions={"Vendor.Trace": "trace-1"},
    )

    metadata = event.canonical_metadata()
    assert metadata["parent_event_ids"] == [parent_id]
    assert metadata["provider_id"] == "provider-a"
    assert metadata["application_id"] == "application-b"
    assert metadata["interface_id"] == "interface-c"
    assert metadata["model_manifest_id"] == "model-d"
    assert metadata["runtime_adapter_id"] == "runtime-e"
    assert metadata["extensions"] == {"vendor.trace": "trace-1"}


def test_canonical_event_contract_rejects_invalid_relationships() -> None:
    event_id = str(uuid4())
    with pytest.raises(state.ConversationValidationError, match="own parent"):
        state.ConversationEventRecord(
            event_id=event_id,
            conversation_id=str(uuid4()),
            event_kind="branch_creation",
            actor_type="user",
            origin_class="current_user_instruction",
            parent_event_ids=(event_id,),
        )

    parent_id = str(uuid4())
    with pytest.raises(state.ConversationValidationError, match="must be unique"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="edit_regeneration",
            actor_type="assistant",
            origin_class="model_proposal",
            parent_event_ids=(parent_id, parent_id),
        )


def test_canonical_event_contract_rejects_invalid_time_and_unknown_kind() -> None:
    with pytest.raises(state.ConversationValidationError, match="timezone-aware"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
            occurred_at="2026-06-23T10:00:00",
        )

    with pytest.raises(state.ConversationValidationError, match="source event kind"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="imported_unknown_event",
            actor_type="importer",
            origin_class="imported_data",
        )
