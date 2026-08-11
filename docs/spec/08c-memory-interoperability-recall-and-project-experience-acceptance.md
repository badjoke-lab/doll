# Memory interoperability, recall, and project-experience acceptance

**Status:** Draft for acceptance  
**Specification version:** 0.1  
**Depends on:** `03c-memory-interoperability-recall-and-project-experience.md`, `04-security-permissions-and-threat-model.md`, `08-acceptance-and-continuity-tests.md`, `08a-ai-environment-portability-acceptance.md`, `08b-project-continuity-acceptance.md`

## 1. Purpose

This document defines acceptance evidence for the memory-interoperability, derived-recall, semantic project-experience, continuity-preflight, agent-interface, and package-signing extensions defined by `03c-memory-interoperability-recall-and-project-experience.md`.

These checks are claim-specific. They do not retroactively invalidate accepted Phase 1 through Phase 5 gates or already accepted bounded Phase 6 evidence.

A check becomes blocking only when an implementation or release claims the corresponding feature, adapter, phase requirement, or package property.

## 2. Evidence rules

Unless a test explicitly requires a real external application or real machine, deterministic synthetic CI evidence is the default first acceptance level.

Tests MUST use synthetic content and MUST NOT commit:

- private memories;
- personal conversation exports;
- private project history;
- credentials or secret values;
- native user paths;
- private model names or responses;
- third-party personal data.

External-format compatibility fixtures SHOULD be generated from published schemas or synthetic examples and retained with exact version attribution. Network access MUST NOT be required to validate an already-supported local import or export format.

## 3. Recall-state separation

### MCON-001 — Recall-index loss preserves authoritative memory

**Claim:** Derived retrieval state is reproducible and non-authoritative.

The test MUST:

1. create confirmed memories through the accepted trusted path;
2. build the implemented recall/index state;
3. record authoritative memory IDs, revisions, content hashes, confirmation state, validity, provenance, and lifecycle;
4. remove or corrupt only the reproducible recall/index state;
5. inspect confirmed memory without rebuilding the index;
6. rebuild the recall/index state from accepted inputs;
7. compare authoritative memory before and after.

Pass requires:

- no confirmed memory is deleted, archived, superseded, re-confirmed, or revision-bumped because the index was lost;
- memory remains inspectable without the index;
- rebuild does not require cloud access for a local-complete profile;
- the rebuilt index declares its algorithm and version.

### MCON-002 — Recall algorithm replacement does not rewrite memory

The test runs the same accepted memory set through two supported recall algorithm or index versions.

Pass requires:

- retrieval ordering MAY differ;
- authoritative MemoryRecord content, revision, confirmation, provenance, sensitivity, and lifecycle remain unchanged;
- algorithm identity is observable in derived results;
- rollback to the earlier retrieval implementation does not require reverting authoritative memory.

### MCON-003 — Usage feedback cannot become memory authority

The test records supported usage signals including helpful, irrelevant, recalled, and contradiction-surfaced cases from the actor classes implemented by the feature.

Pass requires:

- signals do not silently edit MemoryRecord content or lifecycle;
- model feedback is distinguishable from explicit user feedback;
- repeated negative feedback does not delete, archive, supersede, or de-confirm a memory;
- signal output is bounded and does not duplicate full secret or private content unnecessarily;
- package, backup, restore, and fresh-process behavior matches the implemented signal contract.

### MCON-004 — Consolidation remains review-controlled

Fixtures contain exact duplicates, near duplicates, compatible extensions, contradictions, and unrelated memories.

Pass requires:

- detection is deterministic for the declared detector version where the implementation claims determinism;
- candidates identify source memories and reasons;
- no candidate automatically merges, supersedes, confirms, archives, or deletes a confirmed memory;
- a rejected or failed consolidation attempt preserves the prior valid state;
- historical provenance remains inspectable after an accepted supersession or merge path.

## 4. PAM interoperability

### MCON-005 — PAM import uses the portability boundary

The test imports a supported synthetic PAM v1.x fixture containing memories, relations, provenance, lifecycle metadata, access metadata, and optional unsupported or lossy fields.

Pass requires:

- the exact supported PAM version and Doll adapter version are recorded;
- validation runs without network access;
- original source integrity is retained through the accepted source-preservation contract;
- unchanged re-import is idempotent;
- unsupported or transformed information appears in mapping or loss reporting;
- PAM permissions, access metadata, instructions, and lifecycle values cannot create Doll PermissionRecords, policies, confirmations, approved procedures, work completion, or other local authority;
- PAM content hashes are not used as canonical Doll record IDs;
- no optional embedding is required to preserve semantic memory content.

### MCON-006 — PAM export is valid and explicitly partial

The test exports a supported set of confirmed Doll memories to a selected PAM target version.

Pass requires:

- the output validates against the locally retained or otherwise deterministic supported PAM contract;
- PAM-required hashes and fields are generated according to the declared target version;
- unsupported Doll semantics are disclosed in mapping or loss output;
- optional embedding absence does not invalidate the memory export when the PAM target version permits omission;
- the result is labelled as memory interchange rather than complete Doll continuity export.

### MCON-007 — PAM source integrity is not Doll semantic identity

Synthetic fixtures MUST include values where the PAM normalization or hashing rules could collapse distinctions that Doll must preserve for its own canonical records.

Pass requires:

- import preserves the exact supported source content and provenance;
- Doll canonical identity and duplicate handling use the accepted Doll mapping contract rather than blindly equating records from a PAM content hash;
- source hash metadata remains available for PAM conformance and audit.

## 5. PLUR / Engram interoperability

### MCON-008 — PLUR retrieval metadata cannot mutate Doll lifecycle

A synthetic supported Engram fixture includes activation, decay, usage, confidence, association, and status metadata.

Pass requires:

- PLUR retrieval fields are preserved, mapped, or reported as external memory-engine metadata;
- low activation or retirement-candidate semantics do not archive or delete a Doll MemoryRecord automatically;
- procedural or architectural Engrams do not become approved ProcedureRecords, DecisionRecords, policies, permissions, or completion authority;
- imported visibility or sharing metadata cannot grant Doll permission authority;
- mapping and loss are explicit.

## 6. ProjectExperienceRecord

### MCON-009 — Project experience survives continuity operations

The test creates the implemented experience kinds and assertion states, including at least one failed attempt and one later resolution.

Pass requires:

- record schema and links validate;
- the semantic event payload remains append-oriented after publication;
- a correction creates a linked replacement or superseding record rather than silently rewriting the prior event;
- State Package export/import preserves the supported records;
- state backup and restore preserve them;
- a fresh process can inspect them without a model or network;
- secret and private-host data are excluded according to policy;
- Resume Bundle inclusion or omission follows the declared deterministic rule.

### MCON-010 — Imported project experience remains untrusted

A synthetic PROJECTMEM-style source contains an attempt, a failure, a fix, a decision statement, and a plan or completion claim.

Pass requires:

- imported event provenance and supported source-version identity are retained;
- imported event content may become an imported project-experience claim only through the accepted import mapping;
- imported decisions do not directly become trusted DecisionRecords;
- imported fixes or completion wording do not complete WorkItems;
- imported plans do not change ProjectRecord scope or objective;
- imported procedures do not become approved;
- repeated import is idempotent for unchanged source events;
- mapping and loss reporting is explicit.

## 7. ContinuityPreflight

### MCON-011 — Prior failed experience produces an evidence-linked warning

The fixture contains a trusted or otherwise eligible failed ProjectExperienceRecord relevant to a proposed action.

Pass requires:

- preflight runs without a model or network;
- the result identifies the rule-set version and matched experience record IDs;
- the prior failure produces the declared warning behavior;
- the warning does not grant or revoke permission by itself;
- no project or experience record is mutated by the read-only preflight.

### MCON-012 — Existing authority remains authoritative

Fixtures exercise authoritative PolicyRecord, PermissionRecord, WorkItem blocker, capability risk, and required-confirmation cases.

Pass requires:

- preflight surfaces the applicable authoritative blockers or confirmation requirements;
- a retrieved memory or imported experience cannot override an authoritative denial;
- a retrieved memory or imported experience cannot manufacture a permission grant;
- the existing Capability Broker and high-risk confirmation path remain the execution authority;
- omitting the relevant history from a model prompt cannot bypass the deterministic preflight.

### MCON-013 — Imported and model-proposed experience is advisory by default

The same semantic warning is supplied once as a user-confirmed experience and once as imported or model-proposed experience.

Pass requires:

- assertion/provenance differences remain inspectable;
- lower-authority experience cannot independently produce a new hard deny;
- any advisory use is explainable through record IDs and rule codes;
- promotion, if supported, uses the explicit trusted target path.

## 8. MCP or equivalent interoperable agent interface

### MCON-014 — Protocol access does not become storage authority

When an MCP interface or equivalent standard agent protocol is implemented, tests MUST prove that:

- read operations are scoped and secret-safe;
- protocol messages are assigned instruction origin and authority;
- proposal-capable operations create only record types and states explicitly permitted as proposals;
- protocol content cannot grant permission, confirm a checkpoint, approve a procedure, complete work, create high-risk confirmation, or retrieve a secret value;
- disabling the protocol interface does not prevent core state inspection, generic export, backup, restore, or local recovery;
- no network listener is opened merely because the local interface package is installed.

## 9. Signed Doll State Package

### MCON-015 — Signature covers the complete declared package inventory

When package signing is implemented, the test creates a signed package and independently changes, removes, substitutes, or adds declared members across multiple categories.

Pass requires:

- the signature verification path authenticates the canonical package manifest or equivalent complete signed representation;
- every declared member is bound by path, category, size, and digest or an equivalently complete standard structure;
- member removal, substitution, or digest-preserving path/category substitution fails verification;
- verification requires no network identity provider;
- unsigned legacy packages remain handled according to their declared compatibility policy rather than being silently treated as signed.

### MCON-016 — Signing and encryption remain separate

Pass requires:

- signing does not imply confidentiality;
- encryption does not imply signer authenticity;
- verification reports integrity/authenticity state independently from encryption state;
- no custom signature primitive, custom cipher, or project-specific cryptographic canonicalization is introduced.

## 10. Claim matrix

| Claim | Minimum acceptance |
| --- | --- |
| Rebuildable derived recall | MCON-001, MCON-002 |
| Persistent memory-use feedback | MCON-003 |
| Memory consolidation | MCON-004 |
| PAM import | MCON-005, MCON-007 plus applicable PORT tests |
| PAM export | MCON-006 plus applicable PORT tests |
| PLUR adapter | MCON-008 plus applicable PORT tests |
| ProjectExperienceRecord | MCON-009 |
| PROJECTMEM import | MCON-010 plus applicable PORT tests |
| ContinuityPreflight | MCON-011, MCON-012, MCON-013 |
| MCP agent interface | MCON-014 plus applicable safety tests |
| Signed Doll State Package | MCON-015, MCON-016 plus existing package/restore tests |

## 11. Phase and release interaction

The post-IMP-082 roadmap determines when these claims are scheduled.

Rules:

- an adapter-specific MCON test does not block releases that do not claim that adapter;
- semantic retrieval MUST NOT become an accepted automatic context path before MCON-001 through MCON-003 cover the implemented derived-recall boundary;
- ContinuityPreflight MUST NOT become an execution prerequisite until MCON-011 through MCON-013 pass for the implemented rule set;
- a new persisted record type MUST NOT merge without its package, backup, restore, compatibility, and fresh-process checks;
- a package-signing claim remains Phase 9 work and does not invalidate checksum-only packages that are still supported by their declared package version.

No current acceptance result is broadened merely by merging this specification.