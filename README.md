# doll

> A personal AI continuity system.

**Status:** Pre-alpha — specification and continuity architecture phase. Not ready for general use.

`doll` is an open-source project intended to keep a person's AI environment usable even when a cloud service, model provider, user interface, distribution source, network connection, or primary machine becomes unavailable.

The project is not trying to build a foundation model from scratch. It aims to preserve and operate the parts that must remain under the user's control:

- memory and long-term state;
- preferences, policies, and permissions;
- documents, research logs, and source records;
- generated artifacts and project history;
- model and runtime manifests;
- backup, migration, rollback, and recovery paths.

Models are replaceable reasoning engines. The user's state is the durable core.

## Core principle

**Local-complete, cloud-optional.**

The local system must remain useful without API keys, account registration, or a permanent internet connection. Cloud models may later be used as optional, explicitly approved performance extensions, but they must never become the source of truth for memory, identity, files, permissions, or recovery.

## Why this project exists

Access to high-performance AI is controlled by external organizations. Pricing, usage limits, account actions, regional restrictions, policy changes, model withdrawal, service shutdowns, and political or regulatory decisions can all change that access.

`doll` is intended to reduce the risk that losing one external service also means losing the user's AI-assisted working environment.

Many projects make local models easier to run. `doll` focuses on continuity across failures and replacements:

- cloud unavailable → continue locally;
- primary model unavailable → switch to a stored fallback;
- heavy hardware unavailable → degrade to a lighter profile;
- preferred UI unavailable → continue through the local API or CLI;
- model distributor unavailable → use locally preserved and verified assets;
- project development stops → retain an offline recovery path and open data formats.

Performance may decrease. The state and recovery path must remain.

## Planned capabilities

The long-term project direction includes:

- local conversation, writing, summarization, translation, and planning;
- local memory and project state;
- web research with locally stored sources and citations;
- PDF, document, OCR, CSV, image, audio, video, and code assistance;
- model-independent backup, export, import, and restoration;
- local model switching and graceful degradation;
- verified model storage through a Model Vault;
- permission-controlled tool use with local audit records;
- optional cloud acceleration after the local system is complete;
- later mobile companion and mobile-edge modes.

These are goals, not claims of current implementation.

## Initial scope

The first implementation milestone will be a small local proof of continuity:

1. a private workspace separated from the public repository;
2. a minimal portable doll state format;
3. local model access through a replaceable adapter;
4. basic local conversation;
5. explicit memory and decision storage;
6. local document reading and artifact output;
7. backup and restoration;
8. model replacement without losing state;
9. offline startup and operation tests;
10. refusal to write outside the approved workspace.

## What doll is not

`doll` is not intended to be:

- another model runner replacing Ollama, llama.cpp, or vLLM;
- a clone of Open WebUI, Jan, LM Studio, or other local AI interfaces;
- a cloud-required assistant;
- an unrestricted autonomous computer-control agent;
- a guarantee of permanent frontier-model performance;
- a promise that different models will behave identically;
- a system that silently uploads memory, documents, or files.

## Profiles

The project will use one repository and one core system with different execution profiles:

- **Lite:** designed for lower-powered machines and reduced-capability fallback operation;
- **Heavy:** designed for larger local models, richer media processing, deeper retrieval, verification, and model-improvement workflows.

They are not separate products and must share the same state, security, backup, and recovery formats.

## Platform direction

- macOS: initial real-machine verification target;
- Windows x64: CI-tested beta target until real-machine validation is available;
- Ubuntu Linux x64: CI-tested beta target until real-machine validation is available;
- other Linux distributions, ARM systems, and GPU configurations: experimental until validated.

## Development model

The repository will be developed in small pull requests.

- specifications and continuity requirements are written before implementation;
- GPT is used for architecture, task decomposition, and review;
- Codex is used for implementation, tests, and pull requests;
- local hardware testing is performed separately from CI;
- private data, model weights, checkpoints, and personal workspaces must never be committed.

## Repository status

The first phase is specification work. The source specification will live under `docs/spec/`. A generated combined document, `DOLL_FINAL_SPEC.md`, will later be produced for reading and archival use.

## License

The doll source code and project documentation are licensed under the Apache License 2.0 unless a file states otherwise.
