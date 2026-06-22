"""Run the model-independent IMP-023 Phase 3 safety acceptance probe."""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TEST_ID = "IMP-023-SAFETY-ACCEPTANCE"
SPECIFICATION_VERSION = "0.1"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "docs" / "testing" / "phase-3-safety-matrix.json"
_REQUIRED_IDS = tuple(f"SEC-{index:03d}" for index in range(1, 24))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument("--offline-confirmed", action="store_true")
    return parser.parse_args()


def _head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _check_environment(arguments: argparse.Namespace) -> None:
    if not _COMMIT_PATTERN.fullmatch(arguments.commit_sha):
        raise RuntimeError("invalid commit SHA")
    if _head() != arguments.commit_sha:
        raise RuntimeError("checked-out commit mismatch")
    if arguments.evidence_level != "real-machine":
        return
    if platform.system() != "Darwin":
        raise RuntimeError("real-machine evidence requires macOS")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("real-machine evidence requires Intel")
    if not arguments.offline_confirmed:
        raise RuntimeError("offline confirmation required")


def _load_matrix() -> dict[str, Any]:
    payload = json.loads(_MATRIX.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("safety matrix must be an object")
    return payload


def _contains_tests(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    )


def _validate_matrix(matrix: dict[str, Any]) -> dict[str, bool]:
    entries = matrix.get("security_tests")
    if not isinstance(entries, list):
        raise RuntimeError("safety matrix entries are missing")
    ids = tuple(entry.get("id") for entry in entries if isinstance(entry, dict))
    if ids != _REQUIRED_IDS:
        raise RuntimeError("safety matrix must cover SEC-001 through SEC-023 exactly once")

    executable = 0
    not_applicable = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("safety matrix entry is invalid")
        status = entry.get("status")
        note = entry.get("scope_note")
        files = entry.get("pytest_files")
        if not isinstance(note, str) or not note.strip():
            raise RuntimeError("safety matrix scope note is missing")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise RuntimeError("safety matrix pytest files are invalid")
        if status == "not_applicable":
            not_applicable += 1
            if files:
                raise RuntimeError("not-applicable matrix entry must not claim pytest evidence")
            continue
        if status != "pass" or not files:
            raise RuntimeError("blocking safety entry lacks executable evidence")
        for relative in files:
            path = _ROOT / relative
            if not path.is_file() or not _contains_tests(path):
                raise RuntimeError("safety matrix references missing executable tests")
        executable += 1

    gate = matrix.get("real_machine_gate")
    if not isinstance(gate, dict) or gate.get("status") != "pending":
        raise RuntimeError("real-machine gate must remain pending in repository evidence")
    return {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "all_security_ids_mapped": ids == _REQUIRED_IDS,
        "all_implemented_entries_executable": executable == 22,
        "only_unimplemented_listener_not_applicable": not_applicable == 1,
        "real_machine_gate_declared": gate.get("required") is True,
    }


def _fresh_process_probe() -> dict[str, bool]:
    code = r'''
import json
import sys
from dataclasses import replace
from pathlib import Path

from doll import state, workspace
from doll.audit import AuditService
from doll.capabilities import (
    CapabilityPreflightService,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResourceLimits,
    CapabilityTarget,
    OutboundNetworkPolicy,
    built_in_capability_registry,
)
from doll.confirmation import ConfirmationPreview, ConfirmationService
from doll.confirmation_preflight import ConfirmedCapabilityPreflightService
from doll.settings import PermissionDecision


class ScopedPermissions:
    def resolve(self, *, capability_id: str, scope: dict[str, object]) -> PermissionDecision:
        return PermissionDecision(
            record_id="synthetic-permission",
            capability_id=capability_id,
            scope=scope,
            effective_mode="scoped",
            reason="active",
        )


def tier3_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="adapter.fixed_process.example",
        capability_version="1.0",
        operation_id="imp023-tier3",
        actor_type="model",
        origin_class="model_proposal",
        arguments={
            "project_id": "project-1",
            "name": "output.txt",
            "input_record_id": "record-1",
        },
        target=CapabilityTarget("managed_artifact", "project-1/output.txt"),
        destination=None,
        declared_side_effects=frozenset(
            {"process_execution", "create_managed_artifact"}
        ),
        declared_risk_tier=3,
        permission_scope={"kind": "project", "project_id": "project-1"},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
        session_id="session-1",
        cancellation_id="cancel-tier3",
    )


root = Path(sys.argv[1]) / "workspace"
initialized = workspace.initialize_workspace(root)
checks: dict[str, bool] = {}
with state.initialize_state_repository(initialized.root) as repository:
    before = repository.status().state_revision
    try:
        repository.create_record(
            record_type="memory",
            sensitivity="secret",
            metadata={"content": "synthetic secret-shaped value"},
        )
    except state.RecordValidationError:
        checks["secret_write_denied"] = True
    else:
        checks["secret_write_denied"] = False
    checks["denial_preserved_revision"] = repository.status().state_revision == before

    secret_value = "Bearer synthetic-imp023-credential"
    event = AuditService(repository).append(
        action="imp023.synthetic",
        result="denied",
        metadata={"note": secret_value},
    )
    rendered_event = repr(event)
    checks["audit_redacted"] = (
        secret_value not in rendered_event
        and "[REDACTED:authorization_header]" in rendered_event
    )

    registry = built_in_capability_registry()
    permissions = ScopedPermissions()
    network_policy = OutboundNetworkPolicy(enabled=False)
    base = CapabilityPreflightService(
        registry=registry,
        permissions=permissions,
        audit=AuditService(repository),
        network_policy=network_policy,
    )
    unknown = CapabilityRequest(
        capability_id="unknown.capability",
        capability_version="1.0",
        operation_id="imp023-unknown",
        actor_type="model",
        origin_class="model_proposal",
        arguments={"text": "hello", "operation": "uppercase"},
        target=CapabilityTarget("provided_data", "inline-data"),
        destination=None,
        declared_side_effects=frozenset(),
        declared_risk_tier=0,
        permission_scope={"kind": "none"},
        resource_limits=CapabilityResourceLimits(100, 1024, 1),
        timeout_seconds=5,
    )
    unknown_decision = base.preflight(unknown)
    checks["unknown_capability_denied"] = (
        not unknown_decision.authorized
        and unknown_decision.reason == "unknown_capability"
    )

    request = tier3_request()
    confirmations = ConfirmationService(repository)
    release_excluded = ConfirmedCapabilityPreflightService(
        registry=registry,
        permissions=permissions,
        audit=AuditService(repository),
        network_policy=network_policy,
        confirmations=confirmations,
    ).preflight(request)
    checks["release_excluded_precedes_confirmation"] = (
        not release_excluded.authorized
        and release_excluded.capability.reason == "release_excluded"
        and release_excluded.confirmation_reason == "not_evaluated"
    )

    released = CapabilityRegistry(
        tuple(
            replace(definition, release_available=True)
            if definition.capability_id == "adapter.fixed_process.example"
            else definition
            for definition in registry.definitions()
        )
    )
    info = confirmations.issue(
        request,
        registry=released,
        preview=ConfirmationPreview(
            effect_summary="Run one reviewed synthetic fixed adapter.",
            irreversible=False,
            recovery_description="No real side effect is performed.",
        ),
        decision="approved",
    )
    confirmed = ConfirmedCapabilityPreflightService(
        registry=released,
        permissions=permissions,
        audit=AuditService(repository),
        network_policy=network_policy,
        confirmations=confirmations,
    )
    exact = confirmed.preflight(request, confirmation_id=info.confirmation_id)
    changed = confirmed.preflight(
        replace(request, session_id="session-2"),
        confirmation_id=info.confirmation_id,
    )
    checks["fresh_exact_confirmation_accepted"] = exact.authorized
    checks["material_change_invalidates_confirmation"] = (
        not changed.authorized and changed.confirmation_reason == "mismatch"
    )
    checks["confirmation_cannot_bypass_release_exclusion"] = (
        not ConfirmedCapabilityPreflightService(
            registry=registry,
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=network_policy,
            confirmations=confirmations,
        ).preflight(request, confirmation_id=info.confirmation_id).authorized
    )

with state.open_state_repository(initialized.root, read_only=True) as repository:
    events = AuditService(repository).list(limit=200)
    resolution = ConfirmationService(repository).resolve(
        info.confirmation_id,
        request,
        registry_fingerprint=released.fingerprint,
        normalized_destination=None,
    )
    checks["fresh_process_state_opened"] = repository.status().record_count == 0
    checks["fresh_process_audit_readable"] = len(events) >= 5
    checks["fresh_process_confirmation_readable"] = resolution.reason == "approved"

checks["model_runtime_used"] = False
checks["cloud_credentials_used"] = False
checks["live_side_effect_used"] = False
print(json.dumps(checks, sort_keys=True, separators=(",", ":")))
'''
    with tempfile.TemporaryDirectory(prefix="doll-imp023-") as temporary:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", code, temporary],
            cwd=_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError("fresh-process safety probe failed")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict) or not all(isinstance(value, bool) for value in payload.values()):
        raise RuntimeError("fresh-process safety probe returned invalid evidence")
    return payload


def _report(arguments: argparse.Namespace) -> dict[str, Any]:
    started_at = _utc_now()
    matrix = _load_matrix()
    checks = {**_validate_matrix(matrix), **_fresh_process_probe()}
    if not all(checks.values()):
        raise RuntimeError("one or more safety acceptance checks failed")
    real_machine = arguments.evidence_level == "real-machine"
    return {
        "test_id": TEST_ID,
        "specification_version": SPECIFICATION_VERSION,
        "commit_sha": arguments.commit_sha,
        "result": "pass",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "evidence_level": arguments.evidence_level,
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "network_mode": "offline-confirmed" if real_machine else "no-network-path-in-probe",
        "checks": checks,
        "security_test_count": 23,
        "executable_security_test_count": 22,
        "not_applicable_security_test_ids": ["SEC-007"],
        "model_runtime_used": False,
        "cloud_credentials_used": False,
        "live_side_effect_used": False,
        "primary_intel_mac_gate": "pass" if real_machine else "pending",
        "phase3_gate_complete": real_machine,
        "limitations": matrix.get("limitations", []),
        "privacy": {
            "absolute_paths_in_report": False,
            "usernames_in_report": False,
            "hostnames_in_report": False,
            "secret_values_in_report": False,
            "private_fixture_content_in_report": False,
        },
    }


def main() -> int:
    arguments = _arguments()
    try:
        _check_environment(arguments)
        report = _report(arguments)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "test_id": TEST_ID,
                    "commit_sha": arguments.commit_sha,
                    "result": "fail",
                    "completed_at": _utc_now(),
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
