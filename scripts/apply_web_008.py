#!/usr/bin/env python3
"""Apply the one-time WEB-008 roadmap and numbering migration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs/spec/09-development-roadmap.md"
README = ROOT / "README.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one old block, found {count}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    text = ROADMAP.read_text(encoding="utf-8")

    text = replace_once(
        text,
        """Completed:

- Phase 0 specification baseline, subject to controlled specification changes;
- Phase 1 local state foundation;
- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;
- Phase 3 model-independent safety boundary;
- IMP-001 through IMP-023;
- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, secret classification and redaction, secret-safe audit and logging, external secret-store contracts, credential brokering, claim and evidence separation, instruction-origin authority, prompt-injection defense, capability taxonomy, fixed risk tiers, authorization preflight, mandatory high-risk confirmation, and safety acceptance evidence.

Current implementation point:

- Phase 3 is complete;
- IMP-023 passed cross-platform CI and the primary Intel Mac offline real-process gate at main commit `22e78b09ba0c144c2cddc918992d52f845c30185`;
- Phase 4A and Phase 4B are the next model-independent implementation foundations;
- the first scheduled Phase 4 slice receives the next non-conflicting implementation identifier;
- IMP-024 remains blocked until both Phase 4 foundation gates pass;
- local model execution begins only after both Phase 4 foundations.

The controlled specification-set 0.2 change does not reopen completed implementation evidence. It changes future requirements and sequencing.
""",
        """Completed:

- Phase 0 specification baseline, subject to controlled specification changes;
- Phase 1 local state foundation;
- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;
- Phase 3 model-independent safety boundary;
- IMP-001 through IMP-023;
- IMP-030 and IMP-031;
- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, secret classification and redaction, secret-safe audit and logging, external secret-store contracts, credential brokering, claim and evidence separation, instruction-origin authority, prompt-injection defense, capability taxonomy, fixed risk tiers, authorization preflight, mandatory high-risk confirmation, safety acceptance evidence, canonical conversation and event contracts, and canonical conversation and event persistence.

Current implementation point:

- Phase 4A is in progress;
- IMP-030 established provider-independent canonical conversation and event contracts;
- IMP-031 persisted those contracts through the existing Doll State record envelope and read-only reopen path;
- IMP-032 is the next planned implementation identifier for source and target adapter contracts and the source-environment manifest foundation;
- Phase 4B follows the Phase 4A portability gate;
- local model execution begins only after both Phase 4 foundations.

Implementation identifier policy:

- merged implementation identifiers never change;
- new implementation identifiers increase monotonically from IMP-030 onward;
- unused legacy reservations IMP-024 through IMP-029 are retired permanently and must not be reused;
- unscheduled roadmap slices do not reserve identifiers and receive the next monotonic identifier only when an implementation issue is opened.

The controlled specification-set 0.2 change does not reopen completed implementation evidence. It changes future requirements and sequencing.
""",
        "current implementation state",
    )

    text = replace_once(
        text,
        """This phase is model-independent and uses synthetic fixtures.

Required implementation slices, with identifiers assigned only when scheduled:

1. canonical ConversationRecord and extensible ConversationEventRecord schemas;
2. SourceEnvironmentRecord, ImportBatchRecord, MappingReportRecord, PortabilityLossRecord, and ExportBatchRecord;
3. source-adapter and target-adapter contracts;
4. generic JSON or JSONL import staging;
5. generic JSON, JSONL, Markdown, manifest, checksum, and managed-file export;
6. original-source hash and optional managed snapshot;
7. deterministic mapping, provenance, idempotency, conflict, and quarantine behavior;
8. mapping and loss reports;
9. imported-content authority restrictions;
10. PORT-004 through PORT-012 acceptance evidence.
""",
        """This phase is model-independent and uses synthetic fixtures.

Completed implementation slices:

- IMP-030 — canonical ConversationRecord and extensible ConversationEventRecord schemas;
- IMP-031 — canonical conversation and event persistence through the generic Doll State record envelope.

Next planned implementation slice:

- IMP-032 — source and target adapter contracts and the SourceEnvironmentRecord manifest foundation.

Remaining required slices, with identifiers assigned only when scheduled:

1. ImportBatchRecord, MappingReportRecord, PortabilityLossRecord, and ExportBatchRecord;
2. generic JSON or JSONL import staging;
3. generic JSON, JSONL, Markdown, manifest, checksum, and managed-file export;
4. original-source hash and optional managed snapshot;
5. deterministic mapping, provenance, idempotency, conflict, and quarantine behavior;
6. mapping and loss reports;
7. imported-content authority restrictions;
8. PORT-004 through PORT-012 acceptance evidence.
""",
        "Phase 4A slices",
    )

    text = replace_once(
        text,
        """Existing implementation identifiers remain unchanged.

### IMP-024 — Runtime adapter contract

Implement normalized health, inventory, generation, streaming, cancellation, error, offline, and capability contracts with runtime-independent model identity and no direct authority over state, secrets, files, network, capabilities, or project completion.

### IMP-025 — First local runtime adapter

Initial target: Ollama.

Implement local health, inventory mapping, generation, streaming, timeout, cancellation, no silent download, no cloud fallback, and context flow through accepted secret and origin controls.

### IMP-026 — Model manifests and bindings

Implement ModelManifestRecord, RuntimeManifestRecord, ModelBindingRecord, provenance, exact revision, checksums, license, compatibility, quarantine, candidate, active, previous, fallback, and rollback state.

### IMP-027 — Canonical local conversation path

Implement local API and CLI conversation using only the Phase 4A canonical conversation and event records and Phase 4B project-continuity views where requested.

Required properties:

- scoped state retrieval;
- response provenance;
- separate provider, application, interface, runtime, model, and operation attribution;
- no provider-native object as authoritative state;
- no automatic durable memory creation;
- no direct model capability execution;
- no automatic work completion, procedure approval, blocker clearing, or checkpoint confirmation;
- model proposals pass through the safety boundary.

### IMP-028 — Model switch and local fallback

Implement explicit activation, previous binding retention, fallback selection or offer, smoke-test rollback, no unrelated state rewrite, and no cloud request.

### IMP-029 — Offline mode and local AI continuity drill

Prove network-disabled startup, outbound-request guard, local conversation, project-state inspection, fallback, model replacement without state loss, and primary-machine evidence.
""",
        """The following work retains its required order but does not reserve implementation identifiers. Each slice receives the next monotonic IMP identifier only after the Phase 4A and Phase 4B gates pass and the slice is scheduled. The unused identifiers IMP-024 through IMP-029 are retired and must not be reused.

### Runtime adapter contract

Implement normalized health, inventory, generation, streaming, cancellation, error, offline, and capability contracts with runtime-independent model identity and no direct authority over state, secrets, files, network, capabilities, or project completion.

### First local runtime adapter

Initial target: Ollama.

Implement local health, inventory mapping, generation, streaming, timeout, cancellation, no silent download, no cloud fallback, and context flow through accepted secret and origin controls.

### Model manifests and bindings

Implement ModelManifestRecord, RuntimeManifestRecord, ModelBindingRecord, provenance, exact revision, checksums, license, compatibility, quarantine, candidate, active, previous, fallback, and rollback state.

### Canonical local conversation path

Implement local API and CLI conversation using only the Phase 4A canonical conversation and event records and Phase 4B project-continuity views where requested.

Required properties:

- scoped state retrieval;
- response provenance;
- separate provider, application, interface, runtime, model, and operation attribution;
- no provider-native object as authoritative state;
- no automatic durable memory creation;
- no direct model capability execution;
- no automatic work completion, procedure approval, blocker clearing, or checkpoint confirmation;
- model proposals pass through the safety boundary.

### Model switch and local fallback

Implement explicit activation, previous binding retention, fallback selection or offer, smoke-test rollback, no unrelated state rewrite, and no cloud request.

### Offline mode and local AI continuity drill

Prove network-disabled startup, outbound-request guard, local conversation, project-state inspection, fallback, model replacement without state loss, and primary-machine evidence.
""",
        "Phase 5 identifiers",
    )

    text = replace_once(
        text,
        """A PR should normally implement one issue or one tightly related slice.

Documentation-only sequencing changes must not include implementation code.
""",
        """A PR should normally implement one issue or one tightly related slice.

Implementation identifiers follow a monotonic allocation rule:

- the next implementation issue after IMP-031 is IMP-032;
- every later implementation issue receives the next integer greater than all previously assigned IMP identifiers;
- retired identifiers IMP-024 through IMP-029 remain unused permanently;
- roadmap entries do not reserve identifiers before an implementation issue is opened;
- merged issues, pull requests, commits, and implementation records are never renumbered.

Documentation-only sequencing changes must not include implementation code.
""",
        "issue numbering discipline",
    )

    text = replace_once(
        text,
        """## 18. Immediate work

The required order after IMP-021 is:

1. create and implement IMP-022 only;
2. continue IMP-023;
3. pass the Phase 3 safety gate;
4. schedule Phase 4A portability-foundation issues with new non-conflicting identifiers;
5. pass the Phase 4A portability gate;
6. schedule Phase 4B package-v2 and project-continuity issues with new non-conflicting identifiers;
7. pass the Phase 4B project-continuity gate;
8. begin IMP-024 through IMP-029 local model work;
9. prove a real local AI migration path before provider-specific cloud portability becomes a
   primary claim.
""",
        """## 18. Immediate work

The required order after IMP-031 is:

1. implement IMP-032 as the source and target adapter-contract and source-environment manifest foundation;
2. continue the remaining Phase 4A portability slices with monotonically increasing identifiers;
3. pass the Phase 4A portability gate;
4. schedule Phase 4B package-v2 and project-continuity slices with the next monotonic identifiers;
5. pass the Phase 4B project-continuity gate;
6. schedule local runtime and model integration slices with the next monotonic identifiers;
7. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.
""",
        "immediate work",
    )

    ROADMAP.write_text(text, encoding="utf-8", newline="\n")


def update_readme() -> None:
    text = README.read_text(encoding="utf-8")
    old = "The safety-boundary implementation sequence runs through IMP-023. The current position is derived from merged and open `IMP-*` work and published through the [live implementation activity endpoint](https://doll.badjoke-lab.com/api/project-status). Phase 4A then establishes canonical conversation, adapter, generic import/export, provenance, idempotency, quarantine, and loss-report contracts. Phase 4B establishes Doll State Package v2, ProjectRecord v2, WorkItemRecord, ProcedureRecord, ProjectCheckpointRecord, deterministic status, Resume Bundle, and PROJ acceptance. Existing local model work remains IMP-024 through IMP-029 after those gates."
    new = "The safety-boundary implementation sequence runs through IMP-023. Phase 4A is now in progress: IMP-030 established canonical conversation and event contracts, IMP-031 added their persistence, and IMP-032 is the next planned adapter-contract and source-environment foundation. The current position is published through the [live implementation activity endpoint](https://doll.badjoke-lab.com/api/project-status). Phase 4B then establishes Doll State Package v2, ProjectRecord v2, WorkItemRecord, ProcedureRecord, ProjectCheckpointRecord, deterministic status, Resume Bundle, and PROJ acceptance. Local runtime and model work follows both Phase 4 gates and receives the next monotonic implementation identifiers when scheduled. Unused legacy identifiers IMP-024 through IMP-029 are retired and are not reused."
    text = replace_once(text, old, new, "README implementation sequence")
    README.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    update_roadmap()
    update_readme()


if __name__ == "__main__":
    main()
