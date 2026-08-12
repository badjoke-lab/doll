# Memory interoperability, recall, and project experience

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `03a-ai-environment-portability.md`, `03b-project-continuity-and-resumption.md`, `04-security-permissions-and-threat-model.md`, `ADR-008-memory-interchange-recall-and-project-experience.md`

## 1. Purpose

This specification extends Doll State with explicit boundaries between:

- durable memory content;
- external memory interchange;
- recall, ranking, and consolidation behavior;
- semantic project experience;
- deterministic pre-action continuity checks.

The purpose is to make memory more useful and interoperable without narrowing doll from a continuity system into a memory database and without allowing retrieval mechanics, imported formats, models, or agent protocols to gain authority over canonical state.

This document is a forward implementation contract. Merging it does not claim that the new record types, adapters, recall engine, MCP surface, or signing behavior are already implemented.

## 2. Memory layer and continuity layer

Doll distinguishes two related layers.

### 2.1 Memory layer

The memory layer answers:

> What information from prior interaction or work should remain available and, when relevant, be recalled for a later task?

It may include:

- confirmed facts and durable context;
- user preferences that are properly represented as memory rather than policy;
- remembered relationships;
- project-scoped context;
- relations and contradictions between memories;
- memory candidates and consolidation review;
- recall signals and derived retrieval state.

### 2.2 Continuity layer

The continuity layer answers:

> If the model, provider, runtime, interface, conversation, machine, or application changes, what user-owned state is required to reconstruct and resume the AI-assisted environment safely?

It includes the memory layer and also includes, where enabled:

- identity and preferences;
- policy and permission;
- projects and decisions;
- work items and blockers;
- procedures and checkpoints;
- project experience;
- conversations and artifacts;
- sources, evidence, claims, and provenance;
- model, runtime, and binding records;
- import mappings and portability losses;
- backup, migration, restore, and recovery state.

Portable memory is therefore one continuity mechanism. It is not a complete substitute for Doll State or the Doll State Package.

## 3. Canonical state, interchange, and interfaces

### 3.1 Canonical Doll State

Authoritative Doll State remains defined by the accepted versioned Doll record contracts and managed files.

No external memory format, provider export, agent protocol, retrieval index, embedding representation, or product-specific database becomes canonical merely because doll can import, export, or query it.

### 3.2 Interchange formats

Doll SHOULD use suitable published, open, versioned interchange formats through adapters when that avoids an unnecessary Doll-specific external standard.

An interchange adapter MUST declare:

```text
adapter_id
adapter_version
source_or_target_format
supported_format_versions
mapping_rules_version
loss_categories
network_behavior
```

The generic Phase 4A import/export, provenance, idempotency, quarantine, mapping, loss, and reviewed-publication rules continue to apply.

### 3.3 Protocol interfaces

A protocol such as MCP is an access interface, not a persistence schema.

Protocol input MUST be assigned an instruction origin and authority class before it may affect any accepted management path. A protocol client's claim that an object is a policy, permission, approved procedure, trusted memory, completed task, or confirmed decision does not make it authoritative.

A future write-capable external-agent interface MUST begin with proposal-only operations unless a later accepted specification names a narrower trusted mutation and its confirmation requirements.

## 4. Authoritative memory versus recall state

### 4.1 Authoritative memory meaning

For a confirmed memory, the following remain part of the durable semantic record or its accepted linked state:

- content;
- subject;
- confirmation state;
- source and provenance;
- validity interval;
- confidence where defined;
- sensitivity;
- related and contradictory memory links;
- record revision and lifecycle.

These properties are not recalculated from retrieval frequency.

### 4.2 Recall data is not memory truth

The following are recall or retrieval properties rather than authoritative semantic truth:

- last recall time;
- recall frequency;
- injection frequency;
- positive, negative, or neutral usefulness feedback;
- lexical match scores;
- semantic similarity scores;
- embedding IDs and vector dimensions;
- activation or decay scores;
- ranking position;
- context-budget priority;
- derived co-access associations.

The optional `last_recalled_at` and `recall_count` fields previously listed under `MemoryRecord` in `03-doll-state-memory-and-storage.md` are **deprecated as new authoritative MemoryRecord fields**. Existing persisted or imported values MAY remain readable for compatibility, but new implementations MUST place equivalent behavior in the usage-signal or derived-recall boundary defined here.

A retrieval update MUST NOT increment the authoritative MemoryRecord revision merely because the memory was searched, ranked, selected, or injected.

## 5. MemoryUsageSignalRecord

A later implementation MAY persist minimal memory-use evidence when it has clear value for local retrieval quality, explainability, or user review.

When persisted, it uses a versioned `MemoryUsageSignalRecord` rather than mutating the MemoryRecord.

Initial logical fields are:

```text
signal_id
memory_id
signal_kind
occurred_at
actor_type
project_id
session_id
operation_id
retrieval_method_id
context_selection_policy_version
provenance
sensitivity
```

Optional bounded fields may include:

```text
feedback_class
reason_code
related_memory_ids
```

Initial signal kinds may include:

```text
recalled
selected_for_context
helpful
irrelevant
contradiction_surfaced
explicitly_reinforced
```

### 5.1 Signal authority

A usage signal describes an observed retrieval or feedback event. It does not establish that the memory is true, false, approved, obsolete, or safe to delete.

The signal MUST identify the actor or method that produced it. Model-generated usefulness feedback and imported usage counters remain lower-authority evidence than explicit user feedback.

### 5.2 Privacy and boundedness

Usage signals SHOULD retain identifiers and bounded reason codes rather than duplicate memory bodies, prompts, generated responses, native paths, or private environment details.

A signal implementation MUST be locally inspectable and deletable under the applicable retention policy.

### 5.3 Continuity requirements

`MemoryUsageSignalRecord` is authoritative operational history if implemented. Its first accepted implementation MUST include, in the same slice:

- explicit schema versioning;
- record validation;
- Doll State Package registration and validation;
- backup and restore coverage;
- fresh-process inspection;
- migration or compatibility handling;
- secret and sensitivity tests.

The absence of usage signals MUST NOT make confirmed memory uninterpretable.

## 6. RecallState and reproducible retrieval indexes

`RecallState` is a derived view or cache. It is not an authoritative Doll State record unless a future architecture decision explicitly changes that classification.

A RecallState implementation SHOULD identify:

```text
memory_id
memory_revision
algorithm_id
algorithm_version
context_selection_policy_version
generated_at_or_source_revision
lexical_score
semantic_score
recency_component
usefulness_component
scope_component
final_priority
index_or_embedding_reference
```

Not every implementation needs every score. Missing optional retrieval components MUST have documented neutral behavior.

### 6.1 Rebuildability

RecallState, embeddings, BM25/FTS indexes, vector indexes, RRF results, ranking caches, and derived association graphs MUST be rebuildable from authoritative records plus any retained usage signals they declare as inputs.

Deleting or corrupting a reproducible retrieval index MUST NOT:

- delete or archive confirmed memory;
- change memory confirmation state;
- alter policy, permission, project, decision, or work authority;
- block state inspection, backup verification, restore, or generic export.

### 6.2 Model independence

An embedding model or semantic-search model is replaceable. Changing it MAY change retrieval quality or ordering, but MUST NOT change canonical memory identity or semantic content.

Embeddings MUST NOT be the only representation of a memory.

### 6.3 Local-first retrieval

The default recall path for a local-complete release MUST operate without a cloud embedding or ranking service.

Semantic retrieval MAY be absent. A deterministic lexical fallback MUST remain available for the release profiles that claim local memory search.

## 7. Context selection and transparency

Existing explicit selection remains a valid and preferred control path.

A later automatic or semi-automatic recall feature MUST:

- operate under a versioned context-selection policy;
- apply project, sensitivity, validity, and context-budget limits;
- reject secret values and disallowed records before model context construction;
- preserve instruction-origin separation;
- expose which memory IDs were selected where practical;
- permit the user to request a turn without long-term memory;
- avoid automatic expansion from one selected record into unrestricted linked-record traversal;
- treat model-proposed retrieval choices as proposals or ranking input, not authority.

Semantic retrieval does not imply semantic authority.

## 8. Consolidation, duplicates, and contradictions

Doll MAY add a memory-consolidation workflow that detects:

- likely duplicates;
- compatible extensions;
- contradictions;
- expired or stale validity;
- overly broad memories that should be split;
- related memories that may benefit from explicit links.

Detection MAY use deterministic comparison, local models, or optional external models under the accepted outbound boundary.

The output MUST remain a review candidate until the target memory contract's trusted mutation path accepts it.

A consolidation process MUST NOT automatically:

- merge confirmed memories;
- rewrite content;
- supersede a confirmed memory;
- convert a suggestion into confirmed memory;
- archive or delete memory because recall activation is low;
- treat repeated model output as user confirmation.

A contradiction remains inspectable until explicitly resolved. Historical provenance MUST survive merge or supersession.

## 9. General memory interoperability profile: PAM

Portable AI Memory (PAM) v1.x is the first high-priority general memory-interchange target. Initial implementation targets the published PAM v1.0 contract through a version-bound adapter.

PAM support MUST remain optional and MUST NOT be required to inspect or recover Doll State.

### 9.1 PAM import

A PAM importer MUST use the generic staged import path and MUST:

- preserve exact source bytes or an approved content-addressed source reference where permitted;
- bind the import to the PAM format version and Doll adapter version;
- validate supported PAM structure without network dependency;
- preserve source identifiers and provenance where safe;
- map unsupported types, relations, conversations, access metadata, lifecycle values, signatures, and embeddings through explicit mapping or loss reporting;
- keep imported memory content external and untrusted until reviewed for the applicable Doll target;
- remain idempotent for unchanged source objects.

PAM `content_hash` is source-format integrity metadata. Doll MUST NOT use PAM's normalized content hash as the canonical Doll record identity or as proof that two semantically sensitive values are interchangeable.

PAM `access` or equivalent foreign permission metadata MUST NOT create Doll PermissionRecords or local sharing authority.

A valid PAM signature MAY be verified and preserved as source evidence. It does not replace Doll provenance, user confirmation, or package trust rules.

### 9.2 PAM export

A PAM exporter MAY export the subset of confirmed Doll memories and relations that can be represented by the selected PAM target version.

It MUST:

- state the target PAM version;
- calculate PAM-required fields according to that version;
- report Doll fields or semantics that cannot be represented;
- keep optional embeddings non-authoritative;
- distinguish PAM memory export from complete Doll continuity export.

A successful PAM export MUST NOT be described as a complete Doll State Package or complete AI-environment migration.

## 10. Product-specific interoperability profiles

### 10.1 PLUR / Engram

A future PLUR Engram adapter is lower priority than the general PAM profile and the core Doll recall boundary.

The adapter MUST treat PLUR-specific activation, decay, usage, emotional weight, injection ranking, and learned association values as external memory-engine metadata. Those values MUST NOT directly change Doll MemoryRecord lifecycle or confirmation state.

Mapping guidance:

- terminological and behavioral Engrams may become imported memory candidates or imported external memory records according to the accepted target path;
- procedural Engrams MUST NOT automatically become approved ProcedureRecords;
- architectural Engrams MUST NOT automatically become DecisionRecords or PolicyRecords;
- PLUR episodes may map to imported project-experience claims when a safe project relationship exists;
- foreign visibility or sharing metadata cannot grant Doll permission authority.

An export to PLUR MUST disclose fields and semantics that are lossy, including Doll authority, evidence, project-state, and policy distinctions that Engrams do not represent directly.

### 10.2 PROJECTMEM

A future PROJECTMEM adapter begins import-first and MUST bind behavior to the actual supported application/export version rather than assume that a paper description and current implementation are identical.

PROJECTMEM events may be preserved as imported `ProjectExperienceRecord` claims with source provenance. Imported decisions, fixes, completed-state wording, plans, warnings, and agent-authored summaries MUST NOT directly mutate Doll DecisionRecords, WorkItem completion, Procedure approval, checkpoints, policies, or permissions.

Doll-to-PROJECTMEM export is optional. If implemented, it MUST be described as lossy unless the exact selected mapping has acceptance evidence.

## 11. ProjectExperienceRecord

`ProjectExperienceRecord` preserves semantic work history that should survive a conversation or model replacement.

It is distinct from operational audit.

Initial logical fields are:

```text
experience_id
project_id
work_item_id
event_kind
summary
outcome
occurred_at
assertion_state
related_record_ids
evidence_ids
source_ids
supersedes_id
provenance
sensitivity
```

Optional implementation-specific bounded metadata MAY identify a method or tool class, but MUST NOT duplicate raw secrets, full prompts, generated responses, or unnecessary command output.

### 11.1 Event kinds

The first schema SHOULD support:

```text
observation
hypothesis
attempt
outcome
resolution
lesson
```

Unknown kinds MUST NOT be silently coerced to another kind.

### 11.2 Outcomes

Where applicable:

```text
worked
failed
partial
unknown
```

An outcome is a claim whose trust depends on `assertion_state`, provenance, and linked evidence. The word `failed` in imported text is not automatically trusted merely because it maps to the field.

### 11.3 Assertion state

The schema MUST distinguish at least the semantic authority source needed to tell apart:

- user-recorded or user-confirmed experience;
- deterministic system observation with bounded evidence;
- imported external claim;
- model-proposed experience.

Exact enum names are assigned by the implementation specification.

### 11.4 Append-oriented history

After publication, the semantic event payload is append-oriented.

A material correction SHOULD create a new experience record linked through `supersedes_id` or another accepted correction relationship. The earlier record remains inspectable.

Archival or retention metadata MAY change under the common record lifecycle, but the system MUST NOT silently rewrite a failed attempt into a successful one.

### 11.5 Not global event sourcing

ProjectExperienceRecord does not replace revisioned authoritative current state.

Doll continues to store current project objectives, work status, decisions, policies, permissions, bindings, and checkpoints through their accepted record contracts.

### 11.6 Continuity integration

The first accepted ProjectExperienceRecord implementation MUST include:

- versioned schema validation;
- State Package registration and link validation;
- backup and restore;
- fresh-process inspection;
- deterministic export;
- sensitivity and secret controls;
- migration or read-compatibility behavior;
- explicit Resume Bundle inclusion rules or explicit omission and loss reporting.

## 12. ContinuityPreflight

`ContinuityPreflight` is a deterministic, model-independent read-only check over relevant accepted state before a proposed action or capability request proceeds.

It may inspect, within bounded scope:

- PolicyRecords;
- PermissionRecords;
- relevant DecisionRecords;
- approved ProcedureRecords;
- WorkItem blockers and dependencies;
- ProjectExperienceRecords;
- applicable capability and confirmation requirements.

### 12.1 Output

A preflight result SHOULD contain:

```text
rule_set_id
rule_set_version
project_id
proposed_action_class
status
matched_record_ids
warning_codes
authoritative_blocker_ids
requires_confirmation
```

The result MUST avoid raw secret values and unnecessary source content.

### 12.2 Authority

ContinuityPreflight cannot grant permission.

A prior failed experience normally produces a warning with supporting record IDs. It does not create a hard deny merely because the retrieval system ranked it highly.

A hard denial may be surfaced only when it comes from an existing authoritative policy, permission, blocker, capability rule, or another accepted deterministic authority source.

Imported or model-proposed experience MAY contribute advisory context but MUST NOT independently become a hard authority.

### 12.3 Integration with the safety boundary

ContinuityPreflight MUST compose with, not replace, the accepted Capability Broker, permission, risk, credential, confirmation, and prompt-defense boundaries.

A model cannot bypass preflight by omitting prior history from its prompt. The authoritative check is performed outside model reasoning.

## 13. Future agent interface through MCP

MCP MAY be used in Phase 8 or later for interoperable local agent access.

Initial Doll MCP direction is:

- read-only inspection for explicitly scoped non-secret state;
- deterministic search and context retrieval;
- proposal creation where the target schema already permits model or external proposals;
- no direct completion, procedure approval, checkpoint confirmation, policy creation, permission grant, credential access, or high-risk confirmation from protocol content.

A remote MCP transport, multi-user interface, or cross-machine agent requires a separate threat-model and authentication decision. Local MCP support MUST NOT silently open a network listener.

## 14. Package integrity and future signing

Current Doll State Package checksum verification remains the integrity baseline.

A future Phase 9 signing extension MUST separate:

- integrity hashes;
- authenticity signatures;
- encryption/confidentiality.

The signed representation MUST bind the complete declared package inventory. At minimum the authenticated manifest description includes every member's:

```text
path
category
size_bytes
content_digest
```

plus package-format identity and the deterministic metadata required to prevent member substitution or omission.

Where JSON canonicalization is required, Doll SHOULD use an established canonicalization standard such as RFC 8785 rather than a project-specific serializer contract for cryptographic meaning.

A first signing implementation SHOULD use a broadly reviewed signature primitive and library, such as Ed25519 where platform and dependency review accept it.

Signature verification MUST NOT require a network identity provider. DID or remote identity systems remain optional future integrations rather than package prerequisites.

The project MUST NOT invent custom cryptography.

## 15. Compatibility and migration

This specification introduces no immediate physical SQLite migration and no runtime behavior change by itself.

When the new persisted records are implemented:

- each receives an explicit schema version;
- package category registration and compatibility rules are added in the same slice;
- existing State Package v2 inputs that omit the new optional categories remain readable unless a later accepted package-version decision says otherwise;
- backup and restore remain backward compatible for supported earlier state schemas;
- imported external metadata never supplies missing authoritative user decisions;
- derived RecallState may be discarded and rebuilt during migration.

Deprecating `MemoryRecord.last_recalled_at` and `recall_count` for new authoritative writes does not require deleting older compatible data. Migration may preserve legacy values as imported or compatibility metadata while moving future behavior to usage signals.

## 16. Claim discipline

The following are separate claims:

- confirmed-memory persistence;
- deterministic local memory search;
- semantic retrieval;
- recall feedback;
- memory consolidation;
- PAM import;
- PAM export;
- PLUR import or export;
- PROJECTMEM import or export;
- ProjectExperienceRecord continuity;
- ContinuityPreflight;
- MCP read interface;
- MCP proposal interface;
- signed Doll State Package.

Passing one claim MUST NOT be used as evidence for another.

In particular:

- a valid PAM file is not proof of complete Doll continuity;
- a working embedding index is not proof that memory survives index loss;
- a successful imported PROJECTMEM event is not proof of trusted work completion;
- a preflight warning is not a permission denial unless an accepted authoritative rule produces that denial;
- checksum verification is not a cryptographic-authenticity claim.

## 17. Acceptance requirements

The applicable behavior MUST pass `08c-memory-interoperability-recall-and-project-experience-acceptance.md` before the corresponding stable claim is made.

Adding this specification does not retroactively invalidate accepted Phase 1 through Phase 5 evidence or completed bounded Phase 6 slices. New tests become blocking only for the feature or phase claim identified by the post-IMP-083 roadmap extension.

## 18. External design references

The following external designs informed this specification but are not runtime dependencies or sources of Doll authority:

- Portable AI Memory (PAM) specification v1.0;
- PLUR Engram specification v2.1;
- PROJECTMEM v0.2.x and the PROJECTMEM paper.

Doll adapters MUST bind to the exact supported external version at implementation time and MUST re-check upstream behavior before claiming compatibility.