# doll specification decisions baseline

**Status:** Accepted baseline for the specification phase  
**Version:** 0.1  
**Date:** 2026-06-13

This document records the decisions that are already accepted before detailed implementation begins. It exists to prevent later specification work from reopening settled questions without an explicit architecture or product decision.

## 1. Product identity

### Accepted

- The project name is `doll`.
- `doll` is a **personal AI continuity system**.
- Its first purpose is to create a usable continuity environment for the project's owner.
- Its second purpose is to remain an open-source system that other people may use, inspect, adapt, and improve.
- General-market productization is not a prerequisite for the first implementation.

### Rejected

- Defining `doll` primarily as an AI companion.
- Defining `doll` primarily as a local chatbot.
- Defining `doll` primarily as a computer-control agent.
- Defining `doll` primarily as a model runner or model-distribution client.

## 2. Core principle

### Accepted

> **Local-complete, cloud-optional.**

The system must remain useful without cloud AI, API keys, account registration, remote license validation, or a permanent internet connection.

Cloud models may later be used as optional, explicitly approved performance extensions. They must not become the authoritative store for user state, memory, files, permissions, or recovery information.

### Consequences

- Local operation is the default.
- Automatic cloud fallback is prohibited.
- A local failure must fail locally and explain the available options.
- Cloud support is outside the local core and outside the initial completion criteria.
- Removing all cloud adapter code must not prevent the local system from starting.

## 3. Continuity before feature count

### Accepted priority order

1. continuity, ownership, portability, degradation, and recovery;
2. general-purpose AI capabilities;
3. optional personality, voice, avatar, automation, cloud, and mobile features.

The project will not compete by matching the feature count of existing local AI applications or agents.

### Required continuity concepts

The final specification must define:

- a Continuity Contract;
- graceful degradation behavior;
- a portable Doll State Package;
- an Offline Recovery Kit;
- a Continuity Test Suite.

## 4. What is durable

### Accepted

The durable core is user-controlled state, including where applicable:

- explicit long-term memory;
- preferences and policies;
- permissions and prohibitions;
- project and work history;
- documents and source references;
- research logs and citation records;
- generated artifacts and indexes;
- model manifests and validation records;
- runtime and recovery manifests;
- optional identity, personality, voice, and appearance configuration.

Models are replaceable reasoning engines. User state must not be stored only inside a model-specific prompt, proprietary database, or one user interface.

### Important limitation

The project may preserve and migrate personality-related state, but it cannot guarantee identical behavior across different models. The specification must promise state portability and continuity, not perfect behavioral identity.

## 5. Repository and data boundary

### Accepted

- Repository: `badjoke-lab/doll`.
- Visibility: public.
- Structure: one monorepo.
- License: Apache License 2.0 for project-owned source and documentation unless a file states otherwise.
- Lite and Heavy are profiles of one system, not separate repositories or duplicated products.
- Private user data and model files must remain outside the repository.

The public repository may contain:

- source code;
- schemas;
- migrations;
- tests using synthetic fixtures;
- examples;
- specifications and documentation;
- model manifests and validation metadata where legally distributable;
- training recipes and validation tools.

The public repository must not contain:

- personal conversations;
- user documents;
- private research caches;
- generated personal artifacts;
- API keys, credential values, or other secrets;
- model weights;
- private datasets;
- training checkpoints;
- personal evaluation records.

## 6. Initial user and deployment model

### Accepted for version 1

- one user;
- one primary local workspace;
- one local machine at a time;
- local-only server binding by default;
- no public hosted service;
- no enterprise account system;
- no multi-user authorization model.

Mobile access and multiple machines are later extensions and must not distort the first local architecture.

## 7. Profiles

### Lite

Lite is the lower-resource and fallback profile. It must support useful local operation on modest hardware, accepting lower speed and lower model capability.

### Heavy

Heavy is the higher-resource profile. It may add larger models, richer media processing, deeper retrieval, verification, model routing, and model-improvement workflows.

### Accepted profile rule

Lite and Heavy must share:

- the same core state model;
- the same security boundary;
- compatible backup and recovery formats;
- the same permission semantics;
- the same migration system.

### Deferred

A separate Standard profile will not be created until measurements show that it is necessary. An eventual `auto` profile may recommend or select capabilities based on detected hardware.

## 8. Platform policy

### Intended platforms

- macOS;
- Windows x64;
- Ubuntu Linux x64.

### Initial support labels

- macOS Intel: real-machine verification target;
- Windows x64: CI-tested beta until real-machine verification exists;
- Ubuntu Linux x64: CI-tested beta until real-machine verification exists;
- other distributions, ARM systems, and GPU configurations: experimental until validated.

The codebase must be cross-platform from the beginning. Lack of a Windows or Linux test machine does not permit POSIX-only assumptions.

## 9. Initial technical direction

### Accepted core direction

- Python 3.12;
- `uv` for the initial supported development and installation path;
- FastAPI for the local API boundary;
- Typer for management CLI commands;
- Pydantic for validated data contracts;
- SQLite and SQLite FTS5 for initial local metadata and text search;
- documented file formats such as Markdown, JSONL, JSON, and CSV where practical.

### Initial model runtime

- Ollama is the first runtime adapter target.

### Later runtime adapters

- llama.cpp;
- vLLM;
- local OpenAI-compatible servers.

No model runtime may be hard-coded into the durable state model.

## 10. User interface policy

### Accepted

- Open WebUI is the initial recommended conversational interface.
- Open WebUI is not the doll core and is not a mandatory dependency.
- The core must remain accessible through a local API and management CLI.
- Loss or replacement of the preferred UI must not make the state inaccessible.

### Deferred

- a dedicated doll web interface;
- a PWA;
- native mobile applications;
- visual avatar and companion interfaces.

## 11. Security and permissions

### Initial allowed capability class

- read approved local data;
- perform local search and analysis;
- perform explicit web search or URL retrieval;
- create new files inside the approved workspace;
- save research logs and artifacts;
- create backups.

### Initial prohibited capability class

- autonomous deletion;
- silent overwrite of existing files;
- unrestricted shell execution;
- automatic external upload;
- automatic email or social posting;
- purchases or financial transactions;
- account changes;
- secret collection;
- automatic cloud submission;
- writes outside the approved workspace.

The user must retain a separate, explicit management path for deleting their own data. AI autonomy and user control are not the same thing.

## 12. Memory policy

### Accepted memory classes

- session memory: temporary to the current interaction;
- suggested memory: proposed by the system but not yet durable;
- confirmed memory: explicitly approved or explicitly created durable memory.

### Accepted rules

- conversation content must not automatically become training data;
- secret values must never become durable memory; doll may retain only a non-secret reference to an externally stored credential;
- sensitive but non-secret personal information must not become durable memory by default;
- the user must be able to inspect, edit, export, and delete confirmed memory;
- memory passed to a model must be scoped to the current need.

## 13. Model acquisition and lifecycle

### Accepted

- Models are not bundled in the GitHub repository.
- Model downloads must not occur silently.
- Before acquisition, the user must be shown the source, license, approximate size, runtime requirements, and expected hardware needs.
- Acquired models must be recorded with source, revision, checksum, license, quantization, runtime compatibility, and validation state.
- New models must not automatically replace the active model.
- The lifecycle must support quarantine, evaluation, candidate status, activation, previous-version retention, fallback, and rollback.

### Standard model eligibility

A model may be included in the validated catalog only when its local execution and storage terms are sufficiently clear for the intended use. Models with unclear provenance, unclear rights, mandatory remote code, or incompatible restrictions are not standard targets.

## 14. Hardware purchase policy

### Accepted

No Heavy-specific hardware will be purchased before Lite v1.0 is implemented and measured.

The sequence is:

1. build and test Lite on the current machine;
2. measure real bottlenecks;
3. define the required Heavy workloads and model sizes;
4. establish hardware requirements;
5. evaluate available hardware at that time.

Heavy code may be designed and tested with mocks before real Heavy hardware is available, but Heavy must not be declared complete without real-machine validation.

## 15. Cloud policy

### Accepted

- Cloud APIs are not part of Lite v1.0 or Heavy v1.0 completion criteria.
- The architecture may define an optional cloud gateway boundary.
- Provider-specific support is implemented only after the local system is complete.
- Any later cloud use must be opt-in and auditable.
- Original files, long-term memory, and full conversation history must not be sent by default.
- Secret values remain outside ordinary Doll State and must not be exposed to models; later credential use must pass through the accepted external secret-store and credential-broker boundary.
- The user must be shown the destination and outbound content before transmission unless they explicitly configure a narrower allowlisted mode.

## 16. Mobile policy

### Accepted order

1. PC Lite;
2. PC Heavy foundation;
3. mobile browser or companion access;
4. PWA;
5. Android hybrid or edge mode;
6. iOS hybrid or edge mode.

A user's own remote PC running doll is distinct from a third-party cloud AI provider and must be modeled separately in security and permission rules.

## 17. Release and publication policy

### Accepted

- The repository is public from the start.
- The project status begins as pre-alpha.
- Public repository availability is not the same as a stable release.
- Lite v1.0 is the first intended generally usable release gate.
- Claims must match accepted tests.

### First implementation objective

The first usable proof is not a chatbot or a full general-purpose assistant. It is a model-independent continuity demonstration capable of proving that:

- the durable core starts locally without network access, cloud credentials, or a model runtime;
- explicit durable state is separate from every model and UI;
- state can be exported and imported into an empty compatible target;
- verified state and workspace backups can be restored into empty compatible targets;
- restored identity, revision, records, links, audit history, and artifact bytes validate in a fresh process;
- failed import or restore preserves the last known good state;
- the system refuses unsafe archive paths and writes outside its workspace.

Local conversation and model replacement become a separate proof only after the model-independent safety boundary has passed its acceptance gate.

## 18. Specification source and generated document

### Accepted

- files under `docs/spec/` are the maintainable source specification;
- a generated combined specification will be produced as `DOLL_FINAL_SPEC.md` or under a distribution directory;
- the generated document must not be edited directly;
- architecture decision records may be stored separately under `docs/decisions/`;
- competitor research may be stored under `docs/research/` but is not part of the normative specification.

## 19. Deferred decisions

The following are intentionally not fixed yet:

- the exact Heavy computer model;
- specific future cloud providers;
- final Android or iOS frameworks;
- dedicated UI design;
- specific long-term recommended model names;
- zero-from-scratch foundation-model training;
- general-market packaging and support commitments.

These must not block the initial specification or Lite development.

## 20. Change control

Changing this baseline requires a dedicated decision document or pull request that:

- identifies the previous decision;
- explains the evidence for changing it;
- describes compatibility and migration effects;
- evaluates continuity and security consequences;
- updates affected specifications and acceptance tests.

Unrelated feature pull requests must not quietly alter these decisions.
