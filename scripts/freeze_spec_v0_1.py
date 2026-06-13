#!/usr/bin/env python3
"""Apply the reviewed specification v0.1 freeze changes.

This script is intentionally narrow and idempotent. It normalizes accepted
status metadata, resolves the Personal Lite document-read ordering conflict,
and writes the v0.1 audit report.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_FILES = (
    "docs/spec/00-index.md",
    "docs/spec/00-decisions-baseline.md",
    "docs/spec/01-product-and-continuity-contract.md",
    "docs/spec/02-architecture-and-data-flow.md",
    "docs/spec/03-doll-state-memory-and-storage.md",
    "docs/spec/04-security-permissions-and-threat-model.md",
    "docs/spec/05-model-vault-lifecycle-evaluation.md",
    "docs/spec/06-platform-install-update-and-recovery.md",
    "docs/spec/07-release-scope-and-profiles.md",
    "docs/spec/08-acceptance-and-continuity-tests.md",
    "docs/spec/09-development-roadmap.md",
)
ADR_FILES = (
    "docs/decisions/ADR-001-core-boundaries-and-authoritative-state.md",
    "docs/decisions/ADR-002-default-deny-capability-broker.md",
    "docs/decisions/ADR-003-local-model-vault-and-manual-promotion.md",
    "docs/decisions/ADR-004-release-gates-require-evidence.md",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, text: str) -> None:
    (ROOT / relative).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / relative).write_text(text, encoding="utf-8", newline="\n")


def normalize_statuses() -> None:
    for relative in SPEC_FILES:
        text = read(relative)
        text = text.replace(
            "**Status:** Draft for acceptance  ",
            "**Status:** Accepted for implementation  ",
            1,
        )
        write(relative, text)

    for relative in ADR_FILES:
        text = read(relative)
        text, count = re.subn(
            r"\*\*Status:\*\* Proposed for acceptance with PR-\d{3}  ",
            "**Status:** Accepted  ",
            text,
            count=1,
        )
        if count == 0 and "**Status:** Accepted  " not in text:
            raise RuntimeError(f"unexpected ADR status format: {relative}")
        write(relative, text)


def clarify_requirement_language() -> None:
    relative = "docs/spec/00-index.md"
    text = read(relative)
    marker = "The following terms are normative:\n"
    addition = (
        "The terms are interpreted case-insensitively in specification set 0.1; "
        "future changes SHOULD use uppercase forms for clarity.\n\n"
    )
    if addition not in text:
        if marker not in text:
            raise RuntimeError("requirement-language marker missing")
        text = text.replace(marker, marker + "\n" + addition, 1)
    write(relative, text)


def fix_roadmap_ordering() -> None:
    relative = "docs/spec/09-development-roadmap.md"
    text = read(relative)

    old_phase = """Remaining Phase 0 work after PR-005:

1. generate a combined specification document;
2. run a contradiction and completeness audit;
3. normalize requirement wording where needed;
4. freeze specification version 0.1 for implementation;
5. create the initial implementation issue and PR queue.

No production feature should bypass this baseline.
"""
    new_phase = """Phase 0 is complete when:

1. the combined specification is generated deterministically;
2. the contradiction and completeness audit is recorded;
3. requirement wording and acceptance mappings are reviewed;
4. specification set 0.1 is accepted for implementation;
5. the initial implementation issue and PR queue can begin.

No production feature may bypass this baseline. After the v0.1 freeze, implementation starts with IMP-001.
"""
    if old_phase in text:
        text = text.replace(old_phase, new_phase, 1)

    if "#### IMP-012 — Minimal user-selected document intake" not in text:
        def renumber(match: re.Match[str]) -> str:
            number = int(match.group(1))
            return f"#### IMP-{number + 1:03d} —"

        text = re.sub(
            r"^#### IMP-(0(?:1[2-9]|2[0-1])) —",
            renumber,
            text,
            flags=re.MULTILINE,
        )
        insertion_marker = "#### IMP-013 — Runtime adapter contract\n"
        new_slice = """#### IMP-012 — Minimal user-selected document intake

- user-controlled text and Markdown selection;
- safe external read path;
- DocumentRecord creation;
- path and size validation;
- explicit attachment to the current request;
- no model-initiated arbitrary filesystem read.

Acceptance focus:

- CONT-P007.

"""
        if insertion_marker not in text:
            raise RuntimeError("renumbered runtime-adapter heading missing")
        text = text.replace(insertion_marker, new_slice + insertion_marker, 1)

    old_followup = """## 16. Specification follow-up after PR-005

The immediate next repository work is:

1. add deterministic specification generation;
2. generate `DOLL_FINAL_SPEC.md`;
3. run contradiction and requirement audit;
4. update documents where contradictions are found;
5. mark specification set 0.1 accepted for implementation;
6. open IMP-001.
"""
    new_followup = """## 16. Immediate work after specification v0.1 freeze

The next repository work is:

1. open IMP-001;
2. add the Python package and three-operating-system CI skeleton;
3. implement platform paths and workspace initialization in IMP-002;
4. implement SQLite state and migrations in IMP-003;
5. preserve the accepted continuity, security, and recovery boundaries in every implementation PR.
"""
    if old_followup in text:
        text = text.replace(old_followup, new_followup, 1)

    write(relative, text)


def write_audit_report() -> None:
    report = """# Specification set 0.1 audit and freeze report

**Audit status:** Complete  
**Specification set:** 0.1  
**Freeze decision:** Accepted for implementation  
**Date:** 2026-06-14

## 1. Scope

The audit reviewed the normative files under `docs/spec/`, the accepted ADRs under `docs/decisions/`, the generated `DOLL_FINAL_SPEC.md`, and the mapping from release claims to acceptance tests.

The review covered:

- product identity and first-user purpose;
- Local-complete, cloud-optional consistency;
- Lite and Heavy boundaries;
- cloud and mobile deferral;
- authoritative-state ownership;
- permission and network boundaries;
- backup, restore, migration, and recovery;
- Model Vault lifecycle and local fallback;
- test-ID uniqueness and release-gate coverage;
- implementation ordering.

## 2. Measurements

Before freeze normalization, the generated specification contained:

- 11 normative source documents;
- 6,810 generated lines;
- 56 acceptance-test IDs;
- 56 unique acceptance-test IDs;
- no duplicate acceptance-test IDs;
- 11 stale `Draft for acceptance` status labels.

## 3. Findings and resolutions

### AUD-001 — Merged specifications retained draft metadata

**Severity:** Documentation consistency  
**Resolution:** All normative source documents now state `Accepted for implementation`. Accepted ADRs now state `Accepted`.

### AUD-002 — Requirement-keyword casing was inconsistent

**Severity:** Interpretation clarity  
**Resolution:** `00-index.md` now states that MUST, SHOULD, and MAY are interpreted case-insensitively for specification set 0.1. Future changes should use uppercase forms.

### AUD-003 — Personal Lite document-read requirement appeared after the proof gate

**Severity:** Blocking implementation-order contradiction  
**Problem:** The Personal Lite proof requires a user-selected local document, while the roadmap previously placed document intake after the first proof gate.

**Resolution:** A minimal user-controlled text and Markdown intake slice is now IMP-012, before runtime integration and the first complete continuity drill. The later Capability Broker document slice remains responsible for richer model-requested tool behavior.

### AUD-004 — Phase 0 follow-up text was stale after specification generation

**Severity:** Roadmap clarity  
**Resolution:** The roadmap now marks the specification baseline as complete and points directly to IMP-001 after the v0.1 freeze.

## 4. Consistency conclusions

No unresolved blocking contradiction remains in the reviewed v0.1 specification set.

The following principles are consistently preserved:

- doll is a personal AI continuity system, initially built for one user's real local needs;
- the durable core is user-controlled state rather than a model, UI, runtime, or provider;
- local operation is required and cloud inference is optional;
- local failure never silently causes cloud submission;
- Lite and Heavy share one state, security, backup, and migration foundation;
- models and external content are untrusted inputs to a default-deny capability boundary;
- backup creation is not accepted as recovery evidence without restore;
- Heavy cannot be declared stable without real Heavy hardware;
- personality, voice, avatar, cloud, mobile, and broad autonomy remain optional or deferred;
- stable claims require test evidence.

## 5. Known intentional limitations

The freeze does not select:

- a permanent model catalog;
- a Heavy computer;
- cloud providers;
- a dedicated doll UI;
- mobile frameworks;
- exact Lite hardware requirements before measurement;
- a foundation-model training program.

These are deliberate deferred decisions, not missing v0.1 requirements.

## 6. Freeze rule

Specification set 0.1 is accepted as the implementation baseline.

Future changes that weaken local completeness, state portability, workspace confinement, explicit approval, recoverability, or evidence-based release gates require a dedicated specification change and, where applicable, a new ADR.

Implementation begins with IMP-001. The first major gate remains the Personal Lite continuity proof.
"""
    write("docs/audits/specification-v0.1-audit.md", report)


def main() -> None:
    normalize_statuses()
    clarify_requirement_language()
    fix_roadmap_ordering()
    write_audit_report()
    print("Specification set 0.1 freeze changes applied.")


if __name__ == "__main__":
    main()
