# doll specification index

**Status:** Draft for acceptance  
**Specification set version:** 0.1

## 1. Purpose

This directory contains the normative product and engineering specification for doll.

The source files under `docs/spec/` are the maintainable source of truth. A combined reading copy may later be generated from these files, but the generated copy must not be edited directly.

## 2. Normative order

Read and combine the specification in this order:

1. `00-index.md` — document map and requirement language;
2. `00-decisions-baseline.md` — accepted, rejected, and deferred baseline decisions;
3. `01-product-and-continuity-contract.md` — product identity and Continuity Contract;
4. `02-architecture-and-data-flow.md` — service boundaries, adapters, trust boundaries, and flows;
5. `03-doll-state-memory-and-storage.md` — authoritative state, memory, storage, export, and migration;
6. `04-security-permissions-and-threat-model.md` — security boundaries, permissions, and threats;
7. `05-model-vault-lifecycle-evaluation.md` — model ownership, validation, evaluation, promotion, and rollback;
8. `06-platform-install-update-and-recovery.md` — platform, install, update, backup, restore, and recovery;
9. `07-release-scope-and-profiles.md` — release boundaries and Lite/Heavy scope;
10. `08-acceptance-and-continuity-tests.md` — evidence required for product claims and release gates;
11. `09-development-roadmap.md` — implementation sequence and pull-request plan.

Accepted architecture decisions under `docs/decisions/` explain why major constraints were selected. They are normative when their status is accepted and they do not conflict with a later accepted specification change.

## 3. Requirement language

The following terms are normative:

- **MUST / MUST NOT:** mandatory for the applicable release or claim;
- **SHOULD / SHOULD NOT:** expected unless a documented reason justifies an exception;
- **MAY:** optional;
- **DEFERRED:** intentionally outside the current release boundary;
- **EXPERIMENTAL:** available without a stable compatibility promise;
- **BLOCKING TEST:** failure prevents the applicable release or claim;
- **ADVISORY TEST:** failure requires documentation but does not automatically block release.

Ordinary descriptive language is not automatically a mandatory requirement unless it is tied to an acceptance criterion, decision, or release gate.

## 4. Conflict resolution

When accepted documents conflict, use this order:

1. the most recent explicit decision changing the earlier requirement;
2. the release-specific scope and acceptance criteria;
3. the Continuity Contract;
4. security and data-integrity requirements;
5. architecture and implementation direction;
6. roadmap estimates.

A conflict must be resolved in a dedicated pull request. Implementations must not silently choose one interpretation.

## 5. Status meanings

- **Draft for acceptance:** proposed in an open pull request;
- **Accepted:** merged into the default branch and not superseded;
- **Superseded:** retained for history but replaced by a newer accepted decision;
- **Deprecated:** still readable but not intended for new implementation;
- **Experimental:** intentionally incomplete or unstable.

Merging a draft specification into `main` changes it to accepted unless the document explicitly states otherwise.

## 6. Claim discipline

Public documentation and release notes must distinguish:

- planned;
- implemented;
- tested in CI;
- tested on a real machine;
- community verified;
- experimental;
- stable for the named release.

A feature being present in source code does not prove that the feature satisfies its Continuity Contract or security requirements.

## 7. Generated combined specification

The project will later add a deterministic build step that concatenates accepted source files into a reading copy such as:

```text
DOLL_FINAL_SPEC.md
```

The generator must:

- use the order defined in this index;
- identify source file names and versions;
- fail when an expected file is missing;
- avoid silently including drafts or unrelated research;
- produce deterministic output;
- mark the output as generated;
- be checked in CI.

## 8. Non-normative material

The following are non-normative unless promoted through an accepted specification or decision:

- competitor research;
- brainstorming notes;
- issue comments;
- pull-request discussions after merge;
- screenshots and design mockups;
- benchmark experiments without an accepted evaluation definition;
- personal planning documents;
- generated summaries.

## 9. Change requirements

A specification-changing pull request SHOULD include:

- the requirement being changed;
- the reason and evidence;
- compatibility effects;
- migration effects;
- security and privacy effects;
- acceptance-test changes;
- release-scope changes;
- documentation updates.

A change that weakens local completeness, state portability, workspace confinement, explicit approval, or recoverability requires a dedicated architecture decision.
