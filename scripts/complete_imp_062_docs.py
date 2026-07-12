"""Apply the deterministic documentation and status completion for IMP-062."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def update_matrix() -> None:
    path = ROOT / "docs/testing/phase-6-local-portability-matrix.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    extension = data.get("context_replay_extension")
    if not isinstance(extension, dict):
        raise RuntimeError("context_replay_extension is missing")
    if extension.get("acceptance_implementation") != "IMP-062":
        raise RuntimeError("IMP-062 acceptance binding is missing")
    extension["implementation_doc"] = (
        "docs/implementation/"
        "imp-062-imported-context-replay-real-machine-acceptance.md"
    )
    extension["runbook"] = "docs/testing/imp-062-primary-intel-mac-runbook.md"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_status() -> None:
    path = ROOT / "website/project-status.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    phase = data.get("phase")
    if not isinstance(phase, dict):
        raise RuntimeError("project phase is missing")
    if phase.get("next_implementation") != 62:
        raise RuntimeError("expected IMP-062 as current next implementation")
    phase["next_implementation"] = 63
    model_runtime = data.get("model_runtime")
    if not isinstance(model_runtime, dict):
        raise RuntimeError("model_runtime is missing")
    model_runtime["message"] = (
        "Phase 6 is in progress through IMP-062. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, the bounded "
        "selected-history ChatGPT source path, numbered ChatGPT conversation-member "
        "aggregation, bounded imported conversation context replay, and its "
        "exact-commit primary Intel Mac acceptance harness are implemented. "
        "PORT-001, PORT-003, the bounded IMP-057 portion of PORT-013, PORT-014, "
        "and PORT-015 retain their accepted evidence. The IMP-061/IMP-062 "
        "cross-runtime replay extension remains CI-only until a separate "
        "privacy-reviewed primary Intel Mac result is accepted. The complete "
        "Phase 6 gate, target-specific application replacement, and stable "
        "general anti-lock-in remain incomplete."
    )
    data["last_reviewed"] = "2026-07-12"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- IMP-030 through IMP-061;",
        "- IMP-030 through IMP-062;",
        "completed implementation range",
    )
    text = replace_once(
        text,
        "and bounded imported conversation context replay through IMP-061.",
        "bounded imported conversation context replay through IMP-061, and the "
        "exact-commit imported-context replay real-machine acceptance harness "
        "through IMP-062.",
        "completed implementation summary",
    )
    text = replace_once(
        text,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-061;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-062;",
        "current Phase 6 implementation point",
    )
    text = replace_once(
        text,
        """- IMP-061 adds bounded replay of explicitly selected imported canonical text events through accepted source mappings, data-only imported instruction origins, the existing prompt-defense boundary, and a distinct approved synthetic local target runtime;
- IMP-061 is assigned to Issue #198;
- the IMP-061 cross-runtime replay extension is `ci-pass`; separate exact-commit primary Intel Mac evidence remains required before any broader real-machine cross-runtime replay claim;
- the next bounded implementation receives IMP-062 only when a new implementation issue is opened;
""",
        """- IMP-061 adds bounded replay of explicitly selected imported canonical text events through accepted source mappings, data-only imported instruction origins, the existing prompt-defense boundary, and a distinct approved synthetic local target runtime;
- IMP-061 is assigned to Issue #198;
- IMP-062 adds an exact-commit primary Intel Mac acceptance runner, deterministic synthetic ChatGPT-format source, injected no-socket CI mode, fixed-loopback real Ollama mode, strict privacy-safe evidence schema, and a private-machine runbook for the IMP-061 replay extension;
- IMP-062 is assigned to Issue #200;
- the IMP-061/IMP-062 cross-runtime replay extension remains `ci-pass`; separate exact-commit privacy-reviewed primary Intel Mac evidence remains required before a real-machine cross-runtime replay claim;
- the next bounded implementation receives IMP-063 only when a new implementation issue is opened;
""",
        "current IMP-062 allocation",
    )
    text = replace_once(
        text,
        "Status: implemented with deterministic synthetic CI evidence; separate exact-commit primary Intel Mac cross-runtime replay evidence remains pending.",
        "Status: implemented with deterministic synthetic CI evidence; IMP-062 provides the exact-commit primary Intel Mac acceptance path, and accepted real-machine evidence remains pending.",
        "IMP-061 status",
    )
    text = replace_once(
        text,
        """IMP-061 does not establish automatic or semantic retrieval, embeddings, vector search, model-selected context, attachment-byte or multimodal replay, tool or capability execution, native application history discovery, target-specific export, provider round-trip fidelity, cloud portability, automatic cloud fallback, runtime installation, model download, full application replacement, the complete Phase 6 gate, or stable general anti-lock-in.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.
""",
        """IMP-061 does not establish automatic or semantic retrieval, embeddings, vector search, model-selected context, attachment-byte or multimodal replay, tool or capability execution, native application history discovery, target-specific export, provider round-trip fidelity, cloud portability, automatic cloud fallback, runtime installation, model download, full application replacement, the complete Phase 6 gate, or stable general anti-lock-in.

### IMP-062 — Primary Intel Mac imported-context replay acceptance

Status: acceptance infrastructure implemented with deterministic synthetic CI evidence; separate exact-commit primary Intel Mac execution and privacy-safe evidence acceptance remain pending.

Implemented a bounded acceptance probe and runner for the IMP-061 imported-context replay path. The probe generates a deterministic non-private synthetic ChatGPT-format source, publishes it through the accepted ChatGPT and generic publication boundaries, explicitly selects two imported canonical text events, and replays them into a distinct explicitly bound Ollama target conversation.

Imported context remains immutable `imported_data`, `untrusted_data`, and data-only. It reaches the runtime only through `untrusted_content`, cannot authorize `task_instruction`, cannot select the target binding, and cannot create policy, permission, capability, credential, confirmed memory, trusted fact, project state, work completion, procedure approval, checkpoint confirmation, or another model binding. Prompt-injection findings remain advisory and the canonical target turn continues to use the accepted user, context-snapshot, and assistant event graph.

CI mode uses an injected deterministic Ollama transport and performs no socket operation. Real-machine mode requires the exact checked-out commit, Darwin on Intel, explicit operator-confirmed networking disabled, explicit local-only confirmation, one caller-selected already-installed local model, and fixed IPv4 loopback. A socket guard rejects every undeclared destination and the runner does not install or start a runtime, download a model, access a provider account, retrieve credentials, execute tools, or enable cloud fallback.

The content-free result schema includes only bounded platform facts, booleans, counts, hashes, runtime request counts, socket-attempt counts, and non-claim flags. It excludes native model names, source-native identifiers, source text, prompt text, model response text, private paths, usernames, hostnames, credentials, and secret values. The real-machine runbook writes the raw result outside the repository and requires manual privacy review before a separate completion pull request may accept evidence.

Dedicated synthetic acceptance passes on Ubuntu, macOS, and Windows. The context replay extension remains `ci-pass` until exact-commit primary Intel Mac evidence is executed and accepted separately.

IMP-062 does not establish native history discovery, automatic or semantic retrieval, embeddings, vector search, model-selected context, attachment-byte or multimodal replay, tool or capability execution, target-specific export, provider round-trip fidelity, runtime or model installation, cloud portability, automatic cloud fallback, complete application replacement, the complete Phase 6 gate, or stable general anti-lock-in.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.
""",
        "IMP-062 roadmap section",
    )
    text = replace_once(
        text,
        """After IMP-061 imported-context replay foundation, the immediate order is:

1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;
2. retain the accepted IMP-057 bounded PORT-013 evidence while recording the IMP-061 cross-runtime replay extension as `ci-pass` until separate exact-commit primary Intel Mac evidence is accepted;
3. allocate IMP-062 only when a new bounded implementation issue is opened; a primary Intel Mac cross-runtime replay drill, ZIP ingestion, attachment bytes, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;
4. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;
5. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.
""",
        """After IMP-062 imported-context replay real-machine acceptance infrastructure, the immediate order is:

1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;
2. retain the accepted IMP-057 bounded PORT-013 evidence while recording the IMP-061/IMP-062 cross-runtime replay extension as `ci-pass` until separate exact-commit privacy-reviewed primary Intel Mac evidence is accepted;
3. merge the IMP-062 implementation, execute its network-disabled primary Intel Mac run against the exact merged commit, and accept only a content-free privacy-reviewed result through a separate completion pull request;
4. allocate IMP-063 only when a new bounded implementation issue is opened; ZIP ingestion, attachment bytes, target-specific export, cloud credentials, tools, automatic cloud fallback, and unrelated daily-use features remain separate work;
5. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.
""",
        "immediate work",
    )
    path.write_text(text, encoding="utf-8")


def update_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """    status.phase?.started_by_implementation === 55 &&
    status.phase?.next_implementation === 62,
  "project-status.json must mark Phase 6 in progress through IMP-061 with IMP-062 next",
);
""",
        """    status.phase?.started_by_implementation === 55 &&
    status.phase?.next_implementation === 63,
  "project-status.json must mark Phase 6 in progress through IMP-062 with IMP-063 next",
);
""",
        "project status implementation point",
    )
    text = replace_once(
        text,
        """expect(
  localPortability.context_replay_extension?.implementation === "IMP-061" &&
    localPortability.context_replay_extension?.portability_test_id ===
      "PORT-013" &&
    localPortability.context_replay_extension?.status === "ci-pass" &&
    localPortability.context_replay_extension?.passed_evidence_levels?.length ===
      1 &&
    localPortability.context_replay_extension?.passed_evidence_levels?.[0] ===
      "ci" &&
    localPortability.context_replay_extension?.required_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.real_machine_gate_status ===
      "pending" &&
    localPortability.context_replay_extension?.phase6_gate_complete === false &&
    localPortability.context_replay_extension?.stable_anti_lock_in_claim === false,
  "IMP-061 context replay extension must remain CI-only until real-machine evidence",
);
""",
        """expect(
  localPortability.context_replay_extension?.implementation === "IMP-061" &&
    localPortability.context_replay_extension?.acceptance_implementation ===
      "IMP-062" &&
    localPortability.context_replay_extension?.portability_test_id ===
      "PORT-013" &&
    localPortability.context_replay_extension?.status === "ci-pass" &&
    localPortability.context_replay_extension?.passed_evidence_levels?.length ===
      1 &&
    localPortability.context_replay_extension?.passed_evidence_levels?.[0] ===
      "ci" &&
    localPortability.context_replay_extension?.required_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.accepted_real_machine_result ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate?.required ===
      true &&
    localPortability.context_replay_extension?.real_machine_gate?.status ===
      "pending" &&
    localPortability.context_replay_extension?.real_machine_gate?.commit_sha ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate?.completed_at ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate_status ===
      "pending" &&
    localPortability.context_replay_extension?.implementation_doc ===
      "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md" &&
    localPortability.context_replay_extension?.runbook ===
      "docs/testing/imp-062-primary-intel-mac-runbook.md" &&
    localPortability.context_replay_extension?.phase6_gate_complete === false &&
    localPortability.context_replay_extension?.stable_anti_lock_in_claim === false,
  "IMP-061/IMP-062 context replay extension must remain CI-only until accepted real-machine evidence",
);
""",
        "context replay extension checker",
    )
    text = replace_once(
        text,
        """expect(
  roadmap.includes("### IMP-061 — Bounded imported conversation context replay"),
  "roadmap must record the IMP-061 imported context replay boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-062 only when a new implementation issue is opened"),
  "roadmap must identify IMP-062 as the next unallocated implementation identifier",
);
""",
        """expect(
  roadmap.includes("### IMP-061 — Bounded imported conversation context replay"),
  "roadmap must record the IMP-061 imported context replay boundary",
);
expect(
  roadmap.includes("### IMP-062 — Primary Intel Mac imported-context replay acceptance"),
  "roadmap must record the IMP-062 real-machine acceptance boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-063 only when a new implementation issue is opened"),
  "roadmap must identify IMP-063 as the next unallocated implementation identifier",
);
""",
        "roadmap IMP-062 checker",
    )
    text = replace_once(
        text,
        """  roadmap.includes(
    "After IMP-061 imported-context replay foundation, the immediate order is:",
  ),
  "roadmap must record IMP-061 replay evidence boundary and remaining Phase 6 work",
);
""",
        """  roadmap.includes(
    "After IMP-062 imported-context replay real-machine acceptance infrastructure, the immediate order is:",
  ),
  "roadmap must record IMP-062 acceptance infrastructure and remaining Phase 6 work",
);
""",
        "immediate work checker",
    )
    path.write_text(text, encoding="utf-8")


def update_tests() -> None:
    path = ROOT / "tests/test_imp_062_imported_context_replay_acceptance.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'MATRIX = ROOT / "docs" / "testing" / "phase-6-local-portability-matrix.json"\nPRIVATE_MARKERS = (\n',
        'MATRIX = ROOT / "docs" / "testing" / "phase-6-local-portability-matrix.json"\nIMPLEMENTATION_DOC = (\n    ROOT\n    / "docs"\n    / "implementation"\n    / "imp-062-imported-context-replay-real-machine-acceptance.md"\n)\nRUNBOOK = ROOT / "docs" / "testing" / "imp-062-primary-intel-mac-runbook.md"\nPRIVATE_MARKERS = (\n',
        "test document constants",
    )
    text = replace_once(
        text,
        '    assert extension["accepted_real_machine_result"] is None\n    assert extension["real_machine_gate"] == {\n',
        '    assert extension["accepted_real_machine_result"] is None\n    assert extension["implementation_doc"] == (\n        "docs/implementation/"\n        "imp-062-imported-context-replay-real-machine-acceptance.md"\n    )\n    assert extension["runbook"] == (\n        "docs/testing/imp-062-primary-intel-mac-runbook.md"\n    )\n    assert IMPLEMENTATION_DOC.is_file()\n    assert RUNBOOK.is_file()\n    assert extension["real_machine_gate"] == {\n',
        "matrix document bindings",
    )
    if "def test_imp_062_runbook_keeps_private_execution_bounded()" not in text:
        text += '''\n\ndef test_imp_062_runbook_keeps_private_execution_bounded() -> None:\n    implementation = IMPLEMENTATION_DOC.read_text(encoding="utf-8")\n    runbook = RUNBOOK.read_text(encoding="utf-8")\n\n    assert "Primary Intel Mac imported-context replay acceptance" in implementation\n    assert "Synthetic CI mode" in implementation\n    assert "Real-machine mode" in implementation\n    assert "stable general anti-lock-in" in implementation\n\n    assert "--evidence-level real-machine" in runbook\n    assert "--offline-confirmed" in runbook\n    assert "--local-only-confirmed" in runbook\n    assert "IFS= read -r MODEL" in runbook\n    assert "mktemp -d" in runbook\n    assert "outside the repository" in runbook\n    assert "Manual privacy review" in runbook\n    assert "unset MODEL" in runbook\n    assert "phase6_gate_complete" in runbook\n    assert "stable_anti_lock_in_claim" in runbook\n'''
    path.write_text(text, encoding="utf-8")


def main() -> int:
    implementation_doc = (
        ROOT
        / "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md"
    )
    runbook = ROOT / "docs/testing/imp-062-primary-intel-mac-runbook.md"
    if not implementation_doc.is_file() or not runbook.is_file():
        raise RuntimeError("IMP-062 documentation files are missing")
    update_matrix()
    update_status()
    update_roadmap()
    update_checker()
    update_tests()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_final_spec.py")],
        cwd=ROOT,
        check=True,
    )
    print("IMP-062 documentation and status completion applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
