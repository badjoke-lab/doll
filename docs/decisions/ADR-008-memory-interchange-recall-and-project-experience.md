# ADR-008: Separate memory interchange, recall state, and project experience from canonical continuity

**Status:** Accepted when merged  
**Date:** 2026-08-12

## Context

Doll is already defined as a personal AI continuity system rather than a model wrapper or one chat application's storage layer. Its accepted specifications preserve user-owned state across model, runtime, interface, provider, machine, conversation, and project changes.

A review of current local-first and portable-memory systems exposed three adjacent but distinct problems:

1. **memory interchange** — moving remembered user information between systems;
2. **memory recall and consolidation** — selecting, reinforcing, deduplicating, and surfacing useful remembered information;
3. **project experience and judgment** — retaining what was tried, what failed, what worked, and what should be checked before a similar action is attempted again.

Portable AI Memory (PAM) addresses the first problem as an interchange format. PLUR's Engram specification addresses the second with activation, feedback, consolidation, and hybrid retrieval. PROJECTMEM addresses the third with append-only project events and deterministic pre-action warnings.

Those ideas are useful, but none is equivalent to Doll State. Doll continuity also includes policy, permission, project objectives, decisions, work state, procedures, checkpoints, provenance, trust, artifacts, model/runtime bindings, portability reports, backup, migration, restore, and recovery.

Treating a memory exchange schema, retrieval score, embedding index, or project-event log as Doll's canonical state would collapse those distinct responsibilities and weaken existing authority boundaries.

## Decision

Doll will remain a **user-owned personal AI continuity layer**. Portable memory is one subsystem of continuity, not the product boundary.

The following rules are adopted.

### 1. Doll State remains canonical

Doll will not replace its canonical record model or Doll State Package with PAM, PLUR Engrams, PROJECTMEM events, MCP payloads, provider exports, or another external memory representation.

External formats are handled through versioned adapters and the accepted import, provenance, quarantine, mapping, and loss-report boundary.

### 2. Prefer an open memory interchange format over a Doll-specific public memory standard

When an external memory interchange format is suitable, Doll SHOULD implement a version-bound adapter rather than create a competing public interchange format.

PAM v1.x is the first high-priority general memory interchange profile. Doll's PAM support begins with the published v1.0 contract and MUST remain adapter-scoped.

PAM identifiers, content hashes, access metadata, lifecycle labels, signatures, and optional embeddings do not become Doll authority merely because they are valid PAM fields.

Doll MAY retain its own generic JSON/JSONL export and Doll State Package because those formats preserve broader continuity state. That is not a claim that Doll defines a new general-purpose portable-memory standard.

### 3. MCP is an interface, not a storage or authority format

Doll MAY expose future read and proposal operations through Model Context Protocol where useful.

MCP messages, tool declarations, remote-agent claims, or foreign ACLs MUST NOT become canonical Doll State or grant local authority automatically. A future write-capable agent interface begins proposal-only unless a later accepted specification defines a narrower trusted mutation path.

### 4. Authoritative memory is separate from recall state

The semantic content, provenance, validity, confirmation state, contradictions, and lifecycle of a confirmed memory remain authoritative.

Retrieval frequency, last-access time, lexical or semantic score, embedding identity, activation, decay, usefulness, ranking, and context-selection priority are not the truth of the memory.

Doll will therefore separate:

- authoritative `MemoryRecord` state;
- minimal append-oriented usage or feedback signals when persistence is justified;
- derived, rebuildable `RecallState` and indexes.

Changing a recall algorithm or losing an embedding/index MUST NOT rewrite or invalidate confirmed memory.

A low recall score MUST NOT archive, supersede, retract, delete, or weaken the confirmed status of a memory automatically.

### 5. Consolidation produces candidates, not autonomous truth changes

Duplicate detection, contradiction detection, summarization, and consolidation MAY use deterministic rules or models, but their output is a candidate or review proposal.

A model, imported source, retrieval engine, decay process, or usage counter MUST NOT silently merge, supersede, delete, or confirm authoritative memories.

### 6. Add semantic project experience without globally event-sourcing Doll

Doll will add a versioned `ProjectExperienceRecord` contract for durable semantic work history such as observations, hypotheses, attempts, outcomes, resolutions, and lessons.

The experience record is distinct from `AuditEventRecord`:

- audit answers who or what performed an operation and what the system recorded about that operation;
- project experience answers what was tried, what happened, and what was learned in the work itself.

Published experience payloads are append-oriented. Material correction occurs by a new record that references or supersedes the earlier record rather than silently rewriting history.

This does **not** convert Doll's authoritative current state into a global event-sourced architecture. ProjectRecord, DecisionRecord, WorkItemRecord, PolicyRecord, PermissionRecord, and other accepted current-state records retain their existing revisioned models.

### 7. Project experience may inform a deterministic continuity preflight

Doll will define a model-independent `ContinuityPreflight` that can inspect relevant policy, permission, decisions, procedures, work blockers, and prior project experience before a proposed action proceeds.

Prior failed experience normally produces an evidence-linked warning. It does not create a new permission denial by itself.

Where an existing authoritative policy, permission, blocker, or capability rule already denies an action, preflight may surface that denial but MUST NOT bypass or replace the accepted Capability Broker and confirmation boundary.

Imported or model-proposed experience cannot become a hard authority merely because it was retrieved.

### 8. Product-specific memory adapters remain lossy and authority-safe

A future PLUR adapter MAY exchange Engrams and episodes, but PLUR activation/decay state remains retrieval metadata rather than Doll memory lifecycle authority. PLUR procedural or architectural Engrams cannot automatically become approved ProcedureRecords, DecisionRecords, PolicyRecords, or permissions.

A future PROJECTMEM adapter begins import-first. Project events may be preserved as imported project-experience claims with source provenance, while decisions, completion statements, plans, and fixes remain untrusted until promoted through the applicable Doll path.

Doll-to-PROJECTMEM export is optional and MUST be described as lossy unless evidence proves the selected mapping.

### 9. Derived indexes remain disposable or reproducible

Embeddings, vector indexes, BM25 indexes, RRF results, association graphs derived from usage, ranking caches, and similar retrieval structures are reproducible state unless a later accepted decision proves a continuity reason to classify a specific structure otherwise.

Doll MUST remain inspectable and recoverable when those structures are absent.

### 10. Future State Package signatures cover the whole declared package

Doll MAY add package signing in the long-term-operation phase. Signing and encryption remain separate concerns.

A signed package manifest MUST bind every declared package member through path, size, category, and cryptographic digest or an equivalently complete standard structure. Doll will not copy a partial signature scope that leaves declared relationship or index members outside the authenticated package description.

Canonicalization and cryptographic signatures MUST use established standards and reviewed libraries. Doll will not invent custom cryptography.

## Consequences

### Positive

- Doll keeps its broader continuity model instead of narrowing itself to portable memory.
- A general external memory adapter can interoperate with PAM without making PAM a storage dependency.
- Retrieval can become substantially smarter without allowing decay or embeddings to mutate truth.
- Failed attempts and lessons can survive model and conversation replacement as first-class project history.
- The existing safety and capability boundary can consume prior experience without granting the memory engine new authority.
- Product-specific adapters can be added without turning another application's schema into Doll State.
- Future package authenticity can cover the complete continuity package rather than only selected memory fields.

### Costs

- The design has more explicit layers than a single memory database.
- Usage signals and recall state need separate schemas and rebuild rules.
- ProjectExperienceRecord requires package, backup, restore, migration, and fresh-process coverage when implemented.
- Interoperability adapters require mapping and loss reports rather than simple field copying.
- Semantic retrieval and preflight require versioned deterministic behavior and additional acceptance tests.

## Rejected alternatives

### Make PAM the canonical Doll State format

Rejected because PAM is intentionally a memory interchange format and does not represent Doll's complete policy, permission, project, recovery, model/runtime, and continuity state.

### Create a Doll Portable Memory Standard

Rejected while a suitable open interchange target exists. Doll should add value through continuity and safe adapters rather than create avoidable ecosystem fragmentation.

### Copy PLUR activation and decay into MemoryRecord lifecycle

Rejected because retrieval usefulness and semantic truth are different properties. A memory becoming less frequently recalled does not make it false, unconfirmed, or safe to delete.

### Make embeddings authoritative

Rejected because embedding models and vector dimensions change. User-owned memory must survive index loss and model replacement.

### Convert all Doll State to append-only event sourcing

Rejected because immutable semantic work history is valuable for experience, while current policy, permission, binding, work, and project state still need explicit revisioned current representations.

### Let imported plans or procedural memories mutate project authority directly

Rejected because it would bypass existing user-controlled completion, procedure, checkpoint, permission, and policy boundaries.

### Use MCP as the canonical state format

Rejected because an interaction protocol does not replace durable, versioned, user-owned storage and migration semantics.

## Required follow-up

- add a normative memory-interoperability, recall, and project-experience extension;
- add acceptance identifiers for rebuildability, adapter authority, experience preservation, and continuity preflight;
- update the post-IMP-082 roadmap without reserving implementation identifiers prematurely;
- update repository agent guidance so the current implementation phase is not stale;
- implement new persisted record types only with versioning, package, backup, restore, migration, and fresh-process coverage in the same accepted slice;
- keep PAM, PLUR, PROJECTMEM, and MCP integrations optional and removable;
- defer package signing implementation to the long-term-operation phase.