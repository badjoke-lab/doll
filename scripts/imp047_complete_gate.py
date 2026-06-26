from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "ddb58d041e505556910930724d0cf2fd03afe7d3"
COMPLETED = "2026-06-26T12:37:23.396078Z"
RESULT_REL = "docs/testing/results/IMP-047-primary-intel-mac-2026-06-26.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing replacement for {label}")
    return text.replace(old, new, 1)


def validate_result() -> dict[str, object]:
    result = json.loads((ROOT / RESULT_REL).read_text(encoding="utf-8"))
    required = {
        "test_id": "IMP-047-PROJECT-CONTINUITY-ACCEPTANCE",
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": "Darwin",
        "architecture": "x86_64",
        "python_version": "3.12.13",
        "network_mode": "offline-confirmed",
        "commit_sha": COMMIT,
        "completed_at": COMPLETED,
        "primary_intel_mac_gate": "pass",
        "phase4b_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in required.items()):
        raise RuntimeError("stored result does not match accepted evidence")
    checks = result.get("checks")
    privacy = result.get("privacy")
    if not isinstance(checks, dict) or not checks or not all(checks.values()):
        raise RuntimeError("stored result checks are not all true")
    if not isinstance(privacy, dict) or any(privacy.values()):
        raise RuntimeError("stored result privacy flags are not all false")
    return result


def update_matrix() -> None:
    path = ROOT / "docs/testing/phase-4b-project-continuity-matrix.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    matrix["phase4b_gate_complete"] = True
    matrix["accepted_real_machine_result"] = RESULT_REL
    for entry in matrix["project_tests"]:
        entry["evidence_levels"] = [
            "primary_real_machine" if level == "primary_real_machine_pending" else level
            for level in entry["evidence_levels"]
        ]
    matrix["real_machine_gate"].update(
        {"status": "pass", "commit_sha": COMMIT, "completed_at": COMPLETED}
    )
    matrix["limitations"] = [
        "Phase 4B is complete for the model-independent project-continuity foundation.",
        "This gate proves model-independent project continuity and resumption inspection, not autonomous project management.",
        "No local model runtime, provider, cloud account, external issue tracker, or multi-user collaboration path is exercised.",
        "Generated project status, Resume Bundle, and HANDOFF.md remain non-authoritative derived views.",
    ]
    path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")


def update_acceptance_doc() -> None:
    content = """# IMP-047 — Phase 4B project-continuity acceptance

## Status

Accepted. The primary Intel Mac offline gate passed on exact merged `main` commit `ddb58d041e505556910930724d0cf2fd03afe7d3` on 2026-06-26.

Accepted evidence:

- `docs/testing/results/IMP-047-primary-intel-mac-2026-06-26.json`

The stored JSON is preserved from the accepted run. Its `limitations` array still contains the pre-storage pending statement emitted by the runner; the updated matrix is the authoritative post-acceptance gate state.

Phase 4B is complete for the model-independent project-continuity foundation covered by PROJ-001 through PROJ-012. This does not connect a local model runtime or establish autonomous project management.

## Verified boundary

The accepted run verified:

- ProjectRecord v2 and implemented child-record continuity;
- deterministic WorkItemRecord, ProcedureRecord, and ProjectCheckpointRecord behavior;
- deterministic read-only project status and project-scoped Resume Bundle generation;
- independent Resume Bundle inspection using only the Python standard library;
- Doll State Package v2 transfer and supported package-v1 neutrality;
- state and workspace backup restoration with artifact preservation;
- fresh-process operation without a model, provider, cloud account, preferred UI, or usable network route;
- imported-content inability to claim authoritative progress;
- secret omission, privacy-safe bounded output, and recoverable cleanup.

## Accepted environment

- commit: `ddb58d041e505556910930724d0cf2fd03afe7d3`;
- operating system: `Darwin`;
- architecture: `x86_64`;
- Python: `3.12.13`;
- network mode: `offline-confirmed`;
- evidence level: `real-machine`.

Result:

```text
result = pass
primary_intel_mac_gate = pass
phase4b_gate_complete = true
```

The stored result contains no absolute paths, usernames, hostnames, credentials, secret values, private fixture content, or personal project data.

## CI validation

```bash
python scripts/run_imp_047_project_continuity_acceptance.py \\
  --commit-sha "$(git rev-parse HEAD)" \\
  --evidence-level ci
```

CI validates the stored real-machine result against the matrix commit, platform, architecture, completion time, offline mode, and passing checks.

## Deliberate limitations

- This proves model-independent project continuity, not autonomous project management.
- No local model runtime, cloud provider, external issue tracker, or multi-user collaboration path is exercised.
- Generated project status, Resume Bundle, and HANDOFF.md remain non-authoritative derived views.
- Later model integration must continue to use the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.

## Issue

Completion of #145.
"""
    (ROOT / "docs/implementation/imp-047-phase4b-acceptance.md").write_text(
        content, encoding="utf-8"
    )


def update_tests() -> None:
    path = ROOT / "tests/test_project_continuity_acceptance.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "def test_imp_047_ci_evidence_passes_with_primary_machine_pending() -> None:",
        "def test_imp_047_ci_evidence_preserves_completed_primary_machine_gate() -> None:",
        "acceptance test name",
    )
    text = replace_once(
        text,
        'assert payload["primary_intel_mac_gate"] == "pending"',
        'assert payload["primary_intel_mac_gate"] == "pass"',
        "primary gate assertion",
    )
    text = replace_once(
        text,
        'assert payload["phase4b_gate_complete"] is False',
        'assert payload["phase4b_gate_complete"] is True',
        "phase gate assertion",
    )
    path.write_text(text, encoding="utf-8")

    static = '''from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-4b-project-continuity-matrix.json")
INSPECTOR = Path("scripts/imp_047_bundle_inspector.py")


def test_phase_4b_matrix_maps_proj_001_through_proj_012_with_gate_complete() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["project_tests"]
    result_path = Path(matrix["accepted_real_machine_result"])
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "4B"
    assert matrix["phase4b_gate_complete"] is True
    assert result_path == Path(
        "docs/testing/results/IMP-047-primary-intel-mac-2026-06-26.json"
    )
    assert [item["id"] for item in entries] == [
        f"PROJ-{number:03d}" for number in range(1, 13)
    ]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert entries[0]["evidence_levels"][-1] == "primary_real_machine"
    assert entries[8]["evidence_levels"][-1] == "primary_real_machine"

    gate = matrix["real_machine_gate"]
    assert gate == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "network_mode": "offline-confirmed",
        "commit_sha": "ddb58d041e505556910930724d0cf2fd03afe7d3",
        "completed_at": "2026-06-26T12:37:23.396078Z",
    }
    assert result["result"] == "pass"
    assert result["evidence_level"] == "real-machine"
    assert result["operating_system"] == "Darwin"
    assert result["architecture"] == "x86_64"
    assert result["python_version"] == "3.12.13"
    assert result["network_mode"] == "offline-confirmed"
    assert result["commit_sha"] == gate["commit_sha"]
    assert result["completed_at"] == gate["completed_at"]
    assert result["primary_intel_mac_gate"] == "pass"
    assert result["phase4b_gate_complete"] is True
    assert result["project_test_count"] == 12
    assert all(result["checks"].values())
    assert all(value is False for value in result["privacy"].values())


def test_resume_bundle_inspector_has_no_doll_or_third_party_import() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.partition(".")[0])

    assert imports.isdisjoint({"doll", "fastapi", "httpx", "pydantic", "typer"})
'''
    (ROOT / "tests/test_project_continuity_acceptance_static.py").write_text(
        static, encoding="utf-8"
    )


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- Phase 4A AI environment portability foundation;\n- IMP-001 through IMP-023;",
        "- Phase 4A AI environment portability foundation;\n- Phase 4B project continuity foundation;\n- IMP-001 through IMP-023;",
        "completed Phase 4B",
    )
    text = replace_once(
        text,
        "project-continuity transfer and recovery coverage, and automated Phase 4B acceptance evidence,",
        "project-continuity transfer and recovery coverage, and completed Phase 4B acceptance evidence,",
        "completed acceptance summary",
    )
    old_current = """- Phase 4B project continuity is now the active foundation phase;
- IMP-038 establishes Doll State Package format v2 for new exports while preserving supported format v1 inspection, verification, planning, and import;
- IMP-039 adds the versioned authoritative record registry used by package export, manifest validation, typed-validator selection, and source-version inventory checks;
- IMP-040 adds ProjectRecord v2 charters and preserves neutral ProjectRecord v1 read compatibility;
- IMP-041 adds WorkItemRecord v1 lifecycle, dependency, blocker, acceptance-criterion, and verification-state integrity;
- IMP-042 adds ProcedureRecord v1 lifecycle, versioning, validation, rollback description, and non-authority guarantees;
- IMP-043 adds ProjectCheckpointRecord v1 basis revisions, deterministic fingerprinting, trusted confirmation, and stale detection;
- IMP-044 adds deterministic read-only derived project status and fresh-process CLI inspection;
- IMP-045 adds deterministic project-scoped Resume Bundle export, generated HANDOFF.md, and checksum verification;
- IMP-046 adds integrated package, backup, restore, fresh-process, imported-content, compatibility, and secret-safe output coverage for project continuity;
- IMP-047 adds automated PROJ-001 through PROJ-012 acceptance evidence, an independent Resume Bundle inspector, and an exact-commit primary Intel Mac offline runner;
- the primary Intel Mac offline gate remains pending;
- no Phase 5 implementation identifier is assigned until Phase 4B passes;
- local model execution begins only after Phase 4B passes."""
    new_current = """- Phase 4B passed its project-continuity gate on 2026-06-26;
- accepted Phase 4B real-machine evidence is bound to commit `ddb58d041e505556910930724d0cf2fd03afe7d3` on the primary Intel Mac with networking disabled;
- IMP-038 through IMP-047 establish package-v2 continuity, authoritative project records, deterministic status and Resume Bundles, transfer and recovery coverage, and accepted PROJ-001 through PROJ-012 evidence;
- Phase 5 local runtime and model integration is now the next foundation phase;
- the first bounded Phase 5 implementation issue receives IMP-048 when opened;
- model execution must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts."""
    text = replace_once(text, old_current, new_current, "current implementation point")
    text = replace_once(
        text,
        "Status: automated acceptance evidence implemented through IMP-047; primary Intel Mac gate pending.",
        "Status: complete through IMP-047.",
        "Phase 4B status",
    )
    text = replace_once(
        text,
        """Remaining gate step:

1. Run the exact merged `main` commit on the primary Intel Mac with networking disabled, store the accepted result in a separate completion PR, and only then mark Phase 4B complete.""",
        """Accepted Phase 4B evidence:

- merged implementation commit: `ddb58d041e505556910930724d0cf2fd03afe7d3`;
- Ubuntu, macOS, and Windows CI passed before the accepted real-machine run;
- the primary Intel Mac run passed on Darwin `x86_64`, Python 3.12.13, with networking disabled;
- all declared PROJ-001 through PROJ-012 checks passed;
- the accepted report returned `phase4b_gate_complete = true`;
- the stored result contains no private path, username, hostname, credential, secret value, fixture content, or personal project data.

Phase 4B gate status: passed on 2026-06-26.""",
        "accepted Phase 4B evidence",
    )
    text = replace_once(
        text,
        """The required order after the Phase 4A gate is:

1. merge the pending IMP-047 automated Phase 4B acceptance evidence without claiming the phase complete;
2. run the exact merged `main` commit on the primary Intel Mac with networking disabled;
3. store the accepted real-machine result in a separate completion PR and mark Phase 4B complete;
4. schedule local runtime and model integration slices with the next monotonic identifiers only after the Phase 4B gate passes;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.""",
        """The required order after the Phase 4B gate is:

1. schedule the bounded Phase 5 runtime-adapter contract as IMP-048;
2. implement normalized runtime health, inventory, generation, streaming, cancellation, offline, and capability contracts without granting model authority;
3. implement the first local runtime adapter, initially targeting Ollama, with no silent model download or cloud fallback;
4. prove network-disabled startup, local conversation, project-state inspection, model replacement, fallback, and rollback without state loss;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.""",
        "immediate work",
    )
    path.write_text(text, encoding="utf-8")


def update_public_status() -> None:
    status = {
        "schema_version": 2,
        "maturity": "Pre-alpha",
        "completed_phases": ["0", "1", "2", "3", "4A", "4B"],
        "phase": {
            "id": "5",
            "name": "Local runtime and model integration",
            "state": "ready",
            "started_by_implementation": None,
            "next_implementation": 48,
        },
        "model_runtime": {
            "connected": False,
            "message": "Phase 4B is complete. No model runtime is connected yet; bounded Phase 5 local-runtime work is ready to begin.",
        },
        "last_reviewed": "2026-06-26",
    }
    (ROOT / "website/project-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )


def update_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''Array.isArray(status.completed_phases) && status.completed_phases.includes("4A"),
  "project-status.json must record completed phases through Phase 4A",''',
        '''Array.isArray(status.completed_phases) && status.completed_phases.includes("4B"),
  "project-status.json must record completed phases through Phase 4B",''',
        "completed public phase",
    )
    text = replace_once(
        text,
        '''status.phase?.id === "4B" &&
    status.phase?.name === "Project continuity foundation" &&
    status.phase?.state === "in_progress" &&
    status.phase?.started_by_implementation === 38 &&
    status.phase?.next_implementation === 47,
  "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-047 next",''',
        '''status.phase?.id === "5" &&
    status.phase?.name === "Local runtime and model integration" &&
    status.phase?.state === "ready" &&
    status.phase?.started_by_implementation === null &&
    status.phase?.next_implementation === 48,
  "project-status.json must mark Phase 5 ready with IMP-048 next",''',
        "public Phase 5 status",
    )
    text = replace_once(
        text,
        '''    'data-roadmap-phase="4B"',
    "data-roadmap-state",''',
        '''    'data-roadmap-phase="4B"',
    'data-roadmap-phase="5"',
    "data-roadmap-state",''',
        "Phase 5 roadmap marker",
    )
    text = replace_once(
        text,
        '''expect(
  roadmap.includes("the primary Intel Mac offline gate remains pending"),
  "roadmap must keep the IMP-047 primary-machine gate pending",
);
expect(
  roadmap.includes("no Phase 5 implementation identifier is assigned until Phase 4B passes"),
  "roadmap must keep Phase 5 blocked until Phase 4B passes",
);''',
        '''expect(
  roadmap.includes("Phase 4B gate status: passed on 2026-06-26."),
  "roadmap must record the accepted Phase 4B gate",
);
expect(
  roadmap.includes("the first bounded Phase 5 implementation issue receives IMP-048 when opened"),
  "roadmap must identify IMP-048 as the next implementation identifier",
);''',
        "Phase 4B checker gate",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    validate_result()
    update_matrix()
    update_acceptance_doc()
    update_tests()
    update_roadmap()
    update_public_status()
    update_checker()


if __name__ == "__main__":
    main()
