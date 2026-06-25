from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path


def test_emit_phase4a_completed_roadmap_and_spec() -> None:
    roadmap = Path("docs/spec/09-development-roadmap.md")
    text = roadmap.read_text(encoding="utf-8")

    old_current = """Completed:

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
"""
    new_current = """Completed:

- Phase 0 specification baseline, subject to controlled specification changes;
- Phase 1 local state foundation;
- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;
- Phase 3 model-independent safety boundary;
- Phase 4A AI environment portability foundation;
- IMP-001 through IMP-023;
- IMP-030 through IMP-037;
- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, the model-independent safety boundary, canonical conversation and event state, portability adapter and result records, generic import staging, generic export, reviewed publication, source preservation, idempotency, loss visibility, and Phase 4A acceptance evidence.

Current implementation point:

- Phase 4A passed its generic portability gate on 2026-06-25;
- accepted real-machine evidence is bound to commit `839a4ca7a37753fadf81c3e8e79f140e6d66bc03` on the primary Intel Mac with networking disabled;
- Phase 4B project continuity is now the active foundation phase;
- the next implementation issue receives IMP-038 when its first bounded Phase 4B slice is scheduled;
- local model execution begins only after Phase 4B passes.
"""

    old_phase = """Completed implementation slices:

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

Phase 4A gate:

- canonical state is independent of provider-native and runtime-native response objects;
- provider, application, interface, runtime, and model identity are separate;
- generic export is inspectable without a model or preferred UI;
- repeated import is idempotent for unchanged source objects;
- material transformation and loss are explicit;
- imported content cannot become policy, permission, confirmation, capability, confirmed memory, confirmed fact, approved procedure, confirmed checkpoint, or completed work automatically;
- CI passes on macOS, Windows, and Ubuntu;
- no provider-specific cloud adapter is required.
"""
    new_phase = """Status: complete through IMP-037.

Completed implementation slices:

- IMP-030 — canonical ConversationRecord and extensible ConversationEventRecord schemas;
- IMP-031 — canonical conversation and event persistence through the generic Doll State record envelope;
- IMP-032 — source and target adapter contracts and SourceEnvironmentRecord;
- IMP-033 — portability batch, mapping, loss, export, and preservation result contracts;
- IMP-034 — generic JSON and JSONL import staging;
- IMP-035 — deterministic generic JSON, JSONL, Markdown, manifest, checksum, and managed-file export;
- IMP-036 — reviewed canonical publication, original-source preservation, deterministic mapping, idempotency, conflict handling, quarantine, loss reporting, and imported-content authority restrictions;
- IMP-037 — PORT-004 through PORT-012 automated and primary Intel Mac acceptance evidence.

Accepted Phase 4A evidence:

- merged implementation commit: `839a4ca7a37753fadf81c3e8e79f140e6d66bc03`;
- Ubuntu, macOS, and Windows CI passed with 859 tests and 95.14% total coverage;
- the primary Intel Mac run passed on Darwin `x86_64`, Python 3.12.13, with networking disabled;
- all declared PORT-004 through PORT-012 checks passed;
- the accepted report returned `phase4a_gate_complete = true`;
- the stored result contains no private path, username, hostname, credential, secret value, fixture content, or personal conversation data;
- PORT-001 through PORT-003 and PORT-013 through PORT-016 remain future portability work;
- stable anti-lock-in remains unclaimed until PORT-015 passes.

Phase 4A gate status: passed on 2026-06-25.

Phase 4A gate:

- canonical state is independent of provider-native and runtime-native response objects;
- provider, application, interface, runtime, and model identity are separate;
- generic export is inspectable without a model or preferred UI;
- repeated import is idempotent for unchanged source objects;
- material transformation and loss are explicit;
- imported content cannot become policy, permission, confirmation, capability, confirmed memory, confirmed fact, approved procedure, confirmed checkpoint, or completed work automatically;
- CI passes on macOS, Windows, and Ubuntu;
- the primary Intel Mac offline acceptance run passes;
- no provider-specific cloud adapter is required.
"""

    old_issue_rule = "- the next implementation issue after IMP-031 is IMP-032;"
    new_issue_rule = "- the next implementation issue after IMP-037 is IMP-038;"

    old_immediate = """The required order after IMP-031 is:

1. implement IMP-032 as the source and target adapter-contract and source-environment manifest foundation;
2. continue the remaining Phase 4A portability slices with monotonically increasing identifiers;
3. pass the Phase 4A portability gate;
4. schedule Phase 4B package-v2 and project-continuity slices with the next monotonic identifiers;
5. pass the Phase 4B project-continuity gate;
6. schedule local runtime and model integration slices with the next monotonic identifiers;
7. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.
"""
    new_immediate = """The required order after the Phase 4A gate is:

1. schedule the first bounded Phase 4B package-v2 and project-continuity slice as IMP-038;
2. continue Phase 4B with monotonically increasing identifiers;
3. pass the Phase 4B project-continuity gate;
4. schedule local runtime and model integration slices with the next monotonic identifiers;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.
"""

    for old in (old_current, old_phase, old_issue_rule, old_immediate):
        assert old in text
    text = text.replace(old_current, new_current)
    text = text.replace(old_phase, new_phase)
    text = text.replace(old_issue_rule, new_issue_rule)
    text = text.replace(old_immediate, new_immediate)
    roadmap.write_text(text, encoding="utf-8", newline="\n")

    subprocess.run([sys.executable, "scripts/build_final_spec.py"], check=True)
    outputs = {
        "docs/spec/09-development-roadmap.md": roadmap.read_bytes(),
        "DOLL_FINAL_SPEC.md": Path("DOLL_FINAL_SPEC.md").read_bytes(),
    }
    lines: list[str] = []
    for name, content in outputs.items():
        lines.extend((f"BEGIN:{name}", base64.b64encode(content).decode(), f"END:{name}"))
    raise AssertionError("\n".join(lines))
