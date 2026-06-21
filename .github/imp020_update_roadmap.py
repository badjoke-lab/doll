from __future__ import annotations

from pathlib import Path

ROADMAP = Path("docs/spec/09-development-roadmap.md")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one roadmap value, found {count}: {old[:60]}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


text = ROADMAP.read_text(encoding="utf-8")
text = replace_once(text, "- IMP-001 through IMP-014;", "- IMP-001 through IMP-020;")
text = replace_once(
    text,
    "- local workspace, SQLite state, migrations, audit, managed artifacts, preferences, "
    "policies, permissions, confirmed memory, projects, decisions, state-package "
    "export/import, verified backup, restore, continuity acceptance, secret-classification "
    "enforcement, bounded secret detection, deterministic redaction, and secret-safe diagnostics.",
    "- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, "
    "permissions, confirmed memory, projects, decisions, state-package export/import, verified "
    "backup, restore, continuity acceptance, secret classification and redaction, secret-safe "
    "audit and logging, external secret-store contracts, credential brokering, claim and evidence "
    "separation, instruction-origin authority, and prompt-injection defense.",
)
text = replace_once(
    text,
    "- IMP-014 is complete;\n- IMP-015 is the next implementation item;\n"
    "- IMP-015 through IMP-023 complete and validate the remaining safety boundary;",
    "- IMP-020 is complete;\n- IMP-021 is the next implementation item;\n"
    "- IMP-021 through IMP-023 complete and validate the remaining safety boundary;",
)

phase3 = """### IMP-015 — Secret-Safe Audit and Logging

Status: complete.

Implemented centrally enforced secret-safe audit construction, bounded summaries and metadata,
control-character defenses, private-environment minimization, safe exceptional paths, and
failure-preserving tests.

### IMP-016 — External Secret Store Contract

Status: complete.

Implemented a replaceable secret-store contract with non-secret references, adapter capabilities,
availability and lock state, user-presence requirements, lifecycle operations, validation,
failure isolation, and synthetic in-memory acceptance fixtures.

### IMP-017 — Credential Broker

Status: complete.

Implemented bounded credential use without returning stored values to models or ordinary callers,
with exact reference, destination, scope, purpose, approval, timeout, cancellation, result, audit,
and failure controls.

### IMP-018 — Claim, Evidence, and Trust Model

Status: complete.

Implemented separate confirmed facts, claims, evidence, and inferences with immutable provenance,
confidence, uncertainty, review state, explicit support and contradiction links, and no automatic
import-to-fact promotion.

### IMP-019 — Instruction Origin and Untrusted-Content Boundary

Status: complete.

Implemented immutable source attribution, origin-derived authority classes, data-only treatment
for external, imported, tool, runtime, model, and unknown content, stale durable-policy downgrade,
non-escalating derivation links, structured context channels, and state-package validation.

### IMP-020 — Prompt Injection Defense

Status: complete.

Implemented bounded advisory indicators that retain no matched content, secret-safe
complete-or-fail context packaging, structural origin-channel separation, archive and stale-policy
downgrade preservation, external authorization guards based only on IMP-019, hostile-source and
exfiltration fixtures, unrelated-capability defenses, and no model-only authorization boundary.
"""
text = replace_between(
    text,
    "### IMP-015 — Secret-Safe Audit and Logging",
    "### IMP-021 — Capability Taxonomy and Risk Tiers",
    phase3,
)

immediate = """## 18. Immediate work

The required order after IMP-020 is:

1. create and implement IMP-021 only;
2. continue IMP-022 and IMP-023 in order;
3. pass the Phase 3 safety gate;
4. schedule Phase 4A portability-foundation issues with new non-conflicting identifiers;
5. pass the Phase 4A portability gate;
6. schedule Phase 4B package-v2 and project-continuity issues with new non-conflicting identifiers;
7. pass the Phase 4B project-continuity gate;
8. begin IMP-024 through IMP-029 local model work;
9. prove a real local AI migration path before provider-specific cloud portability becomes a
   primary claim.
"""
text = replace_between(text, "## 18. Immediate work", "## 19. Roadmap change control", immediate)
ROADMAP.write_text(text, encoding="utf-8", newline="\n")
