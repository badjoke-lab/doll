from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_imp_060_private_manual.py"
OBSERVED_AT = "2026-07-08T00:00:00Z"
ENVIRONMENT_ID = "60000000-0000-4000-8000-000000000101"
REVIEW_BATCH_ID = "60000000-0000-4000-8000-000000000102"
COMPLETE_BATCH_ID = "60000000-0000-4000-8000-000000000103"
SELECTED_ID = "private-selected-numbered-id-should-not-leak"
UNSELECTED_ID = "private-unselected-numbered-id-should-not-leak"
PRIVATE_MARKERS = (
    SELECTED_ID,
    UNSELECTED_ID,
    "Private numbered selected title should not leak",
    "Private numbered selected text should not leak",
    "Private numbered unselected title should not leak",
    "Private numbered unselected text should not leak",
    "private-numbered-model-should-not-leak",
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
        "metadata": {"model_slug": "private-numbered-model-should-not-leak"},
        "recipient": "all",
        "channel": None,
    }


def _conversation(
    conversation_id: str,
    *,
    title: str,
    text: str,
) -> dict[str, object]:
    return {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": title,
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "mapping": {
            "root": {
                "id": "root",
                "message": None,
                "parent": None,
                "children": ["user"],
            },
            "user": {
                "id": "user",
                "message": _message("message-user", "user", text),
                "parent": "root",
                "children": [],
            },
        },
        "current_node": "user",
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    first = tmp_path / "conversations-1.json"
    second = tmp_path / "conversations-2.json"
    first.write_text(
        json.dumps(
            [
                _conversation(
                    SELECTED_ID,
                    title="Private numbered selected title should not leak",
                    text="Private numbered selected text should not leak",
                )
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            [
                _conversation(
                    UNSELECTED_ID,
                    title="Private numbered unselected title should not leak",
                    text="Private numbered unselected text should not leak",
                )
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    member_list = tmp_path / "numbered-members.txt"
    member_list.write_text(f"{second}\n{first}\n", encoding="utf-8")
    selection = tmp_path / "selected-conversations.txt"
    selection.write_text(f"{SELECTED_ID}\n", encoding="utf-8")
    return member_list, selection


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
    member_list: Path,
    selection: Path,
    batch_id: str,
    *,
    confirmations: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--mode",
        mode,
        "--member-list",
        str(member_list),
        "--selection-file",
        str(selection),
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
    assert str(tmp_path) not in output


def test_numbered_private_manual_review_is_content_free(tmp_path: Path) -> None:
    member_list, selection = _write_inputs(tmp_path)

    result = _run("review", member_list, selection, REVIEW_BATCH_ID)

    assert result.returncode == 0, result.stderr
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["result"] == "review-ready"
    assert payload["mode"] == "review"
    assert payload["test_id"] == "IMP-060-CHATGPT-NUMBERED-PRIVATE-MANUAL"
    aggregation = payload["numbered_aggregation"]
    assert aggregation["member_count"] == 2
    assert aggregation["input_conversation_count"] == 2
    assert aggregation["output_conversation_count"] == 2
    assert aggregation["exact_duplicate_conversation_count"] == 0
    assert [member["index"] for member in aggregation["members"]] == [1, 2]
    assert payload["review"]["conversation_count"] == 2
    assert payload["review"]["selected_conversation_count"] == 1
    assert all(payload["numbered_binding_checks"].values())
    _assert_private_values_absent(result.stdout, tmp_path)


def test_numbered_private_manual_complete_preserves_selected_history(tmp_path: Path) -> None:
    member_list, selection = _write_inputs(tmp_path)

    result = _run(
        "complete",
        member_list,
        selection,
        COMPLETE_BATCH_ID,
        confirmations=True,
    )

    assert result.returncode == 0, result.stderr
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["result"] == "pass"
    assert payload["mode"] == "complete"
    assert payload["evidence_level"] == "private-manual"
    assert payload["numbered_aggregation"]["member_count"] == 2
    assert payload["numbered_aggregation"]["output_conversation_count"] == 2
    assert all(payload["checks"].values())
    assert all(payload["numbered_binding_checks"].values())
    _assert_private_values_absent(result.stdout, tmp_path)


def test_numbered_private_manual_rejects_member_list_inside_repository(tmp_path: Path) -> None:
    _, selection = _write_inputs(tmp_path)
    member_list = ROOT / "imp060-test-member-list.txt"
    member_list.write_text("/tmp/conversations-1.json\n", encoding="utf-8")
    try:
        result = _run("review", member_list, selection, REVIEW_BATCH_ID)
    finally:
        member_list.unlink()

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "numbered_members"
    assert payload["error_class"] == "RuntimeError"
