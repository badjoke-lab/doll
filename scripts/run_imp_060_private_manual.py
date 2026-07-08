"""Run privacy-safe IMP-060 numbered ChatGPT export aggregation and IMP-059 review."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from doll.chatgpt_numbered_aggregation import (
    ChatGPTNumberedConversationAggregator,
    ChatGPTNumberedMember,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "IMP-060-CHATGPT-NUMBERED-PRIVATE-MANUAL"
_BOUND_PATHS = (
    "scripts/run_imp_060_private_manual.py",
    "src/doll/chatgpt_numbered_aggregation.py",
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
    }


def _read_members(member_list: Path) -> tuple[ChatGPTNumberedMember, ...]:
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
    members: list[ChatGPTNumberedMember] = []
    for value in lines:
        path = Path(value).expanduser().resolve()
        if not _outside_repository(path):
            raise RuntimeError("numbered member must remain outside the repository")
        if path in resolved_paths:
            raise RuntimeError("member list contains duplicate paths")
        if not path.is_file():
            raise RuntimeError("numbered member path is not a file")
        resolved_paths.add(path)
        members.append(
            ChatGPTNumberedMember(
                label=path.name,
                source_bytes=path.read_bytes(),
            )
        )
    return tuple(members)


def _run_imp059(
    arguments: argparse.Namespace,
    aggregate_path: Path,
) -> tuple[int, dict[str, object]]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_imp_059_private_manual.py"),
        "--mode",
        arguments.mode,
        "--source",
        str(aggregate_path),
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


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        binding_checks = _verify_commit_binding(arguments.runner_commit)
        if not all(binding_checks.values()):
            raise RuntimeError("numbered runner commit binding failed")
        if not _outside_repository(arguments.selection_file):
            raise RuntimeError("selection file must remain outside the repository")

        stage = "numbered_members"
        members = _read_members(arguments.member_list)
        aggregation = ChatGPTNumberedConversationAggregator().aggregate(members)

        stage = "imp059_private_manual"
        with tempfile.TemporaryDirectory(prefix="doll-imp060-private-") as raw:
            aggregate_path = Path(raw) / "conversations.json"
            aggregate_path.write_bytes(aggregation.aggregated_bytes)
            returncode, payload = _run_imp059(arguments, aggregate_path)

        payload["test_id"] = TEST_ID
        payload["numbered_aggregation"] = aggregation.canonical_summary()
        payload["numbered_binding_checks"] = binding_checks
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
