# Post-IMP-083 memory and continuity roadmap extension

**Status:** Draft for acceptance  
**Specification version:** 0.1  
**Applies after:** IMP-083  
**Depends on:** `09-development-roadmap.md`, `03c-memory-interoperability-recall-and-project-experience.md`, `08c-memory-interoperability-recall-and-project-experience-acceptance.md`, `ADR-008-memory-interchange-recall-and-project-experience.md`

## 1. Purpose

This document extends the accepted development roadmap after IMP-083 with the design consequences of the 2026-08 memory-portability and project-experience review.

It does not renumber or invalidate completed implementation records or accepted evidence.

It exists as a separate extension because `09-development-roadmap.md` is also a historical record of the implementation sequence through IMP-083. Future roadmap consolidation MAY fold this extension into that document once the new slices have stable implementation identifiers.

## 2. Supersession of stale immediate-work text

Section 18, **Immediate work**, in `09-development-roadmap.md` was written from an earlier IMP-067 implementation point and no longer describes the repository's actual frontier.

For work after IMP-083, this document supersedes that section.

All other governing phase order, gate rules, definition-of-done requirements, implementation-identifier rules, and accepted historical results in `09-development-roadmap.md` remain in force unless this extension explicitly changes them.

## 3. Current baseline

The accepted baseline for this extension is:

- Phase 0 through Phase 5 are complete at their documented bounded gates;
- Phase 6 is in progress through IMP-083;
- IMP-073 provides deterministic explicit local lexical state search without a persistent index or automatic context injection;
- IMP-065 through IMP-067 provide explicit, bounded, data-only continuity-context selection for local writing;
- IMP-074 through IMP-082 provide explicit local document and attachment preparation paths;
- IMP-083 adds bounded deterministic local resource measurement and its evidence path; it does not establish adaptive memory or external memory interoperability;
- semantic retrieval, persistent retrieval indexes, embeddings, model-selected context, broad agent protocols, PAM/PLUR/PROJECTMEM adapters, ProjectExperienceRecord, ContinuityPreflight, and package signing are not established by IMP-083.

This extension preserves those non-claims.

## 4. Scheduling principles

The next work MUST preserve these rules.

1. **Do not replace explicit context with semantic automation in one step.** Derived recall is introduced behind the existing explicit and data-only context boundary.
2. **Do not make interoperability formats canonical.** PAM, PLUR, PROJECTMEM, and MCP remain adapters or interfaces around Doll State.
3. **Do not let retrieval state mutate truth.** Usage and ranking are separated before adaptive recall is accepted.
4. **Do not add a persisted record without continuity coverage.** New records require schema, package, backup, restore, compatibility, and fresh-process validation in the same implementation slice.
5. **Do not convert current state to global event sourcing.** Append-oriented ProjectExperienceRecord complements revisioned current-state records.
6. **Do not make prior experience a new permission system.** ContinuityPreflight composes with the existing safety boundary and may only surface existing authority or advisory evidence.
7. **Do not delay local completeness in order to add cloud integration.** Phase 7 remains optional and follows the accepted Phase 6 local-complete priorities.
8. **Do not reserve IMP identifiers in this document.** The next implementation issue receives the next available monotonic identifier only when opened.

## 5. Phase 6 extension — local recall and continuity intelligence

Phase 6 remains **Local AI portability and daily-use integration**.

The following work is scheduled inside or adjacent to the remaining Phase 6 track because it improves local daily use and continuity without adding cloud dependence.

### 5.1 Preserve the current explicit-context baseline

Before adding automatic semantic selection, later work MUST retain:

- explicit user selection as a supported path;
- data-only treatment for selected memory, project, decision, Resume Bundle, document, PDF, OCR, CSV, and attachment material;
- no automatic linked-record expansion;
- no model authority over policy, permission, completion, procedure approval, or checkpoint confirmation;
- the ability to run without semantic indexes or embedding models.

This is a continuing constraint, not a new implementation slice by itself.

### 5.2 MemoryUsageSignalRecord and derived RecallState foundation

The first adaptive-memory implementation slice SHOULD establish:

- versioned `MemoryUsageSignalRecord` when persistent signals are used;
- append-oriented bounded signal creation;
- explicit actor/provenance differences between user, model, deterministic system, and imported signals;
- derived `RecallState` with explicit algorithm/version identity;
- index removal and deterministic rebuild behavior;
- no authoritative MemoryRecord revision changes from retrieval alone;
- MCON-001 through MCON-003 for the implemented boundary.

If the first implementation can prove useful recall without persisting usage signals, it MAY introduce derived RecallState first. It MUST NOT smuggle equivalent counters back into authoritative MemoryRecord fields.

### 5.3 Local retrieval upgrade

After the separation above is proven, local recall MAY progress in bounded steps:

1. deterministic lexical scoring over the existing authoritative searchable surface;
2. optional persistent lexical index where useful;
3. optional local semantic embeddings;
4. deterministic fusion or ranking with an explicit algorithm version;
5. context-budget selection with inspectable selected record IDs.

Every stage MUST retain a no-cloud path and a deterministic lexical fallback for the applicable local profile.

Semantic retrieval is not required merely because PLUR or another system uses embeddings. It should be introduced only when measured usefulness justifies the extra dependency and rebuild cost.

### 5.4 Memory consolidation review

After recall-state separation, a bounded consolidation workflow MAY add duplicate and contradiction candidates.

The first accepted version MUST remain review-controlled and MUST pass MCON-004 before claiming consolidation.

Automatic merge, autonomous deletion, or lifecycle changes based on activation or decay remain out of scope.

### 5.5 PAM v1.x import/export adapter

PAM is the first scheduled general memory-interchange profile.

The implementation order is:

1. exact supported-version declaration;
2. offline validation fixture and resource limits;
3. staged import through the existing Phase 4A portability path;
4. mapping and loss report;
5. unchanged-source idempotency and conflict behavior;
6. authority-separation tests;
7. confirmed-memory subset export;
8. explicit distinction between PAM memory export and Doll State continuity export;
9. MCON-005 through MCON-007 plus applicable PORT evidence.

PAM support is claim-specific. It does not retroactively become a prerequisite for previously accepted doll-to-doll continuity evidence.

### 5.6 ProjectExperienceRecord

A later local-continuity slice SHOULD add ProjectExperienceRecord before any experience-aware pre-action warning is treated as a stable feature.

The implementation MUST include in one accepted slice:

- versioned experience schema and assertion/provenance state;
- append-oriented semantic payload behavior;
- correction/supersession relationships;
- project and optional work-item link validation;
- State Package registration;
- backup and restore;
- fresh-process inspection;
- deterministic export and Resume Bundle inclusion or explicit omission rules;
- secret/sensitivity coverage;
- MCON-009.

The first version SHOULD favor explicit user recording and deterministic system observations. Automatic model extraction from arbitrary conversations remains proposal-only.

### 5.7 ContinuityPreflight

After ProjectExperienceRecord exists, a deterministic read-only ContinuityPreflight MAY be added.

The first slice SHOULD cover only a small set of action classes and rules, for example:

- authoritative policy denial already applicable to the action;
- existing PermissionRecord or capability requirement;
- current WorkItem blocker;
- a directly relevant prior failed ProjectExperienceRecord;
- a required approved ProcedureRecord or confirmation already defined by accepted policy.

The preflight MUST:

- run without a model;
- cite matched record IDs and rule-set version;
- treat prior failure as advisory unless another accepted authority already blocks the action;
- never grant permission;
- never replace the Capability Broker;
- pass MCON-011 through MCON-013.

### 5.8 Existing Phase 6 completion work remains visible

The new memory/experience work MUST NOT hide the pre-existing Phase 6 completion requirements.

The project still needs the remaining evidence required by the accepted Phase 6 and Lite release claims, including applicable portability, performance, accessibility, cross-platform, and soak work identified by the current roadmap and release specification. IMP-083's bounded resource-measurement path is part of that evidence track, not evidence that the broader Phase 6 completion gate has passed.

A claim-specific PAM or semantic-recall adapter MAY ship experimentally without blocking unrelated Phase 6 completion, but no stable claim may be made before its MCON/PORT evidence passes.

## 6. Phase 7 — optional cloud and multiple models

The accepted Phase 7 order remains valid.

Memory and context changes add these constraints:

- cloud embeddings or cloud reranking MUST NOT become the only recall path;
- cloud models consume a bounded context package produced by the same local authority and context-selection boundary;
- cloud-provider memory APIs are source/target adapters, not canonical state;
- provider-native memory, instruction, or ACL semantics cannot grant Doll authority;
- automatic cloud fallback remains prohibited.

No PAM, PLUR, PROJECTMEM, or MCP implementation requires Phase 7 cloud support.

## 7. Phase 8 — agent interfaces and product-specific memory adapters

Phase 8 remains the primary home for optional external-service and agent interfaces.

The following work is added to its candidate sequence.

### 7.1 PLUR / Engram adapter

After the Doll recall boundary and PAM general profile are stable enough to provide a reference mapping discipline, a PLUR adapter MAY be implemented.

Priority:

- import first or bidirectional only when the mapping is clear;
- activation/decay/usage metadata remains external retrieval metadata;
- procedural/architectural Engrams remain candidates rather than authority;
- PLUR episodes may map to imported project-experience claims;
- MCON-008 and applicable PORT evidence are required for a stable claim.

### 7.2 PROJECTMEM importer

PROJECTMEM support begins import-first.

The adapter MUST:

- bind to the actual supported PROJECTMEM application/export version;
- preserve exact source provenance and event relationships available in that version;
- map supported semantic work events to imported project-experience claims;
- keep decisions, fixes, plans, and completion statements non-authoritative;
- pass MCON-010 and applicable PORT evidence.

Doll-to-PROJECTMEM export remains optional and lower priority because it is inherently narrower than complete Doll continuity state.

### 7.3 MCP read and proposal interface

A local MCP interface MAY be added after the applicable state/search operations are stable.

Recommended order:

1. read-only workspace/project/memory inspection under explicit scope;
2. deterministic search and retrieval;
3. proposal-only memory or work-item creation where the target schema already permits proposals;
4. only later consider additional mutations through a dedicated accepted security decision.

MCON-014 is required before a stable MCP interface claim.

A remote MCP listener or cross-machine agent path is not implied and requires its own threat model.

## 8. Phase 9 — package authenticity and long-term operation

Phase 9 gains an explicit Doll State Package signing track.

Recommended order:

1. define the complete canonical package-manifest representation to be signed;
2. bind every declared member path, category, size, and digest;
3. choose established JSON canonicalization where needed;
4. choose a reviewed signature primitive/library;
5. implement offline verification;
6. define unsigned legacy-package compatibility;
7. test member removal, substitution, addition, and metadata tampering;
8. keep signing separate from backup/package encryption;
9. add key rotation, verification, migration, and recovery guidance;
10. pass MCON-015 and MCON-016.

DID, remote certificate services, hosted key accounts, and network identity providers remain optional. Package verification MUST have a local path.

## 9. Non-goals of this extension

This roadmap extension does not schedule:

- a Doll-specific public memory interchange standard;
- global conversion of Doll State to event sourcing;
- automatic deletion driven by memory decay;
- autonomous memory confirmation;
- automatic adoption of imported permissions or ACLs;
- a mandatory vector database;
- a mandatory embedding model;
- cloud-only retrieval;
- arbitrary remote MCP access;
- automatic execution of ProjectExperience lessons;
- custom cryptography.

## 10. Immediate order after this documentation change

Once this specification change is accepted, the implementation frontier is:

1. continue the existing Phase 6 completion track from IMP-083 without regressing explicit context, local-only behavior, portability, resource-measurement evidence, or safety;
2. schedule the bounded derived-recall foundation before any semantic/model-selected memory context feature;
3. schedule PAM v1.x as the first general memory-interchange adapter when the recall/interchange boundary is ready;
4. schedule ProjectExperienceRecord before ContinuityPreflight;
5. keep PLUR, PROJECTMEM, and MCP as later Phase 8 interoperability work unless a concrete user need justifies earlier bounded work;
6. keep full package signing in Phase 9;
7. assign each implementation identifier only when its issue is opened.

No code implementation is authorized merely by the existence of this roadmap document; each slice still requires the normal issue, specification citation, bounded scope, tests, and pull-request review.

## 11. Change-control rule

Future changes that collapse any of the following boundaries require a dedicated architecture decision:

- Doll State versus external memory interchange;
- authoritative MemoryRecord versus derived recall state;
- revisioned current state versus append-oriented project experience;
- advisory experience versus permission/capability authority;
- MCP transport versus canonical persistence;
- package integrity, authenticity, and encryption.

The continuity-first, safety-before-authority, local-complete, cloud-optional ordering remains unchanged.