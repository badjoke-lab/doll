"""Run privacy-safe IMP-060 numbered ChatGPT export review and completion."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from doll.chatgpt_numbered_projection import (
    ChatGPTNumberedPathMember,
    ChatGPTNumberedProjectionResult,
    ChatGPTNumberedSequentialProjector,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "IMP-060-CHATGPT-NUMBERED-PRIVATE-MANUAL"
_BOUND_PATHS = (
    "scripts/run_imp_060_private_manual.py",
    "src/doll/chatgpt_numbered_aggregation.py",
    "src/doll/chatgpt_numbered_projection.py",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("review", "complete"), required=True)
    parser.add_argument("--member-list", type=Path, required=True)
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


def _outside_repository(path: Path) -> bool:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return True
    return False


def _verify_commit_binding(runner_commit: str) -> dict[str, bool]:
    if runner_commit != _git("rev-parse", "HEAD"):
        raise RuntimeError("runner commit mismatch")
    exact = all(
        _git("hash-object", relative) == _git("rev-parse", f"{runner_commit}:{relative}")
        for relative in _BOUND_PATHS
    )
    return {
        "numbered_runner_matches_bound_commit": exact,
        "numbered_aggregator_matches_bound_commit": exact,
        "numbered_projection_matches_bound_commit": exact,
    }


def _read_member_paths(member_list: Path) -> tuple[ChatGPTNumberedPathMember, ...]:
    if not _outside_repository(member_list):
        raise RuntimeError("member list must remain outside the repository")
    lines = [
        line.strip()
        for line in member_list.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        raise RuntimeError("member list is empty")

    resolved_paths: set[Path] = set()
    members: list[ChatGPTNumberedPathMember] = []
    for value in lines:
        path = Path(value).expanduser().resolve()
        if not _outside_repository(path):
            raise RuntimeError("numbered member must remain outside the repository")
        if path in resolved_paths:
            raise RuntimeError("member list contains duplicate paths")
        if not path.is_file():
            raise RuntimeError("numbered member path is not a file")
        resolved_paths.add(path)
        members.append(ChatGPTNumberedPathMember(label=path.name, path=path))
    return tuple(members)


def _read_selection(selection_file: Path) -> tuple[str, ...]:
    if not _outside_repository(selection_file):
        raise RuntimeError("selection file must remain outside the repository")
    selected = tuple(
        line.strip()
        for line in selection_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not selected:
        raise RuntimeError("selection file is empty")
    return selected


def _run_imp059(
    arguments: argparse.Namespace,
    projection_path: Path,
) -> tuple[int, dict[str, object]]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_imp_059_private_manual.py"),
        "--mode",
        arguments.mode,
        "--source",
        str(projection_path),
        "--selection-file",
        str(arguments.selection_file),
        "--source-environment-id",
        arguments.source_environment_id,
        "--import-batch-id",
        arguments.import_batch_id,
        "--observed-at",
        arguments.observed_at,
        "--runner-commit",
        arguments.runner_commit,
    ]
    if arguments.confirm_network_disabled:
        command.append("--confirm-network-disabled")
    if arguments.confirm_reviewed:
        command.append("--confirm-reviewed")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("IMP-059 private manual runner returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("IMP-059 private manual result must be an object")
    return completed.returncode, payload


def _apply_projection_evidence(
    payload: dict[str, object],
    projection: ChatGPTNumberedProjectionResult,
    binding_checks: dict[str, bool],
) -> None:
    payload["test_id"] = TEST_ID
    payload["numbered_aggregation"] = projection.canonical_summary()
    payload["numbered_binding_checks"] = binding_checks

    review = payload.get("review")
    if isinstance(review, dict):
        projection_hash = review.pop("source_root_hash", None)
        if projection_hash is not None:
            review["selected_projection_source_root_hash"] = projection_hash
        review["conversation_count"] = projection.output_conversation_count
        review["attachment_reference_count"] = (
            projection.aggregate_attachment_reference_count
        )
        review["malformed_object_count"] = projection.aggregate_malformed_object_count
        review["unknown_field_count"] = projection.aggregate_unknown_field_count

    checks = payload.get("checks")
    if isinstance(checks, dict) and "exact_source_preserved" in checks:
        preserved = checks.pop("exact_source_preserved")
        checks["selected_projection_exact_source_preserved"] = preserved

    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        projection_hash = evidence.pop("source_root_hash", None)
        if projection_hash is not None:
            evidence["selected_projection_source_root_hash"] = projection_hash
        evidence["conversation_count"] = projection.output_conversation_count
        evidence["aggregate_attachment_reference_count"] = (
            projection.aggregate_attachment_reference_count
        )
        evidence["aggregate_malformed_object_count"] = (
            projection.aggregate_malformed_object_count
        )
        evidence["aggregate_unknown_field_count"] = projection.aggregate_unknown_field_count

    if payload.get("mode") == "complete":
        payload["limitations"] = [
            (
                "The result proves only a bounded selected-history migration drill from one "
                "explicit caller-provided numbered conversation member set."
            ),
            (
                "The complete numbered member set is sequentially validated and "
                "cryptographically bound, while only the bounded selected projection is handed "
                "to the unchanged IMP-059 mapping, publication, generic export, and shutdown "
                "escape path."
            ),
            (
                "ZIP ingestion, automatic discovery, attachment-byte recovery, account "
                "restoration, memory migration, GPT migration, settings migration, file "
                "restoration, and target-specific round-trip fidelity remain outside this result."
            ),
            "The complete Phase 6 gate and stable general anti-lock-in remain incomplete.",
        ]


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        binding_checks = _verify_commit_binding(arguments.runner_commit)
        if not all(binding_checks.values()):
            raise RuntimeError("numbered runner commit binding failed")

        stage = "numbered_members"
        members = _read_member_paths(arguments.member_list)
        selected = _read_selection(arguments.selection_file)
        projection = ChatGPTNumberedSequentialProjector().project(members, selected)

        stage = "imp059_private_manual"
        with tempfile.TemporaryDirectory(prefix="doll-imp060-private-") as raw:
            projection_path = Path(raw) / "conversations.json"
            projection_path.write_bytes(projection.selected_projection_bytes)
            returncode, payload = _run_imp059(arguments, projection_path)

        _apply_projection_evidence(payload, projection, binding_checks)
        status = 0 if returncode == 0 and payload.get("result") in {"review-ready", "pass"} else 1
    except BaseException as exc:
        payload = {
            "test_id": TEST_ID,
            "result": "fail",
            "error_stage": stage,
            "error_class": type(exc).__name__,
            "chatgpt_history_gate_complete": False,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
        }
        status = 1

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
