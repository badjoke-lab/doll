from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_imp_059_private_manual.py"
OBSERVED_AT = "2026-07-05T00:00:00Z"
ENVIRONMENT_ID = "59000000-0000-4000-8000-000000000101"
REVIEW_BATCH_ID = "59000000-0000-4000-8000-000000000102"
COMPLETE_BATCH_ID = "59000000-0000-4000-8000-000000000103"
SELECTED_ID = "private-selected-id-should-not-leak"
UNSELECTED_ID = "private-unselected-id-should-not-leak"
PRIVATE_MARKERS = (
    SELECTED_ID,
    UNSELECTED_ID,
    "Private selected title should not leak",
    "Private selected user text should not leak",
    "Private selected assistant text should not leak",
    "Private unselected title should not leak",
    "Private unselected text should not leak",
)


def _message(message_id: str, role: str, text: str) -> dict[str, object]:
    return {
        "id": message_id,
        "author": {"role": role, "name": None, "metadata": {}},
        "create_time": 1_700_000_000.0,
        "update_time": None,
        "content": {"content_type": "text", "parts": [text]},
        "status": "finished_successfully",
        "end_turn": True,
        "weight": 1.0,
        "metadata": {"model_slug": "private-model-name-should-not-leak"},
        "recipient": "all",
        "channel": None,
    }


def _conversation(
    conversation_id: str,
    *,
    title: str,
    user_text: str,
    assistant_text: str,
) -> dict[str, object]:
    mapping = {
        "root": {
            "id": "root",
            "message": None,
            "parent": None,
            "children": ["user"],
        },
        "user": {
            "id": "user",
            "message": _message("message-user", "user", user_text),
            "parent": "root",
            "children": ["assistant"],
        },
        "assistant": {
            "id": "assistant",
            "message": _message(
                "message-assistant",
                "assistant",
                assistant_text,
            ),
            "parent": "user",
            "children": [],
        },
    }
    return {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": title,
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "mapping": mapping,
        "current_node": "assistant",
    }


def _write_private_inputs(tmp_path: Path) -> tuple[Path, Path]:
    source_path = tmp_path / "conversations.json"
    selection_path = tmp_path / "selected-conversations.txt"
    source = [
        _conversation(
            SELECTED_ID,
            title="Private selected title should not leak",
            user_text="Private selected user text should not leak",
            assistant_text="Private selected assistant text should not leak",
        ),
        _conversation(
            UNSELECTED_ID,
            title="Private unselected title should not leak",
            user_text="Private unselected text should not leak",
            assistant_text="Private unselected text should not leak",
        ),
    ]
    source_path.write_text(
        json.dumps(source, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    selection_path.write_text(f"{SELECTED_ID}\n", encoding="utf-8")
    return source_path, selection_path


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(
    mode: str,
    source_path: Path,
    selection_path: Path,
    batch_id: str,
    *,
    confirmations: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--mode",
        mode,
        "--source",
        str(source_path),
        "--selection-file",
        str(selection_path),
        "--source-environment-id",
        ENVIRONMENT_ID,
        "--import-batch-id",
        batch_id,
        "--observed-at",
        OBSERVED_AT,
        "--runner-commit",
        _head(),
    ]
    if confirmations:
        command.extend(("--confirm-network-disabled", "--confirm-reviewed"))
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_private_values_absent(output: str, tmp_path: Path) -> None:
    for marker in PRIVATE_MARKERS:
        assert marker not in output
    assert "private-model-name-should-not-leak" not in output
    assert str(tmp_path) not in output


def test_private_manual_review_is_content_free(tmp_path: Path) -> None:
    source_path, selection_path = _write_private_inputs(tmp_path)
    result = _run(
        "review",
        source_path,
        selection_path,
        REVIEW_BATCH_ID,
    )

    assert result.returncode == 0, result.stderr
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["result"] == "review-ready"
    assert payload["mode"] == "review"
    review = payload["review"]
    assert review["conversation_count"] == 2
    assert review["selected_conversation_count"] == 1
    assert review["selected_message_count"] == 2
    assert review["supported_message_count"] == 2
    assert review["quarantine_count"] == 0
    assert review["material_loss_count"] == 0
    assert all(value is False for value in payload["privacy"].values())
    _assert_private_values_absent(result.stdout, tmp_path)


def test_private_manual_complete_preserves_selected_history(tmp_path: Path) -> None:
    source_path, selection_path = _write_private_inputs(tmp_path)
    result = _run(
        "complete",
        source_path,
        selection_path,
        COMPLETE_BATCH_ID,
        confirmations=True,
    )

    assert result.returncode == 0, result.stderr
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["result"] == "pass"
    assert payload["mode"] == "complete"
    assert payload["evidence_level"] == "private-manual"
    assert payload["real_machine_used"] is True
    assert payload["private_source_used"] is True
    assert payload["external_network_request_used"] is False
    assert payload["chatgpt_history_gate_complete"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())
    evidence = payload["evidence"]
    assert evidence["conversation_count"] == 2
    assert evidence["selected_conversation_count"] == 1
    assert evidence["selected_message_count"] == 2
    assert evidence["supported_message_count"] == 2
    assert evidence["published_object_count"] == 3
    assert evidence["runtime_mode"] == "private-manual"
    _assert_private_values_absent(result.stdout, tmp_path)


def test_private_manual_complete_requires_confirmations(tmp_path: Path) -> None:
    source_path, selection_path = _write_private_inputs(tmp_path)
    result = _run(
        "complete",
        source_path,
        selection_path,
        COMPLETE_BATCH_ID,
        confirmations=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "private_manual_completion"
    assert payload["error_class"] == "RuntimeError"
    _assert_private_values_absent(result.stdout, tmp_path)
