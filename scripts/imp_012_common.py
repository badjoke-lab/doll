"""Shared helpers for the IMP-012 continuity acceptance runner."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ARTIFACT_TEXT = "IMP-012 continuity acceptance 日本語\n"
TIMESTAMP = "2026-06-18T00:00:00Z"
TEST_ID = "IMP-012-CONTINUITY-ACCEPTANCE"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument("--offline-confirmed", action="store_true")
    return parser.parse_args()


def current_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def check_environment(arguments: argparse.Namespace) -> None:
    if not _COMMIT_PATTERN.fullmatch(arguments.commit_sha):
        raise RuntimeError("invalid commit SHA")
    if current_head() != arguments.commit_sha:
        raise RuntimeError("checked-out commit mismatch")
    if arguments.evidence_level != "real-machine":
        return
    if platform.system() != "Darwin":
        raise RuntimeError("real-machine evidence requires macOS")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("real-machine evidence requires Intel")
    if not arguments.offline_confirmed:
        raise RuntimeError("offline confirmation required")


def fresh_status(root: Path) -> dict[str, object]:
    code = """
import json
import sys
from pathlib import Path
from doll import state
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.settings import PermissionService, PolicyService, PreferenceService

root = Path(sys.argv[1])
with state.open_state_repository(root, read_only=True) as repository:
    status = repository.status()
    artifacts = WorkspaceFileService(repository).list()
    for artifact in artifacts:
        WorkspaceFileService(repository).verify(artifact.artifact_id)
    payload = {
        "workspace_id": status.workspace_id,
        "schema_version": status.schema_version,
        "state_revision": status.state_revision,
        "record_count": status.record_count,
        "preferences": len(PreferenceService(repository).list(include_archived=True)),
        "policies": len(PolicyService(repository).list(include_archived=True)),
        "permissions": len(PermissionService(repository).list(include_archived=True)),
        "memories": len(ConfirmedMemoryService(repository).list(include_archived=True)),
        "projects": len(ProjectService(repository).list(include_archived=True)),
        "decisions": len(DecisionService(repository).list(include_archived=True)),
        "artifacts": len(artifacts),
        "audit_events": len(AuditService(repository).list(limit=200)),
    }
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("invalid fresh-process payload")
    return payload


def tamper_archive(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = next(name for name in sorted(members) if name.endswith("manifest.json"))
    members[manifest] += b"\n"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
