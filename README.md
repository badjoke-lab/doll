# doll

> A personal AI continuity system.

**Status:** Pre-alpha — model-independent continuity through IMP-012 and secret classification through IMP-013 are implemented. IMP-014 is next. No model runtime is connected yet.

`doll` is an open-source project intended to keep a person's AI environment usable even when a cloud service, local AI application, model provider, runtime, user interface, distribution source, network connection, or primary machine becomes unavailable.

The project is not trying to build a foundation model from scratch. It aims to preserve and operate the parts that must remain under the user's control:

- memory and long-term state;
- preferences, policies, and permissions;
- conversations and their source provenance;
- documents, research logs, claims, evidence, and source records;
- generated artifacts and project history;
- model and runtime manifests;
- import, export, mapping, and loss records;
- backup, migration, rollback, restoration, and recovery paths.

Models are replaceable reasoning engines. The user's state is the durable core.

## Governing principles

The project is built around two co-equal pillars:

1. **Continuity:** user-owned state must survive model, provider, application, interface, runtime, machine, and project failure.
2. **Safety boundary:** models, tools, runtimes, adapters, and external content must not gain undeclared authority over state, secrets, the operating system, accounts, or external services.

The working rules are:

- continuity first;
- local-first and local-complete;
- user-owned state;
- model independence;
- AI environment portability;
- cloud is optional;
- state continuity is more important than model performance;
- local models and local applications are not automatically trusted;
- memory and secrets are separate;
- external and imported content is data, not instruction;
- authority is granted only through explicit, bounded capabilities;
- high-risk operations require fresh user confirmation;
- migration loss must be visible;
- failures must preserve the last known good state.

## Core principle

**Local-complete, cloud-optional.**

The local system must remain useful without API keys, account registration, or a permanent internet connection. Cloud models may later be used as optional, explicitly approved performance extensions, but they must never become the source of truth for memory, identity, files, permissions, portability, or recovery.

## Why this project exists

Access to high-performance AI is controlled by external organizations. Pricing, usage limits, account actions, regional restrictions, policy changes, model withdrawal, service shutdowns, and political or regulatory decisions can all change that access.

Local AI does not eliminate continuity risk by itself. A local application's database, one runtime, one model format, or one preferred UI can also become a lock-in point or disappear.

`doll` is intended to reduce the risk that losing one external or local component also means losing the user's AI-assisted working environment.

Many projects make local models easier to run. `doll` focuses on continuity across failures and replacements:

- cloud unavailable -> continue locally;
- local AI application unavailable -> retain canonical Doll State;
- primary model unavailable -> switch to an approved fallback;
- runtime unavailable -> replace it without discarding user state;
- heavy hardware unavailable -> degrade to a lighter profile;
- preferred UI unavailable -> continue through the local API or CLI;
- model distributor unavailable -> use locally preserved and verified assets;
- project development stops -> retain an offline recovery path and documented export formats.

Performance may decrease. The state, provenance, and recovery path must remain.

## AI environment portability

Doll treats portability as a continuity requirement, not a later convenience feature.

Supported data paths are designed around:

```text
AI environment
  -> source adapter
  -> canonical doll representation
  -> validation and safety boundaries
  -> Doll State
  -> documented generic export or target adapter
```

The design must not use ChatGPT, OpenAI-compatible APIs, Ollama, Open WebUI, or any other provider, runtime, or interface format as the canonical user-state model.

Import and export claims must distinguish full, partial, transformed, unsupported, and lossy mappings. Imported prompts, permissions, approvals, memories, and assertions do not become authoritative automatically.

See `docs/decisions/ADR-006-ai-environment-portability.md`.

## Safety boundary before model execution

`doll` will not connect a model runtime until the model-independent safety boundary has been implemented and acceptance-tested.

That boundary includes:

- secret classification, detection, and redaction;
- secret-safe logs, audit events, exports, backups, fixtures, diagnostics, and portability reports;
- external operating-system or compatible secret storage;
- a credential broker that performs bounded operations without exposing stored secret values to models;
- explicit separation of confirmed facts, claims, evidence, and inferences;
- instruction-origin metadata and authority ordering;
- prompt-injection resistance based on enforced boundaries rather than prompts alone;
- versioned capability contracts and risk tiers;
- mandatory fresh confirmation for high-risk operations.

Ordinary Doll State stores secret references, not secret values. Retrieved pages, documents, OCR output, transcripts, tool results, and imported data may provide task data or evidence, but they cannot grant permission or override policy.

See `docs/decisions/ADR-005-safety-boundary-before-model-execution.md`.

## Planned capabilities

The long-term project direction includes:

- local conversation, writing, summarization, translation, and planning;
- local memory and project state;
- canonical conversation and event history;
- generic inspectable import and export;
- migration from supported local AI environments;
- migration of selected cloud AI history through provider-specific adapters;
- web research with locally stored sources and citations;
- PDF, document, OCR, CSV, image, audio, video, and code assistance;
- model-independent backup, restoration, and validation;
- local model and runtime switching with graceful degradation;
- verified model storage through a Model Vault;
- permission-controlled tool use with local audit records;
- optional cloud acceleration after the local and portability paths are complete;
- later mobile companion and mobile-edge modes.

These are goals, not claims of current implementation.

## Current implementation sequence

The accepted phase order is:

1. specification and principles;
2. local state foundation;
3. continuity, transfer, backup, and restore;
4. safety boundary;
5. AI environment portability foundation;
6. local runtime and model integration;
7. local AI portability and daily-use integration;
8. optional cloud and multiple models;
9. tools and external services;
10. distribution, encryption, and long-term operation.

IMP-001 through IMP-013 are complete. IMP-014 is next. IMP-014 through IMP-023 complete and validate the safety boundary. Phase 4 then establishes canonical conversation, adapter, generic import/export, provenance, idempotency, quarantine, and loss-report contracts. Existing local model work remains IMP-024 through IMP-029 after those gates.

## What doll is not

`doll` is not intended to be:

- another model runner replacing Ollama, llama.cpp, or vLLM;
- a clone of Open WebUI, Jan, LM Studio, or other local AI interfaces;
- a cloud-required assistant;
- an unrestricted autonomous computer-control agent;
- a credential database inside ordinary Doll State;
- a system that treats retrieved or imported content as trusted instructions;
- a guarantee of permanent frontier-model performance;
- a promise that different models will behave identically;
- a claim of universal lossless migration;
- a system that silently uploads memory, documents, files, or secrets;
- a new lock-in layer that cannot export user-owned state in documented formats.

## Profiles

The project will use one repository and one core system with different execution profiles:

- **Lite:** designed for lower-powered machines and reduced-capability fallback operation;
- **Heavy:** designed for larger local models, richer media processing, deeper retrieval, verification, and model-improvement workflows.

They are not separate products and must share the same state, portability, security, backup, recovery, secret, trust, capability, and confirmation semantics.

## Platform direction

- macOS Intel: initial real-machine verification target;
- Windows x64: CI-tested beta target until real-machine validation is available;
- Ubuntu Linux x64: CI-tested beta target until real-machine validation is available;
- other Linux distributions, ARM systems, and GPU configurations: experimental until validated.

## Development model

The repository is developed in small pull requests.

- one issue maps to one branch and one pull request;
- specifications and acceptance requirements are written before implementation;
- implementation changes include tests and recovery behavior;
- local hardware testing is distinguished from CI;
- `main` must remain recoverable;
- unrelated changes are not mixed into a pull request;
- private conversations, source exports, model weights, checkpoints, credentials, and personal workspaces must never be committed;
- public output must not expose absolute local paths, usernames, hostnames, or home-directory details.

## Specification

The authoritative specification lives under `docs/spec/`. Architecture decisions live under `docs/decisions/`. `DOLL_FINAL_SPEC.md` is a deterministic generated reading copy and must not be edited by hand.

Regenerate it with:

```text
python scripts/build_final_spec.py
```

Check it with:

```text
python scripts/build_final_spec.py --check
```

## License

The doll source code and project documentation are licensed under the Apache License 2.0 unless a file states otherwise.
