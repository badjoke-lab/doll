# ADR-001: Core boundaries and authoritative state

**Status:** Proposed for acceptance with PR-002  
**Date:** 2026-06-13

## Context

Doll must remain usable when models, runtimes, UIs, providers, or hardware change. Existing local AI applications often store important state inside one UI database, one model prompt, one runtime tag system, or one cloud account. That would violate the Continuity Contract.

The project therefore needs an explicit answer to two questions:

1. Which component owns durable state?
2. Which components are replaceable adapters?

## Decision

The doll-managed private workspace is the authoritative source of user-controlled state.

The durable core owns:

- state schemas and versions;
- memory, policy, permission, project, source, artifact, model, runtime, audit, backup, and migration records;
- export, import, backup, restoration, and migration behavior;
- workspace identity and revision.

The following are replaceable adapters or clients:

- Open WebUI and other conversational UIs;
- Ollama, llama.cpp, vLLM, and other runtimes;
- individual language, embedding, vision, and speech models;
- document, search, OCR, audio, video, and browser tools;
- optional cloud providers;
- optional mobile clients.

Models may propose actions or state changes, but all side effects must pass through doll services and the Capability Broker.

No adapter may become the only store for authoritative state.

## Consequences

### Positive

- Model and UI replacement do not require discarding user state.
- Backup and recovery can be defined independently of third-party applications.
- Lite and Heavy can share one state format.
- Optional tools can disappear without preventing core startup.
- Security policy can be enforced at one boundary.
- Cloud support can remain optional.

### Negative

- Doll must implement and maintain its own state schemas and migrations.
- Existing UI or runtime databases cannot be treated as sufficient backups.
- Adapter integrations require explicit mapping and provenance records.
- Some third-party features may need duplication at the metadata or orchestration layer.
- Early development is slower than directly coupling a UI to a runtime.

## Rejected alternatives

### Use Open WebUI as the authoritative database

Rejected because loss, replacement, or incompatible upgrade of the UI would threaten continuity.

### Use Ollama tags and configuration as the model registry

Rejected because runtime-specific identifiers are not stable model identities and cannot represent the full license, revision, checksum, and validation lifecycle.

### Store identity and memory only in system prompts

Rejected because prompt content is model- and context-dependent, difficult to inspect, and insufficient for structured migration and conflict handling.

### Let each adapter own its own durable records

Rejected because backup, migration, security, and portability would become fragmented and inconsistent.

### Make the cloud account the synchronization authority

Rejected because cloud independence is a non-negotiable product requirement.

## Implementation constraints

- All authoritative record types must have versioned schemas.
- Adapter caches must be classed as reproducible or disposable unless explicitly promoted.
- The private workspace must not default inside the repository checkout.
- Model and runtime identifiers must be separate.
- The local API and CLI must provide state inspection and recovery paths independent of the preferred UI.
- Capability and audit records must identify adapter operations and side effects.

## Validation

This decision is validated when the first continuity proof demonstrates that:

1. state is created through doll-managed services;
2. the preferred UI can be absent without making the state inaccessible;
3. the active model and runtime can be changed without deleting state;
4. a backup can restore the state into an empty workspace;
5. optional adapters can be missing while the core still starts;
6. an attempted write outside the workspace is refused.
