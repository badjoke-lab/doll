# doll specification index

**Status:** Accepted for implementation  
**Specification set version:** 0.1

## 1. Purpose

This directory contains the normative product and engineering specification for doll.

The source files under `docs/spec/` are the maintainable source of truth. `DOLL_FINAL_SPEC.md` is the deterministic combined reading copy and must not be edited directly.

## 2. Governing pillars

The specification is governed by two co-equal architectural pillars:

1. **Continuity:** user-owned state must survive model, provider, interface, machine, network, and project failure.
2. **Safety boundary:** models, tools, runtimes, and external content must not gain undeclared authority over state, secrets, the operating system, accounts, or external services.

Implementation must prove continuity without a model, then complete and acceptance-test the safety boundary, then connect a model runtime.

## 3. Normative order

Read and combine the specification in this order:

1. `00-index.md` — document map, governing pillars, and requirement language;
2. `00-decisions-baseline.md` — accepted, rejected, and deferred baseline decisions;
3. `01-product-and-continuity-contract.md` — product identity and Continuity Contract;
4. `02-architecture-and-data-flow.md` — service boundaries, adapters, trust boundaries, and flows;
5. `03-doll-state-memory-and-storage.md` — authoritative state, memory, storage, export, and migration;
6. `04-security-permissions-and-threat-model.md` — security boundary, secrets, trust, instructions, permissions, capabilities, and threats;
7. `05-model-vault-lifecycle-evaluation.md` — model ownership, validation, evaluation, promotion, and rollback;
8. `06-platform-install-update-and-recovery.md` — platform, install, update, backup, restore, and recovery;
9. `07-release-scope-and-profiles.md` — release boundaries and Lite/Heavy scope;
10. `08-acceptance-and-continuity-tests.md` — evidence required for product claims and phase or release gates;
11. `09-development-roadmap.md` — implementation sequence and pull-request plan.

Accepted architecture decisions under `docs/decisions/` explain why major constraints were selected. They are normative when their status is accepted and they do not conflict with a later accepted specification change.

The accepted decision set includes:

- `ADR-001-local-complete-cloud-optional.md`;
- `ADR-002-default-deny-capability-broker.md`;
- `ADR-003-state-independent-of-model-and-ui.md`;
- `ADR-004-release-gates-require-evidence.md`;
- `ADR-005-safety-boundary-before-model-execution.md`.

## 4. Requirement language

The following terms are normative.

The terms are interpreted case-insensitively in specification set 0.1; future changes SHOULD use uppercase forms for clarity.

- **MUST / MUST NOT:** mandatory for the applicable release, phase gate, or claim;
- **SHOULD / SHOULD NOT:** expected unless a documented reason justifies an exception;
- **MAY:** optional;
- **DEFERRED:** intentionally outside the current release boundary;
- **EXPERIMENTAL:** available without a stable compatibility promise;
- **BLOCKING TEST:** failure prevents the applicable phase, release, or claim;
- **ADVISORY TEST:** failure requires documentation but does not automatically block release.

Ordinary descriptive language is not automatically a mandatory requirement unless it is tied to an acceptance criterion, decision, or release gate.

## 5. Conflict resolution

When accepted documents conflict, use this order:

1. the most recent explicit decision changing the earlier requirement;
2. the release-specific or phase-specific scope and acceptance criteria;
3. the Continuity Contract;
4. security, secret-separation, trust, and data-integrity requirements;
5. architecture and implementation direction;
6. roadmap estimates.

A conflict must be resolved in a dedicated pull request. Implementations must not silently choose one interpretation.

ADR-005 changes the implementation sequence so that the complete safety boundary and its acceptance gate precede model execution. Earlier roadmap text that placed model integration first is superseded by the accepted roadmap carrying that decision.

## 6. Status meanings

- **Draft for acceptance:** proposed in an open pull request;
- **Accepted:** merged into the default branch and not superseded;
- **Superseded:** retained for history but replaced by a newer accepted decision;
- **Deprecated:** still readable but not intended for new implementation;
- **Experimental:** intentionally incomplete or unstable.

Merging a draft specification into `main` changes it to accepted unless the document explicitly states otherwise.

## 7. Claim discipline

Public documentation and release notes must distinguish:

- planned;
- implemented;
- tested in CI;
- tested on a real machine;
- community verified;
- experimental;
- stable for the named release.

A feature being present in source code does not prove that it satisfies its Continuity Contract or security requirements.

A model responding successfully does not prove that secret isolation, instruction authority, capability enforcement, prompt-injection resistance, or high-risk confirmation are correct.

## 8. Generated combined specification

`DOLL_FINAL_SPEC.md` is generated from the normative source order defined by `scripts/build_final_spec.py`.

The generator must:

- use the order defined in this index;
- identify source file names and versions;
- fail when an expected file is missing;
- avoid silently including drafts or unrelated research;
- produce deterministic output;
- mark the output as generated;
- be checked in CI.

Regenerate with:

```text
python scripts/build_final_spec.py
```

Check with:

```text
python scripts/build_final_spec.py --check
```

## 9. Non-normative material

The following are non-normative unless promoted through an accepted specification or decision:

- competitor research;
- brainstorming notes;
- issue comments;
- pull-request discussions after merge;
- screenshots and design mockups;
- benchmark experiments without an accepted evaluation definition;
- personal planning documents;
- generated summaries other than the deterministic combined specification as a reading copy.

## 10. Change requirements

A specification-changing pull request SHOULD include:

- the requirement being changed;
- the reason and evidence;
- compatibility effects;
- migration effects;
- security and privacy effects;
- acceptance-test changes;
- phase and release-scope changes;
- documentation updates.

A change that weakens local completeness, state portability, workspace confinement, secret separation, trust provenance, instruction-origin enforcement, explicit approval, high-risk confirmation, or recoverability requires a dedicated architecture decision.
