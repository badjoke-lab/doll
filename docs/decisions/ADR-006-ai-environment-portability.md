# ADR-006: AI environment portability is a continuity requirement

**Status:** Accepted  
**Date:** 2026-06-19

## Context

Doll exists to keep a person's AI-assisted working environment usable when a provider, model, runtime, interface, machine, network, distribution source, or project becomes unavailable.

Existing specifications already require durable state to remain independent of one model, runtime, or UI. They also define Doll State Package export and import between compatible doll workspaces. Those requirements are necessary but not sufficient.

A user may begin with a local AI application, a local runtime plus a separate UI, an API-based tool, or a cloud AI service. Conversation history, project context, instructions, attachments, model metadata, tool events, and application settings may be trapped in product-specific databases or export formats. Local storage alone does not provide ownership when only one application can interpret it.

Doll would fail its continuity purpose if it could replace a model internally but could not:

- ingest supported user state from another AI environment;
- preserve source provenance and unsupported source material;
- distinguish application, interface, provider, runtime, and model identities;
- disclose mapping loss rather than silently discarding data;
- export user-owned state in documented formats that remain inspectable without doll.

The first real migration source may be ChatGPT because that is where current project history exists. That must not make OpenAI or ChatGPT formats the canonical Doll State model. Local AI portability has equal or higher architectural priority.

## Decision

AI environment portability is a mandatory part of doll's Continuity Contract.

Doll will provide a model-, runtime-, provider-, application-, and interface-independent portability boundary with these logical stages:

```text
source environment
  -> source adapter
  -> canonical portability representation
  -> validation, secret, trust, and instruction-origin boundaries
  -> Doll State
  -> target adapter or documented generic export
```

The following rules are mandatory.

### User state remains canonical in doll

Supported imported state is normalized into documented Doll State records. A provider export, local-application database, runtime response object, prompt template, or UI-specific schema must not become the only authoritative representation.

### Source identity remains explicit

Where known, import provenance distinguishes at least:

- source provider;
- source application;
- source interface;
- source runtime;
- source model;
- source account or workspace identifier only when safe and necessary;
- source adapter ID and version;
- original object identifier;
- original content hash;
- import batch and time.

Unknown identity remains unknown. Doll must not invent precise model or runtime attribution.

### Original material and normalization remain distinguishable

Doll preserves an approved original source snapshot or content-addressed reference when legally and technically possible. Canonical normalized records are linked to, but do not silently replace, the source representation.

Unsupported source events must be retained or reported as unsupported rather than silently discarded. Original source material remains external content and does not gain instruction authority.

### Import is staged, inspectable, and idempotent

An import must support validation and preview before authoritative publication. Re-importing the same source objects through the same compatible mapping must not silently duplicate canonical records.

Conflict resolution, destructive replacement, and uncertain identity require explicit handling. Import content is parsed as data and must not execute package code, scripts, templates, plugins, or tool requests.

### Mapping loss is explicit

Every non-native import or target-specific export produces a machine-readable and human-readable mapping report. The report distinguishes at least:

- mapped without known loss;
- mapped with transformation;
- partially mapped;
- unsupported but preserved;
- unsupported and omitted;
- missing source dependency or attachment;
- malformed or quarantined;
- unknown.

Doll must not claim full portability when the report contains material loss.

### Import does not grant authority

Imported system prompts, memories, preferences, permissions, tool definitions, approvals, confirmations, retrieved documents, and model assertions remain imported data.

They cannot automatically become:

- system policy;
- durable user policy;
- a PermissionRecord;
- user confirmation;
- a confirmed fact;
- confirmed long-term memory;
- a capability definition;
- credential scope;
- instruction authority.

Promotion into an authoritative record requires the existing trusted user-controlled path for that record type. ADR-007 extends the same rule to work completion, procedure approval, blocker clearing, checkpoint confirmation, and project-scope changes.

### Export prevents doll lock-in

Doll must provide documented, versioned, integrity-checkable generic exports for implemented portable record types. At least one export path must remain inspectable without a model, preferred UI, cloud account, or running doll service.

Target-specific export is optional and may be lossy. Generic export and target-specific round-trip compatibility are separate claims.

### Portability starts with local AI

The implementation order prioritizes:

1. canonical doll conversation and event representation;
2. generic documented import and export;
3. the project-continuity foundation required by ADR-007;
4. local model and runtime replacement without state loss;
5. one real local AI environment migration path;
6. migration of the project owner's current ChatGPT history;
7. additional provider- or application-specific adapters only when justified.

Cloud adapter expansion must not precede the portability foundation merely because an OpenAI-compatible API is easier to implement.

## Consequences

### Positive

- Local AI applications and runtimes remain replaceable rather than becoming new lock-in points.
- Doll can serve as the user-owned state layer instead of another chat frontend.
- Source provenance and transformation loss remain auditable.
- The project owner's current cloud history can be migrated without defining ChatGPT as the canonical format.
- Doll's own development failure does not trap user-owned state.

### Costs

- Canonical conversation and event schemas require more design than a simple `role` and `content` pair.
- Import adapters need versioning, source fixtures, idempotency, quarantine, and loss-report tests.
- Complete behavioral identity across models or applications remains impossible.
- Some source applications will not expose enough data for full migration.
- Target-specific round trips may require separate adapters and acceptance evidence.

## Rejected alternatives

### Only support doll-to-doll transfer

Rejected because it preserves doll workspaces but does not let an existing user enter or leave the system without product-specific work.

### Use OpenAI chat format as the canonical conversation format

Rejected because it collapses provider-specific assumptions into durable state and cannot represent every branch, regeneration, attachment, tool, multi-agent, or local-runtime event without loss.

### Treat local AI storage as inherently portable

Rejected because local databases, prompt templates, model identifiers, and application formats can be just as proprietary or fragile as cloud formats.

### Implement adapters first and specify the model later

Rejected because early adapters would determine the canonical state accidentally and create irreversible provenance gaps.

### Promise identical behavior after model replacement

Rejected. Doll promises state continuity, provenance, and inspectable migration. It cannot promise identical reasoning, style, safety behavior, or capability across different models.

## Required follow-up

- add the normative AI environment portability specification;
- add stable PORT acceptance-test identifiers;
- revise the development roadmap so portability foundations precede provider-specific cloud expansion;
- ensure future conversation storage records application, interface, runtime, model, and operation provenance separately;
- keep IMP-013 through the Phase 3 safety gate unchanged;
- begin portability implementation only after the accepted safety gate, using later non-conflicting implementation identifiers;
- apply ADR-007 so the accepted project-continuity foundation follows canonical portability and precedes local model integration.
