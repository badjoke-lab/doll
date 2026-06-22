#!/usr/bin/env python3
"""Record the accepted IMP-023 primary-machine result and complete Phase 3."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT_SHA = "22e78b09ba0c144c2cddc918992d52f845c30185"
COMPLETED_AT = "2026-06-22T15:19:43.591791Z"

RESULT = {
    "architecture": "x86_64",
    "checks": {
        "all_implemented_entries_executable": True,
        "all_security_ids_mapped": True,
        "audit_history_readable": True,
        "classified_state_denied": True,
        "confirmation_cannot_bypass_release_exclusion": True,
        "confirmation_history_readable": True,
        "denial_preserved_revision": True,
        "exact_confirmation_accepted": True,
        "material_change_denied": True,
        "matrix_schema_valid": True,
        "only_unimplemented_listener_not_applicable": True,
        "prohibited_runtime_paths_absent": True,
        "read_only_reopen_succeeded": True,
        "real_machine_gate_declared": True,
        "release_exclusion_precedes_confirmation": True,
        "unknown_capability_denied": True,
    },
    "cloud_credentials_used": False,
    "commit_sha": COMMIT_SHA,
    "completed_at": COMPLETED_AT,
    "evidence_level": "real-machine",
    "executable_security_test_count": 22,
    "limitations": [
        "The repository has no model adapter or model execution path.",
        "The repository has no live capability execution adapter or external side effect.",
        "Localhost binding becomes applicable when an API listener is introduced.",
    ],
    "live_side_effect_used": False,
    "model_runtime_used": False,
    "network_mode": "offline-confirmed",
    "not_applicable_security_test_ids": ["SEC-007"],
    "operating_system": "Darwin",
    "phase3_gate_complete": True,
    "primary_intel_mac_gate": "pass",
    "privacy": {
        "absolute_paths_in_report": False,
        "hostnames_in_report": False,
        "private_fixture_content_in_report": False,
        "secret_values_in_report": False,
        "usernames_in_report": False,
    },
    "result": "pass",
    "security_test_count": 23,
    "specification_version": "0.1",
    "started_at": "2026-06-22T15:19:43.590538Z",
    "test_id": "IMP-023-SAFETY-ACCEPTANCE",
}


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one {label} block")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;\n- IMP-001 through IMP-021;\n- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, secret classification and redaction, secret-safe audit and logging, external secret-store contracts, credential brokering, claim and evidence separation, instruction-origin authority, prompt-injection defense, capability taxonomy, fixed risk tiers, and authorization preflight.""",
        """- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;\n- Phase 3 model-independent safety boundary;\n- IMP-001 through IMP-023;\n- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, secret classification and redaction, secret-safe audit and logging, external secret-store contracts, credential brokering, claim and evidence separation, instruction-origin authority, prompt-injection defense, capability taxonomy, fixed risk tiers, authorization preflight, mandatory high-risk confirmation, and safety acceptance evidence.""",
        label="completed-state",
    )
    text = replace_once(
        text,
        """- Phase 3 is in progress;\n- IMP-021 is complete;\n- IMP-022 is the next implementation item;\n- IMP-022 and IMP-023 complete and validate the remaining safety boundary;\n- Phase 4A and Phase 4B work begins only after the Phase 3 gate;\n- local model execution begins only after the safety gate and both Phase 4 foundations.""",
        """- Phase 3 is complete;\n- IMP-023 passed cross-platform CI and the primary Intel Mac offline real-process gate at main commit `22e78b09ba0c144c2cddc918992d52f845c30185`;\n- Phase 4A and Phase 4B are the next model-independent implementation foundations;\n- the first scheduled Phase 4 slice receives the next non-conflicting implementation identifier;\n- IMP-024 remains blocked until both Phase 4 foundation gates pass;\n- local model execution begins only after both Phase 4 foundations.""",
        label="current-state",
    )
    text = replace_once(
        text,
        """### IMP-022 — Mandatory High-Risk Confirmation\n\nImplement fresh user-controlled confirmation for every Tier 3 operation, exact binding to capability and side effects, expiry, material-change invalidation, and no confirmation from content.\n\n### IMP-023 — Safety Acceptance Test\n\nProve secret separation, credential isolation, claim and evidence separation, instruction origin, hostile-content resistance, capability denial, risk enforcement, exact confirmation, audit safety, cross-platform CI, and applicable primary-machine checks.\n\nPhase 3 gate:""",
        """### IMP-022 — Mandatory High-Risk Confirmation\n\nStatus: complete.\n\nImplemented fresh user-controlled confirmation for every Tier 3 operation, exact binding to capability and side effects, expiry, material-change invalidation, one-time consumption support, and no confirmation from content.\n\n### IMP-023 — Safety Acceptance Test\n\nStatus: complete.\n\nProved secret separation, credential isolation, claim and evidence separation, instruction origin, hostile-content resistance, capability denial, risk enforcement, exact confirmation, audit safety, cross-platform CI, and the primary Intel Mac offline real-process gate.\n\nAccepted Phase 3 evidence:\n\n- merged implementation commit: `22e78b09ba0c144c2cddc918992d52f845c30185`;\n- Ubuntu, macOS, and Windows CI passed;\n- Windows reported 745 passed, 1 skipped, and 95.25% coverage;\n- the primary Intel Mac run passed on Darwin `x86_64` with networking disabled;\n- the accepted report returned `phase3_gate_complete = true`;\n- SEC-007 remains explicitly deferred because no API listener exists.\n\nPhase 3 gate status: passed on 2026-06-22.\n\nPhase 3 gate:""",
        label="imp022-imp023",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_acceptance_doc() -> None:
    path = ROOT / "docs/testing/IMP-023-safety-acceptance.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "Automated CI acceptance is implemented on Issue #78. The Phase 3 gate remains open until the exact final commit also passes the primary Intel Mac real-process run with networking disabled.",
        "IMP-023 and the Phase 3 safety gate are complete. Cross-platform CI and the primary Intel Mac offline real-process run passed for main commit `22e78b09ba0c144c2cddc918992d52f845c30185`.",
        label="acceptance-status",
    )
    text = replace_once(
        text,
        "A passing report from this command is the remaining machine-level evidence required before the roadmap may mark IMP-023 and Phase 3 complete.",
        """The accepted primary-machine run completed at `2026-06-22T15:19:43.591791Z` on Darwin `x86_64`, with `network_mode = offline-confirmed`, `primary_intel_mac_gate = pass`, and `phase3_gate_complete = true`. The complete bounded report is stored in `docs/testing/imp-023-primary-intel-mac-result.json`.""",
        label="machine-result",
    )
    text = replace_once(
        text,
        "Automated CI success proves that the implemented model-independent boundary is internally consistent across the supported CI operating systems. It does not by itself authorize Phase 4 or IMP-024.",
        "Combined cross-platform CI and primary Intel Mac evidence proves that the implemented model-independent Phase 3 boundary passed its accepted gate. This authorizes beginning Phase 4A and Phase 4B foundation work; it does not authorize IMP-024 or model integration before both Phase 4 gates pass.",
        label="gate-interpretation",
    )
    text = replace_once(
        text,
        "- The primary Intel Mac result cannot be supplied by GitHub-hosted CI and must be recorded separately on the exact final commit.",
        "- Future listeners, runtimes, adapters, and executable capabilities require additional acceptance evidence for their newly introduced paths.",
        label="known-limitation",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_matrix() -> None:
    path = ROOT / "docs/testing/phase-3-safety-matrix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase3_gate_complete"] = True
    payload["accepted_real_machine_result"] = (
        "docs/testing/imp-023-primary-intel-mac-result.json"
    )
    payload["real_machine_gate"] = {
        "required": True,
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "status": "pass",
        "runner": "scripts/run_imp_023_safety_acceptance.py",
        "commit_sha": COMMIT_SHA,
        "completed_at": COMPLETED_AT,
        "evidence_level": "real-machine",
        "network_mode": "offline-confirmed",
    }
    payload["limitations"] = [
        item
        for item in payload["limitations"]
        if item
        != "The primary Intel Mac real-process run remains required before Phase 3 is declared complete."
    ]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_result() -> None:
    path = ROOT / "docs/testing/imp-023-primary-intel-mac-result.json"
    path.write_text(
        json.dumps(RESULT, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    update_roadmap()
    update_acceptance_doc()
    update_matrix()
    write_result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
