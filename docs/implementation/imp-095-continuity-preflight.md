# IMP-095 — Bounded deterministic ContinuityPreflight

Status: implementation candidate for Issue #288

## Purpose

IMP-095 adds the first bounded `ContinuityPreflight` slice required after ProjectExperienceRecord. It checks explicit accepted state before a proposed project action without model reasoning and without granting execution authority.

Governing requirements:

- `docs/spec/03c-memory-interoperability-recall-and-project-experience.md` §12;
- `docs/spec/08c-memory-interoperability-recall-and-project-experience-acceptance.md` MCON-011 through MCON-013;
- `docs/spec/09a-post-imp-083-memory-continuity-roadmap.md` §5.7;
- the existing Capability Broker, permission, policy, procedure, work-item, and ProjectExperienceRecord authority boundaries.

## Read-only rule set

`src/doll/continuity_preflight.py` defines rule set `doll.continuity-preflight` version 1.

The service requires an already-open **read-only** StateRepository and returns only deterministic metadata:

- rule-set ID and version;
- project ID;
- proposed action class;
- status;
- matched record IDs;
- warning/rule codes;
- authoritative blocker record IDs where a blocker is represented by an accepted record;
- whether existing authority requires explicit user confirmation.

The service does not write Doll State, append audit events, run a model, invoke a capability, open a network connection, launch a process, or consume an allow-once permission.

## Explicit bounded scope

The first version deliberately avoids broad semantic matching.

A caller explicitly selects the project and optional work item. It may also supply:

- a capability ID/version and exact permission scope;
- policy IDs that an existing accepted policy-matching layer has already classified as applicable denials;
- procedure IDs already classified as required for the proposed action.

ContinuityPreflight revalidates those referenced records and their current lifecycle state. It **does not parse PolicyRecord free text to invent new policy semantics** and does not infer arbitrary procedure relevance from prose.

The explicit lists are bounded to 64 IDs. ProjectExperience inspection is bounded to 500 active records and fails closed if the global active experience set exceeds that first-version limit.

## Existing authority remains authoritative

The first rule set can surface these existing conditions:

- an explicitly applicable active/enabled PolicyRecord denial;
- a selected WorkItem that is already blocked;
- selected WorkItem dependencies that are not completed;
- a required ProcedureRecord that is not approved;
- an existing PermissionRecord decision resolved through `PermissionService`;
- a high-risk or release-excluded capability definition from the immutable CapabilityRegistry.

A permission with mode `ask` or a high-risk capability produces `requires_confirmation = true`. A denied/no-record permission remains denied. ContinuityPreflight never converts either condition into a grant.

The actual Capability Broker remains the execution authorization boundary. IMP-095 does not execute a capability and does not replace the existing capability preflight, confirmation, permission-consumption, or network policy paths.

## Prior project experience is advisory

The service inspects active ProjectExperienceRecords in the selected project and adds an evidence-linked warning for directly relevant unsuperseded records whose outcome is `failed`.

Relevance is intentionally narrow:

- with a selected WorkItem, project-level failures and failures linked to that WorkItem are eligible;
- without a selected WorkItem, only project-level failures are eligible;
- failures superseded by a later ProjectExperienceRecord are not replayed;
- failures linked only to another WorkItem are not replayed.

The output distinguishes user-recorded, user-confirmed, deterministic-system, imported, and model-proposed assertion classes through warning codes.

All ProjectExperienceRecord failures are advisory in this slice. Imported and model-proposed failures cannot independently create a hard denial. User-confirmed or deterministic-system failures also remain warnings unless a separate existing authority source blocks the action.

## Status precedence

The deterministic result precedence is:

1. `blocked` when an existing authoritative blocker or denied/release-excluded capability condition applies;
2. `confirmation_required` when no blocker exists but existing capability/permission state requires user confirmation;
3. `warning` when only advisory prior-experience or other non-blocking rule codes remain;
4. `clear` when no rule matches.

A `clear` result is **not an execution permission grant**. The Capability Broker and other accepted safety boundaries still decide whether an operation may proceed.

## MCON evidence

`tests/test_imp_095_continuity_preflight.py` provides deterministic synthetic evidence for:

- **MCON-011** — a relevant prior failed ProjectExperienceRecord yields an evidence-linked warning while the state revision remains unchanged;
- **MCON-012** — existing PolicyRecord, WorkItem blocker, required ProcedureRecord, PermissionRecord, and capability-risk/confirmation state remain authoritative and explainable through IDs/codes;
- **MCON-013** — imported and model-proposed failed experience remains lower-authority advisory evidence and cannot manufacture a hard deny or permission grant.

Additional tests cover:

- read-only enforcement;
- a clear baseline;
- superseded and unrelated experience filtering;
- denied/no-record versus scoped permission behavior;
- disabled denial-policy rejection;
- invalid/duplicate explicit scope rejection;
- cross-project WorkItem/Procedure rejection;
- bounded ProjectExperience scope failure.

## Persisted-state note

IMP-095 adds no authoritative record type, table, schema migration, package member, backup format, or Resume Bundle member. The result is a transient deterministic read model over already accepted state.

## Explicit non-goals

IMP-095 does not add:

- PLUR or PROJECTMEM adapters;
- MCP;
- a remote/network preflight service;
- model-based policy interpretation or action reasoning;
- automatic ProjectExperience extraction or promotion;
- new permission semantics;
- arbitrary policy-language execution;
- automatic action execution;
- replacement of the Capability Broker;
- a Phase 6 completion, Lite v1.0, or stable general anti-lock-in claim.
