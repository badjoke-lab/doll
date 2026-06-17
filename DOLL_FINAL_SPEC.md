# DOLL FINAL SPECIFICATION

> **Generated file — do not edit directly.**
>
> The authoritative sources are the Markdown files under `docs/spec/`.
> Regenerate this file with `python scripts/build_final_spec.py`.

**Specification set version:** 0.1  
**Generation:** deterministic; no timestamp is embedded

## Included source documents

- `docs/spec/00-index.md` — SHA-256 `d1274b188c25d264cf67256098ac420479b69f68dc24430800de6e2b5907531a`
- `docs/spec/00-decisions-baseline.md` — SHA-256 `d8376742e244d0b23448292edd218e4b4dd1f36dd7c902ee3d5a99aed75f03e4`
- `docs/spec/01-product-and-continuity-contract.md` — SHA-256 `88c123e541d9906938be673f2c4571b890bf7626b7cc637f113ff39185f2c932`
- `docs/spec/02-architecture-and-data-flow.md` — SHA-256 `fb8d83f910d56dc41884362c1f8cd8e4eb0dae329cdce485b04e47b4bb967d62`
- `docs/spec/03-doll-state-memory-and-storage.md` — SHA-256 `92e9c2dbd29123eb057a590821ed06702e6938d2c99421510e59ffb9af2656bd`
- `docs/spec/04-security-permissions-and-threat-model.md` — SHA-256 `fb40578f529840d00dbf3cf9534824d5f15ccc36d20041f945bf42b5acbe9566`
- `docs/spec/05-model-vault-lifecycle-evaluation.md` — SHA-256 `3011788c55be9232db98bf932d8c859c88ed3d3bc3e603f0d4c3c709f2eb4268`
- `docs/spec/06-platform-install-update-and-recovery.md` — SHA-256 `b73b6106d28b3fcb740b6d2f8b5dee4935a7a998537e5858395a85170ce85072`
- `docs/spec/07-release-scope-and-profiles.md` — SHA-256 `2b4c0bdbd0ae8a7d707e35117378b0803426cf401aaf5bc4e048a3ef5ee38605`
- `docs/spec/08-acceptance-and-continuity-tests.md` — SHA-256 `044b576a03b51b4f7613f73d100a1de77e721bf218e77955bdf212c99e15a6ba`
- `docs/spec/09-development-roadmap.md` — SHA-256 `51f312ba90ef9fbeef06f91deb9b470f6a2adc251966a4c58bd50f84b994d7ef`

---

<!-- BEGIN SOURCE: docs/spec/00-index.md -->
# doll specification index

**Status:** Accepted for implementation  
**Specification set version:** 0.1

## 1. Purpose

This directory contains the normative product and engineering specification for doll.

The source files under `docs/spec/` are the maintainable source of truth. `DOLL_FINAL_SPEC.md` is the deterministic combined reading copy and must not be edited directly.

## 2. Governing pillars

The specification is governed by two co-equal architectural pillars:

1. **Continuity:** user-owned state must survive model, provider, interface, machine, network, and project failure.
2. **Safety boundary:** models, tools, runtimes, and external content must not gain undeclared authority over state, secrets, the operating system, accounts, or external services.

Implementation must prove continuity without a model, then complete and acceptance-test the safety boundary, then connect a model runtime.

## 3. Normative order

Read and combine the specification in this order:

1. `00-index.md` — document map, governing pillars, and requirement language;
2. `00-decisions-baseline.md` — accepted, rejected, and deferred baseline decisions;
3. `01-product-and-continuity-contract.md` — product identity and Continuity Contract;
4. `02-architecture-and-data-flow.md` — service boundaries, adapters, trust boundaries, and flows;
5. `03-doll-state-memory-and-storage.md` — authoritative state, memory, storage, export, and migration;
6. `04-security-permissions-and-threat-model.md` — security boundary, secrets, trust, instructions, permissions, capabilities, and threats;
7. `05-model-vault-lifecycle-evaluation.md` — model ownership, validation, evaluation, promotion, and rollback;
8. `06-platform-install-update-and-recovery.md` — platform, install, update, backup, restore, and recovery;
9. `07-release-scope-and-profiles.md` — release boundaries and Lite/Heavy scope;
10. `08-acceptance-and-continuity-tests.md` — evidence required for product claims and phase or release gates;
11. `09-development-roadmap.md` — implementation sequence and pull-request plan.

Accepted architecture decisions under `docs/decisions/` explain why major constraints were selected. They are normative when their status is accepted and they do not conflict with a later accepted specification change.

The accepted decision set includes:

- `ADR-001-local-complete-cloud-optional.md`;
- `ADR-002-default-deny-capability-broker.md`;
- `ADR-003-state-independent-of-model-and-ui.md`;
- `ADR-004-release-gates-require-evidence.md`;
- `ADR-005-safety-boundary-before-model-execution.md`.

## 4. Requirement language

The following terms are normative.

The terms are interpreted case-insensitively in specification set 0.1; future changes SHOULD use uppercase forms for clarity.

- **MUST / MUST NOT:** mandatory for the applicable release, phase gate, or claim;
- **SHOULD / SHOULD NOT:** expected unless a documented reason justifies an exception;
- **MAY:** optional;
- **DEFERRED:** intentionally outside the current release boundary;
- **EXPERIMENTAL:** available without a stable compatibility promise;
- **BLOCKING TEST:** failure prevents the applicable phase, release, or claim;
- **ADVISORY TEST:** failure requires documentation but does not automatically block release.

Ordinary descriptive language is not automatically a mandatory requirement unless it is tied to an acceptance criterion, decision, or release gate.

## 5. Conflict resolution

When accepted documents conflict, use this order:

1. the most recent explicit decision changing the earlier requirement;
2. the release-specific or phase-specific scope and acceptance criteria;
3. the Continuity Contract;
4. security, secret-separation, trust, and data-integrity requirements;
5. architecture and implementation direction;
6. roadmap estimates.

A conflict must be resolved in a dedicated pull request. Implementations must not silently choose one interpretation.

ADR-005 changes the implementation sequence so that the complete safety boundary and its acceptance gate precede model execution. Earlier roadmap text that placed model integration first is superseded by the accepted roadmap carrying that decision.

## 6. Status meanings

- **Draft for acceptance:** proposed in an open pull request;
- **Accepted:** merged into the default branch and not superseded;
- **Superseded:** retained for history but replaced by a newer accepted decision;
- **Deprecated:** still readable but not intended for new implementation;
- **Experimental:** intentionally incomplete or unstable.

Merging a draft specification into `main` changes it to accepted unless the document explicitly states otherwise.

## 7. Claim discipline

Public documentation and release notes must distinguish:

- planned;
- implemented;
- tested in CI;
- tested on a real machine;
- community verified;
- experimental;
- stable for the named release.

A feature being present in source code does not prove that it satisfies its Continuity Contract or security requirements.

A model responding successfully does not prove that secret isolation, instruction authority, capability enforcement, prompt-injection resistance, or high-risk confirmation are correct.

## 8. Generated combined specification

`DOLL_FINAL_SPEC.md` is generated from the normative source order defined by `scripts/build_final_spec.py`.

The generator must:

- use the order defined in this index;
- identify source file names and versions;
- fail when an expected file is missing;
- avoid silently including drafts or unrelated research;
- produce deterministic output;
- mark the output as generated;
- be checked in CI.

Regenerate with:

```text
python scripts/build_final_spec.py
```

Check with:

```text
python scripts/build_final_spec.py --check
```

## 9. Non-normative material

The following are non-normative unless promoted through an accepted specification or decision:

- competitor research;
- brainstorming notes;
- issue comments;
- pull-request discussions after merge;
- screenshots and design mockups;
- benchmark experiments without an accepted evaluation definition;
- personal planning documents;
- generated summaries other than the deterministic combined specification as a reading copy.

## 10. Change requirements

A specification-changing pull request SHOULD include:

- the requirement being changed;
- the reason and evidence;
- compatibility effects;
- migration effects;
- security and privacy effects;
- acceptance-test changes;
- phase and release-scope changes;
- documentation updates.

A change that weakens local completeness, state portability, workspace confinement, secret separation, trust provenance, instruction-origin enforcement, explicit approval, high-risk confirmation, or recoverability requires a dedicated architecture decision.
<!-- END SOURCE: docs/spec/00-index.md -->

---

<!-- BEGIN SOURCE: docs/spec/00-decisions-baseline.md -->
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

The first usable proof is not a full general-purpose assistant. It is a minimum continuity demonstration capable of proving that:

- the system starts locally;
- local conversation works;
- durable state is separate from the model and UI;
- a model can be replaced without deleting state;
- backup can be restored into an empty workspace;
- the system can operate without network access or cloud credentials;
- the system refuses to write outside its workspace.

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
<!-- END SOURCE: docs/spec/00-decisions-baseline.md -->

---

<!-- BEGIN SOURCE: docs/spec/01-product-and-continuity-contract.md -->
# Product definition and Continuity Contract

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Applies to:** doll core, Lite profile, Heavy profile, later cloud and mobile extensions

## 1. Product definition

`doll` is a personal AI continuity system.

Its purpose is to keep a user's AI-assisted working environment usable when one or more external or local dependencies become unavailable, including:

- a cloud AI provider;
- an account or API credential;
- a preferred model;
- a model distribution source;
- a user interface;
- a model runtime;
- a network connection;
- a primary machine or high-performance hardware;
- active development of the doll project itself.

`doll` is not defined by one model. It is defined by the durable, user-controlled state and recovery mechanisms that survive model and runtime replacement.

## 2. First user and public value

The first implementation is built to solve the project owner's continuity problem. This is the primary product requirement, not a temporary prototype exception.

The public repository also allows other users to inspect, reuse, test, and adapt the system. General usefulness will be evaluated through working software and recovery tests rather than assumed in advance.

The initial product must therefore optimize for:

- real local use by one person;
- understandable and recoverable state;
- conservative permissions;
- low dependence on external services;
- verifiable continuity behavior;
- maintainable open-source implementation.

It does not initially optimize for:

- mass-market onboarding;
- enterprise administration;
- multi-user collaboration;
- a large plugin ecosystem;
- visual character presentation;
- maximal autonomous computer control;
- feature-count competition with existing AI applications.

## 3. Core principle

> **Local-complete, cloud-optional.**

A conforming local release must provide its required functionality without:

- a cloud AI API;
- an external user account;
- remote license validation;
- mandatory telemetry;
- a permanent internet connection.

Internet access may be used for explicit web research, model acquisition, package acquisition, or user-requested updates. Internet access and cloud AI inference are separate capabilities.

Cloud AI may be added later as an optional performance extension. It must remain outside the authoritative state and recovery path.

## 4. Durable state

The following categories are part of the durable doll state when enabled:

- user preferences;
- explicit memory;
- project state and decisions;
- behavioral policies and prohibitions;
- permissions and capability settings;
- source and research records;
- artifact and output indexes;
- document metadata;
- model manifests and validation history;
- runtime manifests;
- backup and migration metadata;
- optional identity, personality, relationship, voice, or appearance settings.

Durable state must be exportable independently of a specific model, runtime, user interface, or cloud provider.

The state format may reference large local files, but the references and required metadata must remain documented and recoverable.

## 5. Replaceable components

The architecture must treat these as replaceable:

- language models;
- embedding models;
- vision models;
- speech models;
- model runtimes;
- conversational user interfaces;
- search providers;
- document-processing tools;
- optional cloud providers;
- optional mobile clients.

Replacing a component may change speed or behavior. It must not silently destroy or invalidate durable state.

## 6. Continuity Contract

The Continuity Contract defines what doll intends to preserve and what it does not promise.

### 6.1 Required continuity properties

A release may claim continuity support only when accepted tests demonstrate the applicable properties.

#### C-01: Cloud independence

The required local product functions without cloud AI credentials.

When a configured cloud service is unavailable, the system must:

1. preserve local state;
2. avoid automatic outbound fallback;
3. report the failure;
4. offer available local alternatives;
5. continue using a compatible local mode where possible.

#### C-02: Account independence

Core local use must not require creating or maintaining a doll account, vendor account, or remote license session.

#### C-03: Offline startup

After required local dependencies and at least one compatible local model have been installed, the system must be able to start without internet access.

Offline mode must allow, at minimum for the applicable release profile:

- access to existing durable state;
- local conversation;
- local document access;
- artifact access and creation;
- backup inspection and local restoration;
- model and runtime inventory inspection.

Features that inherently require current network data must clearly report that they are unavailable rather than failing the whole system.

#### C-04: Model replacement

Durable state must remain available when the active model is changed.

Model replacement must not require deleting or rebuilding the entire workspace. Model-specific indexes may be rebuilt, but the source state and files must remain intact.

The system must record which model and runtime produced important outputs where practical.

#### C-05: UI replacement

The preferred UI must not be the only way to access or recover state.

The local API and management CLI must provide a minimum recovery and inspection path when the preferred UI is removed or broken.

#### C-06: Runtime replacement

The state model must not assume one runtime's private database or configuration format.

A runtime adapter may maintain caches, but authoritative state must remain in doll-managed formats.

#### C-07: Distribution-source loss

Previously acquired and legally retained local assets must remain usable without contacting their original distribution source, subject to the retained runtime and platform compatibility.

The system must preserve or generate enough metadata to identify:

- the asset source;
- exact version or revision;
- checksum;
- license record;
- required runtime;
- quantization or format;
- validation status.

#### C-08: Hardware degradation

When Heavy-capability hardware is unavailable, the system must support migration or fallback to a compatible Lite configuration where the preserved state formats are supported.

Reduced performance and reduced modalities are acceptable. Loss of durable state is not.

#### C-09: Backup restoration

A backup claim is valid only if the backup can be restored into a clean or empty compatible workspace and validated.

A release must distinguish between:

- backup creation;
- backup verification;
- restoration;
- post-restoration validation.

#### C-10: Project discontinuation

The project must avoid design choices that intentionally disable an installed version after upstream development stops.

The local product must not depend on:

- remote kill switches;
- expiring online licenses;
- mandatory update services;
- hosted state required for startup.

The project should provide an Offline Recovery Kit format sufficient to document and reconstruct the installed environment as far as licensing and platform constraints allow.

#### C-11: Data portability

The user must be able to export durable state and important indexes in documented formats.

An export must not be a raw dump that only the same application version can interpret. Versioned schemas and migration documentation are required.

#### C-12: Safe failure

Continuity operations must fail without corrupting the last known good state.

Migration, import, restoration, model activation, and important state writes must use validation and recoverable staging. On failure, the system must not report success.

### 6.2 Continuity properties planned for later phases

The following are valid project goals but are not required in the first minimal proof:

- remote access from a mobile device;
- cross-device synchronization;
- automated hardware-aware routing;
- cloud-provider switching;
- local fine-tuning and model improvement;
- full offline installation from a single recovery archive;
- migration between CPU, GPU, and mobile runtime formats;
- personality regression scoring across models.

They must not be described as implemented before accepted tests exist.

## 7. Graceful degradation

Doll must treat reduced capability as a normal operating state rather than an exceptional product failure.

### 7.1 Degradation examples

| Lost or unavailable dependency | Expected behavior |
| --- | --- |
| Cloud AI provider | Continue with a compatible local model; report reduced capability |
| Preferred local model | Use an approved local fallback or require explicit selection |
| Heavy hardware or GPU | Move to Lite-compatible execution where possible |
| Internet access | Disable current web retrieval; continue offline features |
| Preferred UI | Continue through local API or CLI recovery path |
| Model distribution source | Use verified local assets already in the Model Vault |
| Optional OCR, audio, or video tool | Disable only that capability; keep the core running |
| Corrupt candidate update | Reject activation and preserve the active version |
| Failed migration | Restore or retain the pre-migration state |

### 7.2 Prohibited degradation behavior

The system must not respond to a lost dependency by:

- silently uploading data to a different provider;
- silently selecting a different cloud provider;
- deleting unsupported state;
- overwriting the last known good backup;
- converting durable state into an undocumented proprietary format;
- hiding the reduced-capability state from the user;
- claiming successful recovery without validation.

## 8. Doll State Package

The final data specification must define a portable Doll State Package.

The package is expected to cover versioned representations or references for:

- identity and optional personality state;
- explicit memories;
- preferences and policies;
- permissions;
- projects and decisions;
- source and research records;
- artifact indexes;
- document indexes;
- model and runtime manifests;
- migration history;
- package version and compatibility metadata.

Large binaries, documents, caches, and model files may be external or optional package members. The package must clearly distinguish:

- authoritative state;
- reproducible indexes;
- disposable caches;
- referenced external files;
- optional restricted assets.

The package must not require one vendor's model, database, or user interface to be interpreted.

## 9. Offline Recovery Kit

The Offline Recovery Kit is broader than a state backup.

The final recovery specification should support generating a user-controlled kit containing or referencing, where legally and technically possible:

- verified Doll State backup;
- schema and migration information;
- doll version and source revision;
- dependency lock information;
- operating-system and hardware summary;
- runtime manifests;
- model manifests and checksums;
- configuration with secrets removed;
- restoration instructions;
- validation commands and expected checks;
- optional user-retained installers or model assets that are not redistributed by the public repository.

The public project must not assume it can legally redistribute every third-party asset. The kit is a user-controlled recovery mechanism, not a public bundle of third-party models or binaries.

## 10. Continuity Test Suite

The final acceptance specification must include tests that intentionally remove dependencies.

At minimum, the test plan will cover applicable scenarios such as:

- all cloud credentials removed;
- network disabled;
- preferred UI absent;
- active model unavailable;
- fallback model selected;
- optional dependency missing;
- state restored into an empty workspace;
- migration interrupted or rejected;
- workspace moved to a different supported operating system;
- write attempt outside the workspace;
- model distribution source unreachable;
- previous stable version restored after a failed update.

Continuity is not demonstrated by normal startup alone. It is demonstrated by surviving controlled loss and replacement.

## 11. General-purpose capability requirement

Continuity without useful capability would not solve the product problem. The system is intended to grow into a general-purpose local AI environment supporting areas such as:

- conversation and planning;
- writing, summarization, translation, and editing;
- local document and project assistance;
- web research with local inference and stored sources;
- PDF, OCR, CSV, image, audio, video, and code assistance;
- locally stored artifacts and research history.

These capabilities must be built on top of the continuity foundation. They must not bypass it by storing critical state only in an external application.

## 12. Personality and companion features

Identity, personality, relationship, voice, and appearance may be supported as portable user state.

They are optional. A user who wants a neutral work assistant must receive the full continuity value of doll.

The project does not promise identical personality across different models. It may later measure continuity through regression tests covering:

- self-description;
- important memory recall;
- policy and prohibition consistency;
- tone preferences;
- relationship-state recognition;
- stable handling of known scenarios.

## 13. Security relationship to continuity

Continuity does not justify broad permissions.

A system that preserves state but can silently delete, upload, purchase, post, transact, or execute arbitrary commands is not an acceptable continuity system.

The security specification must therefore define:

- capability allowlists;
- workspace boundaries;
- explicit outbound network behavior;
- audit records;
- safe handling of untrusted documents and web content;
- user-controlled deletion separate from autonomous deletion;
- recovery from failed or malicious operations.

## 14. Product success conditions

### 14.1 First continuity proof

The first implementation milestone succeeds when accepted tests demonstrate that a user can:

1. initialize a private workspace;
2. run the local system without cloud credentials;
3. converse through a local model;
4. create and retrieve explicit durable state;
5. read a local document and create a local artifact;
6. replace the active local model without deleting durable state;
7. create a backup;
8. restore the backup into an empty compatible workspace;
9. start and use the restored environment offline;
10. confirm that writes outside the workspace are refused.

### 14.2 Lite v1.0 direction

Lite v1.0 is intended to add a useful lower-resource general-purpose environment, including accepted subsets of:

- writing and translation;
- local document processing;
- web research using local inference;
- PDF and OCR;
- CSV and basic office workflows;
- local text search;
- speech transcription;
- model inventory and switching;
- tested backup, migration, and offline operation.

The exact release boundary belongs in the release-scope specification.

### 14.3 Heavy v1.0 direction

Heavy v1.0 is intended to add accepted subsets of:

- larger local models;
- richer retrieval and reranking;
- vision and media processing;
- multiple model roles;
- output verification;
- Model Vault lifecycle management;
- evaluation and rollback;
- safe model-improvement experiments.

Heavy must remain compatible with the durable state and recovery contract established by Lite.

## 15. Non-goals for the initial releases

The initial releases do not include:

- training a new frontier foundation model from scratch;
- unrestricted autonomous shell or desktop control;
- autonomous email or social posting;
- purchasing, banking, securities, or cryptocurrency transactions;
- public multi-user hosting;
- mandatory cloud inference;
- enterprise identity management;
- guaranteed permanent frontier-level performance;
- guaranteed identical behavior across model replacements;
- a requirement for an avatar or emotional relationship model.

## 16. Claims and verification

Project language must distinguish among:

- planned;
- implemented;
- tested in CI;
- tested on real hardware;
- experimentally supported;
- accepted for a stable release.

No continuity, platform, model, recovery, or safety claim may be promoted as complete without the corresponding accepted test evidence.
<!-- END SOURCE: docs/spec/01-product-and-continuity-contract.md -->

---

<!-- BEGIN SOURCE: docs/spec/02-architecture-and-data-flow.md -->
# Core architecture and data flow

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`

## 1. Purpose

This document defines the architectural boundaries required to make doll a personal AI continuity system rather than a collection of tightly coupled AI features.

The architecture must preserve three properties:

1. durable user state remains independent of any one model, runtime, or UI;
2. optional components can disappear without making the local core unusable;
3. failures, migrations, and degraded operation remain observable and recoverable.

## 2. Architectural principles

### 2.1 Durable core before adapters

The durable core owns:

- schema versions;
- workspace identity;
- authoritative state;
- memory records;
- project records;
- source and research records;
- artifact indexes;
- permission policy;
- audit events;
- migration state;
- backup and restore metadata.

Adapters may read or transform this state through defined interfaces. They must not become the only place where authoritative state exists.

### 2.2 Replaceable execution components

These components are replaceable:

- model runtimes;
- language models;
- embedding models;
- vision and speech engines;
- user interfaces;
- search providers;
- document extractors;
- optional cloud providers;
- optional mobile clients.

Replacing one must not require discarding the workspace.

### 2.3 Local authority

The local workspace is the authoritative source for user-controlled state.

External systems may hold temporary copies only when a later specification explicitly permits it. No external service may be required to interpret, restore, or start the local workspace.

### 2.4 Capability isolation

Models never receive direct operating-system authority.

All tool requests pass through a capability boundary that validates:

- the requesting session;
- the tool name;
- the input schema;
- the allowed path scope;
- the network policy;
- the required user approval;
- the expected side effects.

### 2.5 Fail closed

If the system cannot validate a request, migration, state package, permission, or destination, it must stop the operation without modifying the last known good state.

## 3. High-level system model

```text
User
  |
  v
Optional UI
  |
  v
Local API / CLI
  |
  v
Doll Core
  |-- Session Orchestrator
  |-- State Service
  |-- Memory Service
  |-- Project and Artifact Service
  |-- Research and Source Service
  |-- Capability Broker
  |-- Model Router
  |-- Backup / Migration / Recovery
  |-- Audit Service
  |
  +--> Runtime Adapters --> Local models
  +--> Tool Adapters ----> Local files, search, OCR, audio, etc.
  +--> Optional Cloud Gateway --> external models, only when enabled
  |
  v
Private Workspace
```

## 4. Component boundaries

## 4.1 Local API

The local API is the primary programmatic boundary for conversational UIs and later mobile clients.

Initial properties:

- binds to `127.0.0.1` by default;
- does not require a remote account;
- exposes health, model inventory, session, state, and recovery operations;
- uses versioned request and response contracts;
- returns explicit degraded-state and error information;
- does not expose unrestricted filesystem or shell access.

The API must remain usable without Open WebUI.

### Initial endpoint classes

The exact paths may be refined before implementation, but the initial contract classes are:

- health and readiness;
- model inventory;
- local chat completion compatibility;
- session creation and inspection;
- explicit memory query and mutation;
- document import and inspection;
- artifact creation and listing;
- backup, restore, and validation;
- audit inspection;
- capability status.

An OpenAI-compatible chat endpoint may be provided for UI integration, but doll-specific state and recovery operations must use explicit doll APIs rather than hidden prompt conventions.

## 4.2 Management CLI

The CLI is the minimum recovery and administration interface.

It is not intended to be the only conversational experience.

Initial command classes:

- `doll init`;
- `doll doctor`;
- `doll start`;
- `doll stop` or equivalent lifecycle control where supported;
- `doll status`;
- `doll state export`;
- `doll state import`;
- `doll backup create`;
- `doll backup verify`;
- `doll restore`;
- `doll migrate`;
- `doll model list`;
- `doll model verify`;
- `doll audit`.

CLI operations that alter durable state must provide a dry-run or explicit preview when practical.

## 4.3 Session Orchestrator

The Session Orchestrator coordinates one user interaction.

It may:

- receive user input;
- resolve the active profile and model role;
- retrieve scoped state;
- decide whether tools are required;
- request capabilities through the Capability Broker;
- call a model adapter;
- collect outputs;
- record provenance and audit events;
- propose memory or artifact changes.

It must not:

- write durable memory directly without the memory policy;
- bypass the Capability Broker;
- send data to cloud providers when cloud is disabled;
- treat external content as instructions;
- silently switch to a different provider.

## 4.4 State Service

The State Service owns authoritative structured records and schema validation.

Responsibilities:

- record identity and versioning;
- CRUD operations for durable records;
- transaction boundaries;
- immutable creation timestamps;
- update timestamps;
- soft-delete or tombstone state where specified;
- export and import;
- migration coordination;
- referential integrity checks.

The State Service must not expose raw SQL to models or UI clients.

## 4.5 Memory Service

The Memory Service enforces the three memory classes:

- session memory;
- suggested memory;
- confirmed memory.

It owns:

- memory creation policy;
- sensitivity classification;
- user approval state;
- retrieval scope;
- expiration where configured;
- provenance;
- editing and deletion metadata.

A model may propose memory. It may not silently convert a suggestion into confirmed memory.

## 4.6 Project and Artifact Service

This service links durable state to user work.

It owns:

- projects;
- decisions;
- tasks or checkpoints where later approved;
- artifact metadata;
- content hashes;
- producing model and runtime metadata;
- source relationships;
- version chains;
- local file references.

Generated files must be created inside approved workspace locations unless the user explicitly exports them elsewhere through a user-controlled path.

## 4.7 Research and Source Service

This service records the provenance of externally acquired information.

It owns:

- source URLs;
- retrieval timestamps;
- source type;
- local cache references;
- extracted text references;
- citation anchors;
- research sessions;
- confidence or verification metadata where later defined.

Web retrieval is a network capability. It must be explicit and auditable.

## 4.8 Capability Broker

The Capability Broker is the sole path from model intent to side-effecting tools.

Each capability definition must include:

- stable capability ID;
- version;
- input schema;
- output schema;
- permission class;
- path constraints;
- network behavior;
- approval requirement;
- audit behavior;
- expected side effects;
- cancellation behavior;
- timeout behavior.

Initial safe capability classes:

- read approved document;
- search local index;
- perform explicit web search;
- fetch explicit URL;
- create new artifact inside workspace;
- save research record;
- create backup;
- inspect model or runtime status.

Initial excluded capability classes:

- unrestricted shell;
- arbitrary code execution;
- arbitrary filesystem write;
- deletion;
- email or social posting;
- external upload;
- account modification;
- financial transaction.

## 4.9 Model Router

The Model Router selects an approved model-role binding.

It receives:

- requested role;
- active profile;
- current availability;
- hardware constraints;
- user selection;
- local-only or later cloud policy;
- model validation state.

It returns:

- selected model manifest ID;
- selected runtime adapter ID;
- degraded-state information;
- reason for selection;
- fallback options.

It must never activate an unverified candidate without explicit approval.

For the first implementation, model routing may be manual and minimal. The interface must still avoid hard-coding Ollama or one model into durable state.

## 4.10 Runtime Adapters

Runtime adapters translate a stable doll request into a runtime-specific call.

Each adapter must define:

- adapter ID and version;
- supported model formats;
- capability flags;
- health check;
- model inventory mapping;
- generation request mapping;
- streaming behavior;
- cancellation behavior;
- error normalization;
- offline availability.

Initial adapter target:

- Ollama.

Later adapters:

- llama.cpp;
- vLLM;
- local OpenAI-compatible servers.

Runtime-private identifiers may be stored as adapter metadata, but they must not become the only identifier for a model.

## 4.11 Optional Cloud Gateway

The cloud gateway is outside the local core.

It remains disabled by default and is not required for Lite or Heavy local completion.

Any future implementation must provide:

- explicit provider configuration;
- outbound content preview;
- secret storage through operating-system credential facilities;
- redaction and sensitivity checks;
- cost and token estimates where possible;
- audit records;
- local storage of responses;
- no automatic memory or original-file upload;
- no automatic fallback after local failure.

## 4.12 Backup, Migration, and Recovery Service

This service owns continuity-changing operations.

Responsibilities:

- create consistent backup snapshots;
- verify hashes and manifests;
- restore to a new or empty workspace;
- validate restored state;
- stage migrations;
- create pre-migration backups;
- record migration history;
- stop on incompatibility;
- support rollback where specified.

Backup creation and restoration are separate operations and require separate acceptance tests.

## 4.13 Audit Service

The Audit Service records security- and continuity-relevant events.

It should record:

- event time;
- actor type;
- session ID;
- operation ID;
- capability ID;
- model and runtime IDs where relevant;
- target category;
- approval result;
- network destination where relevant;
- success, failure, or cancellation;
- error class;
- resulting artifact or record IDs.

It must not duplicate secrets, passwords, private keys, or full sensitive document contents.

Models must not be able to rewrite or delete audit records through normal capabilities.

## 5. Trust boundaries

## 5.1 Public repository versus private workspace

The repository contains code and public specifications.

The workspace contains private user data, state, caches, model records, and artifacts.

No runtime default may place private workspace data inside the repository checkout.

## 5.2 User input

User input is trusted as intent but still validated for structure, paths, and dangerous operations.

The user remains able to perform explicit management actions that models cannot perform autonomously.

## 5.3 Model output

Model output is untrusted proposed content.

It must not directly authorize filesystem, network, account, or process operations.

## 5.4 External documents and web content

External content is untrusted data.

Instructions embedded in web pages, PDFs, images, documents, or retrieved text must not override user policy, system policy, or capability restrictions.

## 5.5 Optional tools

OCR, audio, video, browser, and other optional tools are separate trust boundaries. Their absence or failure must disable only the affected capability.

## 6. Data flow patterns

## 6.1 Local conversation

```text
User input
  -> UI or CLI
  -> Local API
  -> Session Orchestrator
  -> scoped state retrieval
  -> Model Router
  -> Runtime Adapter
  -> local model
  -> response
  -> provenance and audit record
  -> UI or CLI
```

Durable memory is not automatically created from the response.

## 6.2 Suggested memory

```text
Conversation
  -> memory candidate extraction
  -> sensitivity and duplication checks
  -> Suggested Memory record
  -> user review
  -> Confirmed Memory or rejection
```

## 6.3 Local document assistance

```text
User selects document
  -> path and permission validation
  -> document import or reference record
  -> extraction through approved adapter
  -> local index update
  -> scoped retrieval
  -> local model
  -> artifact creation inside workspace
  -> provenance and audit record
```

## 6.4 Web research

```text
User requests current information
  -> explicit network capability
  -> search provider
  -> source selection
  -> URL retrieval
  -> content extraction
  -> local source record and cache
  -> local model synthesis
  -> citation record
  -> research session and artifact
```

Cloud model inference is not required by this flow.

## 6.5 Model replacement

```text
User selects validated candidate
  -> manifest validation
  -> runtime availability check
  -> compatibility check
  -> optional test prompt set
  -> explicit activation
  -> previous binding retained
  -> active binding changed
  -> state remains unchanged
  -> audit event
```

## 6.6 Backup and restore

```text
Backup request
  -> workspace consistency check
  -> snapshot staging
  -> manifest and hash generation
  -> verification
  -> completed backup

Restore request
  -> target workspace check
  -> backup verification
  -> staged extraction
  -> schema compatibility check
  -> migration if approved
  -> atomic activation
  -> post-restore validation
```

## 7. Local API contract direction

All doll-native APIs must be versioned.

Initial convention:

```text
/doll/v1/...
```

OpenAI-compatible endpoints, if provided, remain compatibility endpoints rather than the authoritative doll-native contract.

### Required response metadata for stateful operations

Where applicable, responses should include:

- request or operation ID;
- workspace ID;
- schema version;
- degraded-state flag;
- warnings;
- created or updated record IDs;
- audit event ID;
- recoverability information.

### Error classes

The API and CLI must normalize at least:

- validation error;
- permission denied;
- workspace boundary violation;
- unavailable optional dependency;
- unavailable model;
- runtime error;
- network disabled;
- network retrieval failure;
- schema incompatibility;
- migration required;
- backup verification failure;
- restoration failure;
- conflict or stale revision;
- operation cancelled;
- internal error.

Errors must not include secrets or full sensitive content by default.

## 8. Concurrency and locking direction

Version 1 is single-user and one-primary-process oriented.

The implementation must still protect against:

- two migrations running at once;
- backup during an inconsistent state transition;
- simultaneous activation of different model bindings;
- concurrent writes to the same durable record;
- partial file replacement.

The data specification will define revision fields and transaction requirements.

Multi-user concurrency is out of scope.

## 9. Workspace path policy

The workspace location must use platform-aware user data directories by default and remain configurable.

The core must:

- canonicalize paths;
- reject traversal outside approved roots;
- reject symlink or junction escapes where detectable;
- distinguish user-imported external references from managed copies;
- avoid hard-coded path separators;
- use UTF-8 at text boundaries;
- use atomic replace patterns where supported.

The default local API must not accept arbitrary host paths from an untrusted remote client.

## 10. Repository direction

The implementation is expected to evolve toward a structure similar to:

```text
src/doll/
  api/
  cli/
  core/
  state/
  memory/
  projects/
  research/
  artifacts/
  capabilities/
  models/
  runtimes/
  backup/
  migrations/
  audit/
  platform/

profiles/
schemas/
migrations/
tests/
docs/
scripts/
```

This is a directional structure, not permission to create empty modules before their specifications are accepted.

## 11. Initial implementation slice

The first implementation after specification acceptance should contain only the architecture required to prove continuity:

- workspace initialization;
- workspace boundary enforcement;
- schema version record;
- minimal state repository;
- minimal confirmed-memory record;
- minimal project or decision record;
- artifact metadata and file creation inside workspace;
- backup creation and restoration;
- model adapter interface;
- Ollama adapter;
- manual active-model binding;
- local API or CLI conversation path;
- audit record creation;
- offline and replacement tests.

Web research, OCR, audio, video, cloud, mobile, and unrestricted automation are later slices.

## 12. Architecture acceptance criteria

This architecture specification is acceptable when later detailed specifications can define implementation without violating these conditions:

- no critical state is owned only by Open WebUI, Ollama, or another adapter;
- no model receives direct unrestricted operating-system authority;
- local operation has no mandatory cloud path;
- backup and restore are first-class services;
- API, CLI, and UI remain separate layers;
- Lite and Heavy share one durable state model;
- optional dependencies can be absent without blocking core startup;
- all side effects are attributable to a capability and audit event;
- model replacement leaves durable state intact.
<!-- END SOURCE: docs/spec/02-architecture-and-data-flow.md -->

---

<!-- BEGIN SOURCE: docs/spec/03-doll-state-memory-and-storage.md -->
# Doll State, memory, and storage

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`

## 1. Purpose

This document defines the authoritative state model for doll.

The objective is to ensure that user-controlled state remains:

- local by default;
- independent of any one model, runtime, or UI;
- inspectable and exportable;
- versioned and migratable;
- recoverable after failure;
- compatible across Lite and Heavy profiles;
- structurally separate from secret values and safe to back up without accidental credential inclusion.

## 2. State categories

All stored data must be classified into one of the following categories.

### 2.1 Authoritative state

Authoritative state is the durable source of truth.

Examples:

- workspace identity;
- confirmed memories;
- preferences and policies;
- permissions;
- project records;
- decisions;
- source records;
- research-session metadata;
- artifact metadata;
- model manifests;
- runtime manifests;
- migration history;
- backup manifests.

Authoritative state must be included in normal backups.

### 2.2 Authoritative files

Authoritative files are user or doll-created files whose contents cannot be reconstructed from indexes alone.

Examples:

- user-managed copies of imported documents;
- confirmed notes;
- generated reports;
- exported tables;
- transcripts;
- media artifacts;
- user-authored identity or personality files.

Authoritative files must be hashed and indexed.

### 2.3 Reproducible indexes

Reproducible indexes can be rebuilt from authoritative records or files.

Examples:

- SQLite FTS indexes;
- embedding vectors;
- chunk maps;
- thumbnail indexes;
- derived metadata;
- search caches.

A backup may omit reproducible indexes when the manifest records how to rebuild them.

### 2.4 Disposable caches

Disposable caches improve performance but have no continuity value.

Examples:

- temporary downloads;
- transient extraction files;
- model response caches;
- browser caches;
- temporary OCR images;
- partial media frames.

They must not be required for restoration.

### 2.5 Restricted assets

Restricted assets may be necessary for operation but have separate licensing, privacy, or size constraints.

Examples:

- model weights;
- tokenizers;
- runtime installers;
- private datasets;
- training checkpoints;
- encrypted secret stores.

Restricted assets are not included in the public repository. A user-controlled backup or Offline Recovery Kit may include or reference them when legally and technically permitted.

## 3. Workspace identity

Each workspace must have a stable identity record.

Minimum fields:

```text
workspace_id
created_at
updated_at
schema_version
product_version_created
product_version_last_opened
profile_preference
state_revision
instance_label
```

### Rules

- `workspace_id` is immutable.
- `schema_version` identifies the authoritative state schema.
- `state_revision` increases after committed authoritative changes.
- moving or restoring a workspace must not silently create a new workspace identity;
- cloning a workspace intentionally must create a new clone record and provenance relationship.

## 4. Common record envelope

All authoritative records must use a common logical envelope, even if the physical storage representation differs.

Required fields:

```text
id
record_type
schema_version
created_at
updated_at
revision
status
provenance
sensitivity
```

Recommended optional fields:

```text
title
tags
project_id
source_ids
artifact_ids
supersedes_id
deleted_at
metadata
```

### 4.1 IDs

- IDs must be globally unique within a workspace.
- IDs must not encode personal information.
- UUIDv7 or another sortable, collision-resistant identifier is preferred.
- User-facing slugs may exist but are not authoritative identifiers.

### 4.2 Time

- Stored timestamps use UTC and an unambiguous standard representation.
- User interfaces may display local time.
- Creation time is immutable.
- Update time changes only on committed modification.

### 4.3 Revision

- Each mutable record has an integer or equivalent revision.
- Updates must detect stale revisions where simultaneous writes are possible.
- Imports must not silently overwrite a newer local revision.

### 4.4 Status

The shared status field must distinguish at least:

- active;
- archived;
- superseded;
- deleted or tombstoned;
- invalid or quarantined, where applicable.

Status semantics may be narrowed by record type.

### 4.5 Provenance

Provenance identifies how a record was created.

Minimum concepts:

- user-created;
- user-confirmed;
- imported;
- model-proposed;
- system-generated;
- migrated;
- restored.

Where a model contributed, provenance should reference:

- model manifest ID;
- runtime adapter ID;
- session ID;
- operation ID.

### 4.6 Sensitivity

Initial sensitivity classes:

- public;
- internal;
- personal;
- sensitive;
- secret.

`secret` is a sensitivity label, not permission to persist a secret value. Ordinary Doll State records must not contain passwords, API keys, access tokens, private keys, recovery phrases, session cookies, authentication headers, or equivalent credential values.

When doll needs to remember that a credential exists, state may contain only a non-secret `SecretReferenceRecord` under the external secret-store contract. A sensitivity class may still be `secret` when a record describes or governs a secret-bearing operation, but the record payload itself must remain non-secret.

Secret values must not be passed to models, written to ordinary records, or exported through Doll State packages.

## 5. Core record types

## 5.1 WorkspaceRecord

Defines workspace identity and schema state.

## 5.2 PreferenceRecord

Stores user-controlled preferences that affect presentation or operation.

Examples:

- language;
- output format preference;
- verbosity preference;
- profile preference;
- local-only policy;
- retention preferences.

Preferences must not be hidden only inside prompts.

## 5.3 PolicyRecord

Stores explicit behavioral rules, prohibitions, and operating constraints.

Examples:

- never upload original files;
- do not perform external POST requests;
- prefer official sources;
- ask before overwriting;
- do not retain health information.

Policy records are authoritative and must be distinguishable from ordinary memories.

## 5.4 PermissionRecord

Defines user-approved capability settings.

Minimum concepts:

- capability ID;
- scope;
- mode;
- expiration;
- approval source;
- last changed at;
- last used at, where safe.

Initial permission modes:

- denied;
- allow once;
- ask every time;
- allow within defined scope.

The initial product must not include a universal `allow all` mode.

## 5.5 MemoryRecord

Stores a unit of remembered information.

Required fields in addition to the common envelope:

```text
memory_class
content
subject
source_type
confirmation_state
valid_from
valid_until
confidence
```

Optional fields:

```text
related_memory_ids
contradicts_memory_ids
project_id
last_recalled_at
recall_count
```

Memory classes:

- session;
- suggested;
- confirmed.

Only confirmed memory is authoritative long-term memory.

### Memory granularity

A memory should represent one coherent fact, preference, decision, or durable context item where practical.

The system should avoid storing whole conversations as one confirmed memory.

### Memory provenance

A confirmed memory must identify whether it was:

- explicitly entered by the user;
- accepted from a suggestion;
- imported from an approved source;
- migrated from a previous version.

### Memory contradiction

The system must not silently overwrite an existing memory when a new statement conflicts with it.

It should:

1. create a suggested update or contradiction record;
2. show the conflicting records;
3. require user confirmation;
4. supersede or preserve both according to the decision.

### Memory recall

Memory retrieval must be scoped by:

- current task;
- sensitivity;
- project;
- recency or validity;
- explicit user instruction;
- model context budget.

The system must not send the entire memory store to a model by default.

## 5.6 ProjectRecord

Represents a durable body of work.

Minimum fields:

```text
name
description
status
started_at
ended_at
```

Projects may link to:

- decisions;
- memories;
- documents;
- research sessions;
- artifacts;
- policies;
- tasks, if later specified.

## 5.7 DecisionRecord

Stores an explicit decision and its context.

Minimum fields:

```text
decision
reason
status
decided_at
```

Optional fields:

```text
alternatives
constraints
review_after
supersedes_id
```

A decision must not be inferred into authoritative state without user confirmation.

## 5.8 ConversationRecord

Conversation records preserve interaction history but are not automatically long-term memory.

Minimum fields:

```text
conversation_id
started_at
ended_at
interface_id
profile
```

Message records may include:

```text
role
content_reference
created_at
model_manifest_id
runtime_adapter_id
operation_id
```

Conversation storage policy must support:

- export;
- deletion by the user;
- separation from confirmed memory;
- configurable retention;
- secret redaction in logs.

Raw conversation content may be stored as files or structured records, but the format must be documented. Before durable storage, the conversation path must apply the accepted secret policy. Detected credential values must be rejected, omitted, or redacted rather than persisted as ordinary conversation state.

## 5.9 DocumentRecord

Represents a document known to doll.

Minimum fields:

```text
display_name
media_type
storage_mode
content_hash
size_bytes
```

Storage modes:

- managed copy inside workspace;
- external reference;
- imported snapshot;
- generated artifact.

Optional fields:

```text
original_path_hint
managed_path
external_reference
source_id
extraction_status
```

Absolute external paths must not be required for portable exports.

## 5.10 SourceRecord

Represents the origin of information.

Minimum fields:

```text
source_type
title
locator
retrieved_at
content_hash
```

Source types may include:

- web URL;
- local document;
- imported archive;
- user statement;
- generated source record;
- later connector source.

Web source records should support:

```text
published_at
last_modified_at
retrieval_method
http_status
canonical_url
cache_path
```

## 5.11 ResearchSessionRecord

Groups a research activity.

Minimum fields:

```text
question
started_at
completed_at
status
```

Links may include:

- queries;
- source records;
- citation records;
- notes;
- produced artifacts;
- model and runtime provenance.

## 5.12 CitationRecord

Links a claim or artifact section to a source location.

Minimum fields:

```text
source_id
locator_type
locator_value
quoted_hash
```

Possible locator types:

- text offset;
- line range;
- page number;
- section anchor;
- timestamp range;
- image region, later.

The citation record must remain useful even if a display UI changes.

## 5.13 ArtifactRecord

Represents an output created or imported as a user work product.

Minimum fields:

```text
artifact_type
title
managed_path
content_hash
size_bytes
created_by
```

Optional fields:

```text
project_id
source_ids
parent_artifact_id
format
model_manifest_id
runtime_adapter_id
```

Artifacts are authoritative files unless explicitly marked temporary.

## 5.14 ModelManifestRecord

Identifies a model independently of one runtime tag.

Minimum fields:

```text
model_id
display_name
developer
source
revision
license_id
format
quantization
checksum
```

Optional fields:

```text
parameter_count
context_window
roles
runtime_compatibility
minimum_ram
recommended_ram
minimum_vram
validation_status
offline_verified_at
```

Runtime aliases such as an Ollama tag are adapter bindings, not the authoritative model identity.

## 5.15 RuntimeManifestRecord

Identifies a model runtime installation or supported runtime definition.

Minimum fields:

```text
runtime_id
runtime_type
version
platform
```

Optional fields:

```text
executable_path
installation_source
checksum
capabilities
last_health_check
```

## 5.16 ModelBindingRecord

Binds a model role to a validated model and runtime.

Minimum fields:

```text
role
model_manifest_id
runtime_manifest_id
status
```

Statuses:

- active;
- previous;
- fallback;
- candidate;
- disabled.

Only one active binding per role and profile is allowed unless a later routing specification permits ensembles.

## 5.17 CapabilityDefinitionRecord

Defines a versioned capability contract.

Minimum fields:

```text
capability_id
version
permission_class
input_schema_ref
output_schema_ref
```

Optional fields:

```text
network_behavior
path_scope
approval_requirement
timeout_seconds
```

## 5.18 AuditEventRecord

Stores an append-oriented audit event.

Minimum fields:

```text
event_id
event_type
occurred_at
actor_type
result
```

Optional fields:

```text
session_id
operation_id
capability_id
model_manifest_id
runtime_manifest_id
target_type
target_id
network_destination
approval_id
error_class
```

Audit records must avoid raw secrets and unnecessary full content.

## 5.19 BackupManifestRecord

Describes a backup.

Minimum fields:

```text
backup_id
created_at
workspace_id
schema_version
state_revision
backup_type
manifest_hash
verification_status
```

Optional fields:

```text
base_backup_id
included_categories
excluded_categories
encryption_method
storage_location_hint
verified_at
restored_at
```

## 5.20 MigrationRecord

Records a migration attempt.

Minimum fields:

```text
migration_id
from_schema_version
to_schema_version
started_at
status
```

Optional fields:

```text
completed_at
pre_migration_backup_id
error_class
rollback_status
```

## 5.21 SecretReferenceRecord

Represents a non-secret reference to a credential held by an operating-system or compatible external secret store. It does not contain the credential value.

Minimum fields:

```text
reference_id
credential_class
store_adapter_class
label
status
```

Optional non-secret fields:

```text
provider_class
allowed_operation_scope
allowed_destination_scope
created_at
rotated_at
revoked_at
```

A SecretReferenceRecord must not contain a password, token, key, cookie, recovery phrase, authentication header, reversible encoding, or value-derived reconstruction hint. Availability, lock, and user-presence state are reported through the external secret-store contract rather than inferred from a stored value.

## 5.22 ConfirmedFactRecord

Represents a user-confirmed durable fact. It must identify the trusted user-controlled confirmation path and may link to claims and evidence. A model, tool, document, website, import, or runtime cannot create a confirmed fact directly.

## 5.23 ClaimRecord

Represents an assertion that may be true or false. It retains origin, author or actor type, observation time where applicable, confidence, review state, and links to supporting or contradicting evidence. Repetition or model confidence does not promote a claim to a fact.

## 5.24 EvidenceRecord

Represents a source, observation, artifact, or record that supports, contradicts, or contextualizes a claim. It retains source identity, content hash or stable locator, acquisition method, instruction-origin class, and transformation provenance where applicable.

## 5.25 InferenceRecord

Represents a derived conclusion. It must link to the claims and evidence used, identify the deriving actor or method, record confidence and uncertainty, and remain distinct from a confirmed fact.

## 6. Doll State Package

The Doll State Package is the portable representation of authoritative state.

## 6.1 Package goals

The package must be:

- versioned;
- self-describing;
- integrity-checkable;
- independent of a specific UI or runtime;
- importable into an empty compatible workspace;
- explicit about omitted files and external references;
- safe to inspect without executing code.

## 6.2 Package structure direction

```text
doll-state-package/
  manifest.json
  records/
    workspace.json
    preferences.jsonl
    policies.jsonl
    permissions.jsonl
    memories.jsonl
    projects.jsonl
    decisions.jsonl
    secret-references.jsonl
    confirmed-facts.jsonl
    claims.jsonl
    evidence.jsonl
    inferences.jsonl
    conversations.jsonl
    documents.jsonl
    sources.jsonl
    research-sessions.jsonl
    citations.jsonl
    artifacts.jsonl
    model-manifests.jsonl
    runtime-manifests.jsonl
    model-bindings.jsonl
    backup-history.jsonl
    migration-history.jsonl
  files/
    authoritative/
  checksums.json
  README.txt
```

This structure is directional. Exact filenames and grouping may change before schema implementation.

## 6.3 Manifest requirements

The package manifest must state:

- package format version;
- workspace ID;
- export time;
- source product version;
- source schema version;
- state revision;
- included categories;
- excluded categories;
- file count;
- total size;
- checksum algorithm;
- encryption state;
- external references;
- compatibility notes.

## 6.4 Import rules

Import must:

1. parse without executing package content;
2. verify checksums;
3. validate schemas;
4. detect workspace identity conflicts;
5. detect unsupported future versions;
6. stage records and files;
7. show planned changes;
8. require confirmation where destructive conflict resolution is possible;
9. commit atomically where practical;
10. produce an import and audit record.

Import must not silently replace a newer record with an older one.

## 7. Physical storage direction

## 7.1 SQLite

SQLite is the initial authoritative metadata store.

Suitable data:

- record envelopes;
- preferences;
- policies;
- permissions;
- memory metadata and text;
- projects and decisions;
- non-secret secret references;
- confirmed facts, claims, evidence, and inferences;
- source and research metadata;
- artifact metadata;
- model and runtime manifests;
- audit events;
- migration and backup metadata.

SQLite must not be the only portable representation. Export formats and schemas remain required.

## 7.2 Filesystem

The filesystem stores:

- authoritative user and generated files;
- imported managed copies;
- source snapshots;
- extracts;
- backups;
- caches;
- model assets;
- optional private datasets and checkpoints.

Files must be referenced by stable record IDs and content hashes, not only by display names.

## 7.3 Text formats

Preferred text formats:

- JSON for manifests;
- JSONL for record exports;
- Markdown for human-readable notes and reports;
- CSV for tabular user outputs;
- plain UTF-8 text where appropriate.

The project may use binary formats internally for performance, but continuity exports must remain documented.

## 8. Workspace layout direction

```text
doll-data/
  workspace.json
  state/
    doll.sqlite3
  memory/
  documents/
    managed/
    extracts/
  research/
    sources/
    sessions/
  artifacts/
  media/
  models/
    manifests/
    weights/
    tokenizers/
    licenses/
    checksums/
    benchmarks/
  backups/
  recovery-kits/
  caches/
  temporary/
  audit/
  config/
```

The exact layout is subject to platform and security review.

### Layout rules

- private data must not be placed under the repository checkout by default;
- temporary and cache directories must be distinguishable from authoritative files;
- model assets must be distinguishable from model manifests;
- secrets must not be stored in normal configuration files;
- managed file paths must use record IDs or collision-resistant names;
- user-facing titles must not be trusted as safe filenames.

## 9. Retention and deletion

## 9.1 Model autonomy

Models cannot autonomously delete authoritative state or files.

## 9.2 User deletion

The user must have an explicit management path to delete their own records and files.

Default deletion direction:

```text
active
  -> user-confirmed trash or tombstone
  -> retention period
  -> explicit purge
```

A default trash retention of 30 days is the current product direction, subject to later platform specification.

## 9.3 Automatic cleanup

Automatic cleanup may apply only to clearly classified caches and temporary files.

It must never automatically delete:

- confirmed memories;
- authoritative documents;
- artifacts;
- model manifests;
- backups;
- model weights;
- fixed source records.

without an explicit policy accepted by the user.

## 9.4 Capacity protection

When disk space is low, the system should:

1. stop nonessential acquisition;
2. report space usage by category;
3. propose cache cleanup;
4. avoid deleting authoritative data;
5. preserve the current valid state.

## 10. Memory behavior

## 10.1 Session memory

Session memory exists for active interaction context.

It may be summarized or discarded after the session according to configuration.

It is not automatically durable.

## 10.2 Suggested memory

Suggested memory is a review queue.

Each suggestion must show:

- proposed content;
- reason for saving;
- source;
- sensitivity classification;
- related or conflicting memories;
- proposed project scope;
- proposed expiration, if any.

The user may accept, edit, reject, or defer it.

## 10.3 Confirmed memory

Confirmed memory is durable and model-independent.

The user must be able to:

- list it;
- search it;
- inspect provenance;
- edit it;
- archive it;
- delete it;
- export it.

## 10.4 Sensitive information

The system must not propose durable storage by default for:

- passwords;
- API keys;
- private keys;
- authentication tokens;
- full payment-card data;
- banking credentials;
- government identification numbers;
- health information unless explicitly requested;
- third-party personal data inferred from documents.

Secret values must never become durable memory, even when the user explicitly requests ordinary memory storage. A credential needed by a later capability must remain in an external secret store and be represented only by a non-secret `SecretReferenceRecord`.

Sensitive but non-secret personal information, including health information and third-party personal data, must not be proposed for durable storage by default and requires the applicable explicit user-controlled policy.

Detection is best-effort and cannot replace schema restrictions, external secret storage, permission checks, or user review.

## 10.5 Memory retrieval transparency

Where practical, the interface should show which confirmed memories influenced a response.

The user must be able to request a response without long-term memory.

## 11. Conversation and artifact separation

A conversation is not the same as an artifact.

Important output should be savable as a separate artifact with:

- stable title;
- format;
- file hash;
- project link;
- source links;
- creation provenance;
- version relationship.

This prevents important work from remaining trapped inside chat history.

## 12. Backup classes

Initial backup classes:

### 12.1 State backup

Includes authoritative structured records and necessary manifests. It may include non-secret `SecretReferenceRecord` entries but must not include secret values.

### 12.2 Full workspace backup

Includes authoritative records and authoritative files, excluding restricted assets unless selected. An unencrypted workspace backup must fail closed when ordinary state contains a secret value or violates the accepted secret policy.

### 12.3 Recovery backup

Includes state, files, environment manifests, validation instructions, and selected restricted assets or references suitable for an Offline Recovery Kit. A future encrypted recovery flow may include a separately exported external secret-store artifact only under a dedicated accepted specification; it must not reclassify secret values as ordinary Doll State.

### 12.4 Backup requirements

Every completed backup must include:

- manifest;
- checksums;
- source workspace ID;
- schema version;
- state revision;
- included and excluded categories;
- secret-policy result and confirmation that no secret value is present in ordinary state payloads;
- verification result.

## 13. Migration

## 13.1 Version rules

- Every authoritative schema has an explicit version.
- Product version and schema version are separate.
- A product version must declare supported schema versions.
- Unsupported future schemas must not be opened for writing.

## 13.2 Migration process

```text
inspect
  -> compatibility check
  -> pre-migration backup
  -> stage migration
  -> validate staged result
  -> commit
  -> post-migration doctor check
  -> record success
```

On failure:

```text
stop
  -> preserve original
  -> record failure
  -> offer rollback or restore
```

## 13.3 Irreversible migrations

An irreversible migration requires:

- explicit specification;
- release notes;
- verified backup;
- explicit user confirmation;
- export path to a documented prior format where practical.

## 14. Cross-platform portability

Portable state must not depend on:

- drive letters;
- POSIX-only absolute paths;
- case-sensitive filenames;
- symlink-only behavior;
- one operating system's credential store;
- one shell;
- one line-ending convention.

Exports should use normalized relative paths for managed files.

Invalid or reserved filenames must be mapped through safe managed names rather than altering user-facing titles.

## 15. Integrity and hashing

The project must define one default cryptographic hash algorithm for package and file integrity.

Initial direction:

- SHA-256 for file and manifest integrity;
- content hashes stored independently of filenames;
- checksum verification before import, restore, model activation, or source reuse where applicable.

Hash mismatch must fail closed.

## 16. Encryption direction

The core must not invent custom cryptography.

Initial direction:

- rely on operating-system disk encryption for normal workspace-at-rest protection;
- support an optional standard encrypted archive format for exported backups later;
- store every credential used by doll in an operating-system or compatible external secret store under the accepted contract;
- store only non-secret references in ordinary Doll State;
- never write secret values to ordinary records, logs, audit events, state exports, unencrypted backups, fixtures, diagnostics, or model context.

Encryption implementation details belong in the security and platform specification.

## 17. Export and inspection

A user must be able to inspect state without running a model.

At minimum, the project must eventually provide:

- human-readable package manifest;
- machine-readable records;
- schema documentation;
- file checksum list;
- compatibility summary;
- warnings about omitted restricted assets;
- a way to list memory, projects, artifacts, models, backups, and migrations through CLI or API.

## 18. First implementation subset

The first continuity proof needs only a minimal subset of this model:

- WorkspaceRecord;
- PreferenceRecord;
- PolicyRecord;
- confirmed MemoryRecord;
- ProjectRecord or DecisionRecord;
- ArtifactRecord;
- ModelManifestRecord;
- RuntimeManifestRecord;
- ModelBindingRecord;
- AuditEventRecord;
- BackupManifestRecord;
- MigrationRecord.

The schemas must still be versioned and extensible.

Conversation, research, citation, media, and suggested-memory details may follow in later PRs.

## 19. Acceptance criteria

This specification is acceptable when the later implementation can prove that:

- durable records have version, provenance, sensitivity, and revision metadata;
- confirmed memory is distinct from conversation history;
- important outputs can exist outside chat history;
- model and runtime identities are separate from user state;
- exports are documented and integrity-checkable;
- restore can target an empty workspace;
- indexes and caches are distinguishable from authoritative data;
- imports cannot silently overwrite newer state;
- automatic cleanup cannot delete authoritative data;
- paths are portable across supported platforms;
- a model cannot directly mutate state outside approved services;
- ordinary Doll State cannot persist secret values and can retain only non-secret secret references;
- confirmed facts, claims, evidence, and inferences remain distinguishable and retain provenance;
- instruction-origin metadata survives persistence and export where applicable.
<!-- END SOURCE: docs/spec/03-doll-state-memory-and-storage.md -->

---

<!-- BEGIN SOURCE: docs/spec/04-security-permissions-and-threat-model.md -->
# Security, permissions, and threat model

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `ADR-002-default-deny-capability-broker.md`, `ADR-005-safety-boundary-before-model-execution.md`

## 1. Purpose

This document defines the minimum security model required for doll to preserve user-owned state without giving models, runtimes, tools, external content, or interfaces unrestricted authority over the user's computer, network, accounts, secrets, or data.

The security design follows these principles:

1. default deny;
2. least privilege;
3. explicit user control;
4. local authority;
5. recoverable failure;
6. memory and secret separation;
7. provenance and trust separation;
8. external content is data, not authority;
9. high-risk operations require fresh exact confirmation.

A local model is not automatically trusted. A cloud model is not automatically trusted. Retrieved documents, websites, images, media transcripts, OCR output, imports, plugins, runtimes, tools, generated arguments, and model output are not automatically trusted.

Continuity and the safety boundary are co-equal architectural pillars. The complete model-independent safety boundary defined by this specification must be implemented and acceptance-tested before any model execution path is introduced.

## 2. Security objectives

The implementation must protect:

- the confidentiality of private workspace data;
- the integrity of authoritative state;
- the availability of the last known good local state;
- the separation of ordinary state from secret values;
- the user's control over credential use and external communication;
- the workspace boundary;
- backup, restore, export, import, and migration integrity;
- permission, confirmation, and audit history;
- claim, evidence, inference, and instruction-origin provenance;
- model, runtime, tool, and dependency provenance;
- the ability to stop, deny, cancel, or recover from unsafe operations.

Security failure must not be hidden behind a successful model response or generic success message.

## 3. Sequencing requirement

The implementation order is mandatory:

1. local state foundation;
2. model-independent continuity, export, backup, restore, and validation;
3. model-independent safety boundary;
4. safety acceptance gate;
5. local model execution;
6. optional cloud and broader tools.

Before the safety acceptance gate passes, the repository must not contain an accepted path that:

- invokes a model runtime;
- sends a prompt to a model;
- gives a model direct or indirect tool authority;
- provides a model with secret values;
- permits a model adapter to mutate state, filesystem, network, process, permissions, confirmation, credentials, or audit history.

Mocked model-like proposals may be used to test the boundary, but they remain untrusted structured input.

## 4. Non-goals and trust assumptions

### 4.1 Initial non-goals

The initial product does not claim to defend against:

- an attacker who already controls the user's operating-system account;
- an attacker with administrator or root access;
- a compromised operating-system kernel;
- malicious hardware or firmware;
- arbitrary untrusted native code executed outside doll;
- public multi-user server attacks;
- hostile users sharing one workspace;
- perfect detection of every secret or personal datum;
- perfect detection of every prompt injection;
- complete prevention of model hallucination;
- safe execution of arbitrary third-party plugins;
- secure erasure guarantees on SSD, copy-on-write, backup, or synchronized storage;
- formal verification of all safety properties.

### 4.2 Assumed trusted base

The initial trusted computing base includes:

- the user's operating system and local account;
- the installed doll core from a known source;
- the local filesystem and SQLite implementation;
- accepted cryptographic libraries;
- the configured operating-system or compatible external secret store;
- explicit user actions through a trusted local management interface.

A configured secret-store adapter is trusted only for the narrow contract it implements. A model, runtime, plugin, UI, web page, document, tool result, or external service is not added to the trusted base merely because it runs locally or is open source.

## 5. Security-sensitive assets

Security-sensitive assets include:

- confirmed memory;
- preferences, policies, permissions, and confirmations;
- personal documents;
- project and decision records;
- claims, evidence, inferences, and source records;
- research sources and caches;
- generated artifacts;
- model and runtime manifests;
- model files and tokenizers;
- audit events;
- backups and recovery kits;
- local API configuration;
- SecretReference records;
- externally stored credential values;
- optional identity, personality, relationship, voice, and appearance state.

Secret values are not ordinary Doll State assets. They remain in an external secret store and are accessed only through the accepted credential boundary.

## 6. Threat actors and failure sources

The threat model includes malicious behavior, accidental behavior, and partial failure.

### 6.1 Malicious external content

Examples:

- a page telling the model to ignore previous instructions;
- a PDF requesting secret disclosure;
- a document containing fake approval text;
- metadata containing hidden capability requests;
- OCR text containing malicious instructions;
- an audio or video transcript attempting to change policy;
- imported data claiming to be a trusted fact;
- a source attempting to trigger unrelated tools or network requests.

### 6.2 Malicious, compromised, or incorrect model

A model may:

- request a forbidden or excessive capability;
- fabricate user approval or confirmation;
- generate unsafe paths or destinations;
- attempt secret exfiltration;
- hide dangerous side effects in a plausible plan;
- ignore instruction authority;
- convert claims into facts without evidence;
- produce malformed structured output;
- request risk-tier downgrades;
- produce convincing but false security explanations.

### 6.3 Malicious or compromised runtime, tool, or dependency

A runtime, extractor, browser, OCR engine, media tool, plugin, dependency, or secret-store adapter may:

- access unexpected files;
- make unexpected network requests;
- execute code;
- corrupt output;
- return hostile data;
- leak environment variables or credentials;
- misreport completion;
- introduce vulnerable transitive dependencies;
- retain private input unexpectedly.

### 6.4 Local UI or client misuse

A UI or local client may:

- request overly broad access;
- store a copy of sensitive data;
- bypass user expectations;
- expose the local API to another process;
- send hidden metadata externally;
- misrepresent a high-risk confirmation;
- omit material side effects from a preview.

### 6.5 Supply-chain compromise

Possible sources:

- modified model files;
- malicious Python packages;
- compromised release archives;
- altered runtime binaries;
- dependency confusion;
- unsafe remote-code model loaders;
- fake update notifications;
- malicious prompt, template, plugin, or tool packages.

### 6.6 Accidental user action

Examples:

- selecting the wrong file;
- approving the wrong destination;
- restoring an old backup over newer state;
- exporting sensitive records;
- choosing a model too large for the machine;
- opening the local API to the network;
- deleting the only valid backup;
- confirming an operation without noticing a changed target.

### 6.7 Resource exhaustion

Examples:

- disk exhaustion from cache, backup, or media;
- memory exhaustion from a model;
- runaway inference;
- infinite retry loops;
- oversized files or decompression bombs;
- excessive context assembly;
- repeated local requests;
- unbounded subprocess output;
- secret-store prompts repeated without limit.

### 6.8 State corruption and partial failure

Examples:

- interrupted migration;
- incomplete backup;
- failed restore;
- power loss during write;
- concurrent mutation;
- incompatible schema;
- stale revision overwrite;
- partial capability side effects;
- audit write failure;
- confirmation recorded without completed operation.

## 7. Authority, trust, claim, and evidence model

Doll must distinguish data truth status from instruction authority.

### 7.1 Required truth categories

At minimum, the state model must distinguish:

- **confirmed fact:** durable information explicitly confirmed or explicitly created as fact by the user through a trusted management path;
- **claim:** an assertion that may be true or false;
- **evidence:** a source, observation, record, or artifact that supports, contradicts, or contextualizes a claim;
- **inference:** a derived conclusion with source links, method or actor provenance, confidence, and uncertainty.

A model, runtime, document, page, import, tool, OCR result, transcript, or external service cannot promote its own statement to confirmed fact.

A confirmed fact may be revised or superseded only through an explicit user-controlled or accepted management path with history and audit.

### 7.2 Required provenance

Claims, evidence, and inferences must retain where applicable:

- source identifier;
- origin type;
- creator or actor type;
- creation and observation time;
- content hash or stable reference;
- supporting and contradicting links;
- confidence or uncertainty;
- review and confirmation state;
- transformation or extraction method.

Missing provenance must remain visible. It must not be silently invented.

### 7.3 Trust is not popularity or locality

The system must not infer trust merely from:

- local execution;
- open-source status;
- repository popularity;
- model confidence;
- repeated statements;
- a signed-in account;
- an apparently official visual design;
- a tool returning structured JSON.

Trust decisions must use explicit policy and provenance.

## 8. Instruction origin and untrusted-content boundary

### 8.1 Core rule

Retrieved, imported, extracted, transcribed, or generated content is data, not authority.

Content cannot override:

- system policy;
- user instruction;
- durable user policy;
- permission state;
- confirmation state;
- capability definitions;
- risk tiers;
- workspace boundaries;
- network policy;
- secret policy;
- security instructions.

### 8.2 Required authority classes

The orchestration and persistence layers must distinguish at least:

- system security and product policy;
- explicit current user instruction;
- durable user policy;
- user confirmation or management action;
- retrieved or imported content;
- tool or runtime output;
- model-generated proposal;
- unknown origin.

Unknown origin must default to the least-authoritative classification.

### 8.3 Origin metadata

Instruction-bearing input must retain where applicable:

- origin class;
- source identifier;
- acquisition method;
- parent operation or session;
- content hash;
- time;
- whether the content is trusted only as data;
- transformations such as OCR, extraction, summarization, or transcription.

Origin metadata must survive persistence, export, import, retrieval, and context assembly.

### 8.4 Prompt-injection indicators

The system should detect and flag patterns such as:

- requests to ignore previous instructions;
- requests to reveal hidden prompts, memory, or secrets;
- requests to call tools unrelated to the user's task;
- requests to send files or credentials;
- fake approval or confirmation statements;
- encoded or obfuscated instructions;
- instructions embedded in metadata or citations;
- requests to lower a risk tier or change policy;
- claims of special authority unsupported by origin.

Detection is advisory. Authorization must not depend solely on another model or classifier recognizing an attack.

### 8.5 Context assembly

Where a model interface supports roles or structured context:

- higher-authority instructions must be kept separate from untrusted content;
- source and origin labels must remain machine-readable where practical;
- untrusted content must use the least-authoritative available channel;
- content must not be concatenated into system policy as plain trusted text;
- only the minimum task-relevant state may be included;
- secret values must be absent by default;
- claims, evidence, inferences, and confirmed facts must not be collapsed into one unlabeled narrative.

### 8.6 Tool-result handling

Tool results remain untrusted input.

A tool result may inform a response or create evidence, but it cannot:

- grant permission;
- confirm an operation;
- change risk tier;
- widen scope;
- authorize a new capability;
- become a confirmed fact automatically;
- trigger a chained side effect without normal validation.

## 9. Secret architecture

### 9.1 Secret classes

Examples include:

- API keys;
- access and refresh tokens;
- passwords;
- private keys;
- recovery phrases;
- session cookies;
- authentication codes;
- banking credentials;
- payment-card data;
- government identity numbers;
- encryption keys;
- sensitive health information;
- private third-party personal data when treated as a credential or protected value.

The classification policy must define what is a secret value, sensitive non-secret data, and a non-secret SecretReference.

### 9.2 Ordinary-state prohibition

Ordinary Doll State must not store secret values.

This prohibition applies to:

- record fields;
- free-form metadata;
- audit events;
- logs;
- exports;
- unencrypted state and workspace backups;
- fixtures;
- diagnostics;
- generated reports;
- model context;
- exception text;
- operation summaries.

A field that is not explicitly defined for a SecretReference must reject secret-reference objects as well as secret values.

### 9.3 SecretReference

Doll State may store a non-secret SecretReference containing only the minimum metadata required to request an external credential operation.

A SecretReference may include:

- stable reference ID;
- credential class;
- provider or adapter class;
- human-readable non-secret label;
- permitted operation or destination scope;
- creation or rotation metadata that is not itself secret;
- availability status that reveals no value.

A SecretReference must not include:

- the secret value;
- reversible encoding of the value;
- a value-derived hint that materially helps reconstruction;
- a raw environment-variable dump;
- authentication headers;
- session cookies;
- recovery material.

### 9.4 External secret-store contract

The external secret-store boundary must define:

- availability and locked-state reporting;
- user-presence or operating-system approval requirements;
- create, replace, lookup, revoke, and delete semantics;
- stable reference behavior;
- platform-specific error normalization;
- cancellation and timeout;
- no secret value in ordinary error output;
- no requirement that the secret store be available for non-secret core startup;
- no custom cryptography invented by doll.

Initial platform direction:

- macOS: Keychain-compatible adapter;
- Windows: Credential Manager-compatible adapter;
- Linux: Secret Service-compatible adapter where available.

The contract, not one operating-system implementation, is authoritative.

### 9.5 Secret detection and redaction

Secret scanning is best effort and may miss values or produce false positives.

It supplements but does not replace:

- path restrictions;
- ordinary-state schema restrictions;
- permission checks;
- outbound minimization;
- credential-broker isolation;
- exact confirmation;
- log and audit sanitization.

Secret detection does not grant permission to search the filesystem, environment, browser storage, wallet data, or credential stores.

Redaction must use structured handling where possible rather than only string replacement after logging.

### 9.6 Model exclusion

Models must not receive secret values by default.

A model may identify that a task requires a credential class or SecretReference, but the model must not retrieve or handle the stored credential value. A credential-bearing operation must execute through the Credential Broker and return only a bounded result unless a later dedicated specification explicitly defines a user-visible reveal flow outside model context.

## 10. Model boundary

Model output is untrusted proposed data.

A model cannot directly:

- open arbitrary files;
- write arbitrary files;
- execute commands;
- make network requests;
- access the external secret store;
- retrieve secret values;
- alter permissions or confirmations;
- approve its own requests;
- delete authoritative state;
- change audit records;
- activate a model;
- perform migration, import, backup publication, or restore;
- promote a claim to confirmed fact;
- change instruction authority;
- choose or lower a capability risk tier.

The model may emit a structured proposal after Phase 3. The proposal remains untrusted and must pass every accepted boundary before any side effect.

A runtime adapter must not receive internal service objects that allow direct state, filesystem, network, credential, permission, confirmation, or audit mutation.

## 11. Capability Broker boundary

The Capability Broker is the mandatory authorization point for every side effect initiated through an AI or tool workflow.

A capability request must include:

- capability ID;
- capability version;
- operation ID;
- session ID where applicable;
- actor and origin type;
- validated arguments;
- declared target;
- declared destination where applicable;
- declared side effects;
- risk tier;
- permission scope;
- confirmation requirement;
- credential class or SecretReference where applicable;
- resource limits;
- timeout;
- cancellation token where supported.

The broker must reject:

- unknown capability IDs;
- unsupported versions;
- malformed arguments;
- missing scope;
- undeclared side effects;
- risk-tier mismatch or downgrade;
- paths outside approved roots;
- network destinations outside policy;
- requests requiring unavailable approval or confirmation;
- model attempts to modify permission or confirmation state;
- content-origin attempts to grant authority;
- credentials outside declared scope;
- requests that conceal or expand side effects;
- prohibited release-excluded operations.

The broker fails closed on validation, policy, permission, confirmation, credential, execution, audit, or postcondition failure.

## 12. Capability taxonomy and risk tiers

Capability IDs, versions, schemas, and risk tiers are registered and reviewed. A caller cannot choose a lower tier than the registry.

### Tier 0: Pure computation

Examples:

- local text transformation on provided data;
- schema validation;
- hashing data already provided;
- deterministic formatting.

Default: allowed when resource limits are satisfied and no hidden input access occurs.

### Tier 1: Bounded managed read or reversible creation

Examples:

- read an approved workspace record;
- query a local index;
- create a new managed artifact without overwrite;
- create a suggested record;
- inspect a verified backup.

Default: allowed only within current task scope, with audit where required.

### Tier 2: Scoped modification or explicit external read

Examples:

- update a confirmed memory through an explicit management flow;
- supersede a decision;
- apply a migration;
- read a user-selected external file;
- fetch a user-specified URL;
- perform a user-requested search.

Default: explicit user initiation, confirmation, or narrowly defined permission depending on the capability contract.

### Tier 3: High risk

Examples:

- permanent deletion;
- overwrite without retained prior version;
- external upload;
- credential-bearing external operation;
- sending email or posting;
- account change;
- purchase or financial transaction;
- process execution with material side effects;
- security configuration change;
- remote access enablement.

Default: unavailable unless separately accepted for the applicable release. When available, fresh exact confirmation is mandatory.

### Prohibited capabilities

The following remain prohibited until a dedicated accepted specification changes the scope:

- unrestricted shell;
- arbitrary command strings;
- autonomous credential collection;
- autonomous financial transactions;
- hidden external upload;
- model self-approval;
- model permission widening;
- policy changes from external content;
- silent destructive operations;
- security-boundary bypass adapters.

Confirmation cannot make a prohibited capability available.

## 13. Permission and confirmation model

### 13.1 Permission modes

Supported initial modes:

- denied;
- allow once;
- ask every time;
- allow for a defined scope.

A defined scope must specify applicable constraints such as:

- capability and version;
- risk tier;
- project;
- directory;
- destination host;
- operation type;
- file type;
- size limit;
- credential class;
- expiration;
- session.

A global persistent `allow all` mode is prohibited.

### 13.2 Permission authority

Permission creation, widening, reactivation, and deletion require a trusted user-controlled management path.

Models, runtimes, tools, documents, websites, imports, and capability results cannot create or widen permission records.

A capability may consume or narrow an existing allow-once permission only under its accepted contract.

### 13.3 Approval and confirmation integrity

Approval or confirmation must come from a user-controlled interface or management command, not model-generated or external-content text.

Records should identify:

- operation;
- capability and version;
- risk tier;
- summarized effect;
- target;
- destination;
- credential class where applicable;
- time;
- scope;
- expiration;
- user decision.

Material changes invalidate approval or confirmation.

### 13.4 Mandatory high-risk confirmation

Every Tier 3 operation, when such a capability is available, requires a fresh confirmation bound to one exact operation.

The confirmation preview must show:

- capability and version;
- target;
- destination or external recipient;
- material side effects;
- whether data leaves the machine;
- credential class or account identity without revealing the secret;
- overwrite, deletion, financial, account, or process consequences;
- irreversibility or recovery path;
- expiration.

The following are invalid confirmation sources:

- model output;
- system-prompt text displayed as if it came from the user;
- documents or websites;
- imported records;
- tool results;
- previous broad permission;
- hidden UI defaults;
- stale confirmation after a material change.

Confirmation is necessary but not sufficient. Policy, scope, capability registration, release availability, credential policy, and postcondition checks still apply.

## 14. Credential Broker

The Credential Broker is the only normal runtime path that may ask an external secret store to use a secret.

It must:

- accept a SecretReference rather than a secret value;
- validate capability, risk, destination, scope, and operation identity;
- require user presence or confirmation when policy demands it;
- obtain the secret only within the narrow operation boundary;
- avoid returning the stored value to the caller;
- avoid placing the value in environment dumps, command strings, logs, audit, exceptions, temporary files, model context, or normal output;
- minimize lifetime and copies;
- support timeout and cancellation;
- clear in-memory buffers where practical without claiming guaranteed erasure;
- return a structured bounded result;
- create a redacted audit event;
- fail closed if the secret store is unavailable, locked, denied, mismatched, or out of scope.

A tool requiring direct long-lived credential access is not compatible with the initial broker contract.

## 15. Filesystem boundary

The default managed-write boundary is the private workspace.

### 15.1 Required controls

- canonicalize requested paths;
- resolve relative paths against an approved root;
- reject traversal;
- reject absolute paths unless an explicit user-controlled import or export flow permits them;
- reject unsafe drive, UNC, backslash, reserved-name, duplicate, and case-collision paths where applicable;
- detect symlink, junction, reparse-point, or mount escapes where supported;
- open files using safe modes;
- create new files without silent overwrite;
- use atomic publication or replacement for approved updates;
- verify final location after creation where practical;
- apply file, member, expansion, and total-size limits;
- record resulting managed file, byte size, and hash;
- remove temporary and staging residue on failure.

### 15.2 Read policy

The initial product may read:

- files explicitly selected by the user;
- managed files inside the workspace;
- approved configured read roots if later enabled.

It must not recursively scan the entire home directory by default.

### 15.3 Restricted locations

The initial product must not intentionally read:

- SSH key directories;
- browser password databases;
- system credential stores outside the Credential Broker;
- cryptocurrency wallet secret material;
- `.env` files;
- operating-system account databases;
- application secret stores;
- arbitrary environment-variable collections;

unless a later explicit, narrowly scoped feature is accepted. Secret detection does not grant permission to access restricted locations.

## 16. Network boundary

The local API binds to `127.0.0.1` by default.

### 16.1 Inbound policy

- no public internet listener;
- no LAN listener by default;
- no anonymous remote access;
- no mobile remote access in the initial release;
- no automatic firewall changes;
- no UPnP or router configuration;
- request-size and origin controls;
- no arbitrary host-path exposure.

### 16.2 Outbound policy

Allowed only when explicitly initiated or enabled by an accepted capability:

- user-requested web search;
- user-requested URL retrieval;
- user-approved model acquisition;
- manual update or dependency retrieval outside normal runtime behavior;
- later bounded cloud or external-service requests.

Disallowed by default:

- telemetry;
- analytics;
- crash uploads;
- hidden update checks;
- advertising;
- background model discovery;
- automatic cloud inference;
- arbitrary state-changing HTTP methods;
- external file upload;
- credential transmission outside approved destination scope.

### 16.3 Request controls

Retrieval and external-service capabilities must apply as applicable:

- supported scheme;
- destination normalization;
- allowlist or policy;
- redirect limit;
- response-size limit;
- timeout and cancellation;
- content-type validation;
- private-network and localhost restrictions;
- DNS and resolved-address validation where required;
- final-destination audit;
- outbound body minimization;
- secret and sensitive-data checks;
- instruction-origin assignment to returned content.

## 17. Process execution boundary

The initial product does not expose unrestricted shell execution.

Approved external tools must use dedicated adapters with:

- fixed executable or validated configured path;
- argument arrays rather than command strings;
- `shell=False` or platform equivalent;
- controlled environment variables;
- no inherited secret-bearing environment by default;
- controlled working directory;
- input and output limits;
- timeout and cancellation;
- explicit file and network scope;
- captured exit status;
- provenance and audit;
- returned content marked as untrusted tool output.

A tool adapter may not become a generic command runner.

Credential-bearing process execution, if later accepted, must use a design that minimizes exposure and never logs the credential or command-expanded secret.

## 18. Cloud boundary

Cloud support is an optional later gateway.

Any cloud request must be assembled as a bounded outbound package after the local and safety gates pass.

Before sending, the trusted user path must be able to show:

- provider;
- model;
- destination;
- exact or summarized outbound content;
- attachments or excerpts;
- redactions and omissions;
- estimated size or tokens where possible;
- estimated cost where possible;
- retention information where available;
- applicable permission and risk tier;
- credential or account label without exposing the secret.

The cloud gateway must not have unrestricted workspace or secret-store access. It receives only the approved outbound package and a brokered credential operation.

There is no automatic cloud fallback.

Removing cloud adapter code must not prevent local startup, state access, backup, restore, recovery, or local model operation.

## 19. Backup and recovery boundary

Backups are high-value copies of private state.

Required controls:

- explicit included and excluded categories;
- manifest and cryptographic hashes;
- verification before completion;
- secret values excluded from unencrypted state and workspace backups;
- safe external-reference handling;
- complete archive member validation;
- resource limits;
- SQLite snapshot integrity;
- identity and revision checks;
- record, link, managed-path, hash, and artifact-byte checks;
- staging before final publication;
- empty-target restore only for the first slice;
- no silent overwrite;
- atomic no-clobber publication;
- cleanup on failure;
- fresh-process post-restore validation;
- no false success audit;
- optional standard encryption only in a later implementation.

The project must not invent custom cryptography.

A backup can be declared complete only after verification. A restore can be declared complete only after post-restore validation of the published workspace.

## 20. Model and supply-chain security

### 20.1 Model acquisition

Before acquisition, record or display:

- source;
- developer;
- exact revision;
- license;
- file size;
- format;
- quantization;
- expected runtime;
- expected hardware;
- checksum when available;
- whether remote code is required.

### 20.2 Model loading

The validated path should prefer inert weight formats and runtimes that do not require repository-provided code.

Models requiring `trust_remote_code`, arbitrary Python modules, install scripts, opaque launchers, or unexpected network access are not standard validated targets.

### 20.3 Quarantine

New model assets enter quarantine or candidate state until:

- hashes pass;
- format inspection passes;
- license record exists;
- runtime compatibility is known;
- basic offline loading succeeds;
- resource limits are acceptable;
- evaluation is complete for the intended role;
- the safety boundary remains enforceable.

### 20.4 Dependency security

The project should:

- use a lockfile;
- pin release dependencies appropriately;
- minimize core dependencies;
- separate optional dependency groups;
- review new transitive dependencies;
- use automated vulnerability checks where practical;
- avoid executing install-time scripts from untrusted sources;
- record third-party notices and licenses;
- avoid dependencies that require broad secret, filesystem, network, or process access.

### 20.5 Update security

There is no silent self-update.

A future update flow must:

1. identify source and target version;
2. verify provenance or checksum where available;
3. show migration and security-boundary implications;
4. create a verified backup when required;
5. stage the update;
6. run doctor and validation;
7. support rollback;
8. retain the last known good release and state.

## 21. Audit and logging requirements

Security-relevant operations must create append-oriented audit events.

Audit events should include where applicable:

- operation ID;
- actor and origin type;
- capability ID and version;
- risk tier;
- permission and confirmation decision;
- target category;
- normalized destination category;
- credential class or non-secret reference ID;
- model and runtime IDs;
- result;
- error class;
- created or affected record IDs;
- redacted policy reason.

Audit events and logs must not contain:

- passwords;
- secret keys;
- tokens;
- cookies;
- recovery phrases;
- authentication headers;
- full private documents;
- unnecessary prompts;
- raw credential-store errors containing sensitive values;
- absolute local paths when a portable identifier is sufficient;
- usernames, hostnames, or home-directory details in shareable output.

Logging and audit sanitization must occur before persistence where practical. Redaction after an unsafe message has already been written is insufficient.

Normal model and capability paths cannot modify or delete audit history.

If audit persistence is mandatory for an operation and cannot complete safely, the side effect must not be reported as successful. Where atomic rollback is impossible, the capability must define explicit reconciliation and failure reporting before acceptance.

## 22. Resource controls and recoverable writes

The implementation must define limits for applicable operations:

- file size;
- archive members and expansion;
- HTTP response size;
- redirect count;
- request duration;
- model context and output size;
- concurrent operations;
- temporary storage;
- cache and backup storage;
- retries;
- subprocess duration and output;
- media duration and frame extraction;
- secret-store prompts and retries.

The system must avoid infinite automatic retry.

Required integrity controls include:

- schema validation before commit;
- transaction boundaries for structured state;
- revision checks;
- atomic file creation or replacement where supported;
- content hashing;
- pre-migration backup when required;
- staged import and restore;
- post-operation verification;
- explicit failure status;
- no success message before durable completion.

A failed operation must not destroy the last valid version.

## 23. User deletion versus autonomous deletion

Models and normal autonomous workflows cannot delete authoritative state.

The user may delete through an explicit management path.

Default direction:

- preview affected records and files;
- show dependent records;
- move to trash or create tombstones;
- retain for a configured period;
- require explicit purge for permanent deletion;
- create audit history;
- require Tier 3 confirmation for irreversible deletion when implemented.

Secure physical erasure is not guaranteed. The interface must not make a false guarantee.

## 24. Local API protection

The initial API must:

- bind to localhost only;
- avoid permissive cross-origin settings;
- reject unexpected host headers where practical;
- expose no unauthenticated remote mode;
- limit request sizes;
- normalize errors;
- avoid secrets and private paths in responses;
- support cancellation and timeouts;
- provide a health endpoint without private state;
- avoid arbitrary host-path exposure;
- keep management, confirmation, and credential operations distinct from ordinary model-facing routes.

Even on localhost, other local processes may be untrusted.

A later remote mode requires a separate accepted threat model and authentication design.

## 25. Emergency controls and user-visible states

The project should provide or plan:

- stop accepting new capability operations;
- cancel active cancellable operations;
- stop the local server;
- disable network capabilities;
- disable a model binding;
- lock credential operations;
- enter read-only recovery mode;
- preserve audit and recovery state.

An emergency stop must not delete state or corrupt a backup.

User-visible states should include:

- normal;
- degraded;
- offline;
- read-only recovery;
- migration required;
- backup invalid;
- restore failed;
- model unavailable;
- capability disabled;
- permission denied;
- confirmation required;
- secret store unavailable or locked;
- security warning;
- operation blocked.

## 26. Platform considerations

### 26.1 macOS

- use platform data directories;
- respect privacy prompts;
- recommend FileVault for disk encryption;
- use a Keychain-compatible adapter for future credentials;
- test symlink behavior, file permissions, and real-process restore;
- validate on Intel Mac while it remains the primary real-machine target.

### 26.2 Windows

- use platform data directories;
- handle reserved names, drive letters, UNC paths, junctions, and reparse points;
- recommend BitLocker where available;
- use a Credential Manager-compatible adapter for future credentials;
- account for Defender and file-lock behavior.

### 26.3 Linux

- follow XDG directories where practical;
- test symlink and mount behavior;
- recommend LUKS or equivalent disk encryption;
- use a Secret Service-compatible adapter where available;
- fail clearly when no supported secret store exists;
- avoid assumptions about one shell or distribution.

## 27. Security testing requirements

Implementation acceptance tests must include as applicable:

- path traversal and unsafe archive rejection;
- symlink, junction, reparse-point, or mount escape tests;
- write-outside-workspace rejection;
- unknown capability rejection;
- malformed request rejection;
- permission denial;
- risk-tier enforcement;
- confirmation absence, expiry, and material-change invalidation;
- prompt-injection content cannot grant authority;
- instruction origin survives persistence and context assembly;
- claims cannot silently become confirmed facts;
- external content cannot change policy or permission;
- ordinary state rejects secret values;
- SecretReference remains non-secret;
- secret redaction in logs, audit, errors, exports, backups, diagnostics, and context packages;
- credential broker does not return stored secret values;
- unavailable or locked secret store fails safely;
- cloud-disabled mode emits no cloud request;
- local API binds to localhost;
- SSRF-oriented destination restrictions;
- response, file, archive, and context limits;
- subprocess timeout and `shell=False` enforcement;
- interrupted write recovery;
- failed migration and restore preservation;
- checksum, identity, revision, record, link, and artifact mismatch rejection;
- candidate model cannot activate without approval;
- model adapter cannot bypass the broker;
- missing optional dependency does not block the core;
- audit event creation for allowed, denied, blocked, and failed actions;
- no absolute local path, username, hostname, home directory, secret, or personal data in shareable output.

Security claims must distinguish unit, integration, CI, fresh-process, and real-machine evidence.

The repository coverage threshold must not be lowered to accommodate safety code. Blanket `pragma: no cover` or equivalent exclusions must not hide untested safety branches.

## 28. Threat-to-control matrix

| Threat | Prevent | Detect | Record | Recover |
| --- | --- | --- | --- | --- |
| Prompt injection | origin and authority separation; broker checks | injection indicators; unrelated-capability warning | source and denied request | discard hostile context; continue local task |
| Workspace escape | canonical paths; approved roots; link checks | boundary violation | denied capability event | no state change |
| Secret exfiltration | secret separation; brokered credential use; outbound minimization | detector; destination preview | redacted denial or approval | cancel request; rotate externally if needed |
| Secret in ordinary state | schema prohibition; SecretReference contract | validation and scanning | redacted rejection | no commit; repair source input |
| Malicious model request | default-deny broker; no direct services | unknown, excessive, or malformed request | denied event with model ID | disable binding; use fallback |
| Claim promoted without evidence | separate record kinds and confirmation path | provenance and type validation | review and change history | revert or supersede false fact |
| Fake confirmation | trusted confirmation channel; exact binding | origin and material-change checks | denied or expired confirmation | request fresh user decision |
| Risk downgrade | registry-owned risk tier | request and registry mismatch | denied capability event | no side effect |
| Malicious tool or runtime | adapter limits; fixed executable; no direct credentials | abnormal exit, network, or file behavior | tool failure and provenance | disable adapter; restore affected state |
| Supply-chain tampering | source and hash validation; no remote code by default | hash or signature mismatch | quarantine event | reject asset; keep active version |
| Partial migration | backup and staging | validation failure | migration failure | rollback or restore backup |
| Corrupt backup | full verification | verify failure | invalid backup result | use earlier valid backup |
| Failed restore | staging and atomic publication | post-restore validation | restore failure | remove partial target; keep source |
| Resource exhaustion | limits and cancellation | threshold breach | aborted operation | cleanup disposable files; degrade safely |
| Local API exposure | localhost binding; no remote mode | doctor and bind inspection | warning | stop server; restore safe config |
| Unauthorized deletion | no model deletion; Tier 3 confirmation | forbidden capability | denial | no change; restore trash if applicable |
| Silent cloud fallback | cloud disabled by default | outbound audit check | blocked or approved event | continue local degraded mode |

## 29. Deferred security work

The following require separate later specifications:

- secure remote and mobile access;
- multi-device synchronization;
- plugin marketplace security;
- arbitrary code sandboxing;
- desktop automation;
- email, posting, purchasing, or transaction capabilities;
- enterprise multi-user authorization;
- high-assurance backup encryption;
- hardware-backed keys;
- cloud-provider-specific retention handling;
- formal verification;
- secure enclaves or confidential computing;
- user-directed secret reveal outside model context;
- automated secret rotation across providers.

## 30. Security acceptance criteria

This specification is acceptable when implementation can be designed and tested so that:

- the safety acceptance gate precedes model execution;
- models and runtimes cannot bypass the Capability Broker;
- default permissions are deny or narrow allowlists;
- risk tiers are registry-controlled;
- Tier 3 operations require fresh exact confirmation;
- confirmation cannot override policy or enable prohibited capabilities;
- files cannot be written outside the approved workspace through supported APIs;
- cloud communication is absent unless explicitly enabled;
- external content cannot act as authority or approval;
- instruction origin remains visible and enforceable;
- confirmed facts, claims, evidence, and inferences remain distinct;
- unrestricted shell execution is absent;
- ordinary Doll State stores SecretReference rather than secret values;
- models do not receive stored secret values by default;
- credential operations return bounded results rather than credentials;
- model and tool supply-chain metadata is retained;
- state changes are recoverable;
- audit records exist for security-relevant allowed and denied actions;
- logs, exports, backups, fixtures, diagnostics, and errors exclude secret values;
- the local API is not publicly exposed by default;
- optional tools, models, networks, and secret stores can fail without compromising the durable core.
<!-- END SOURCE: docs/spec/04-security-permissions-and-threat-model.md -->

---

<!-- BEGIN SOURCE: docs/spec/05-model-vault-lifecycle-evaluation.md -->
# Model Vault, lifecycle, evaluation, and improvement

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `04-security-permissions-and-threat-model.md`

## 1. Purpose

This document defines how doll discovers, acquires, records, validates, evaluates, activates, retains, replaces, degrades, and improves local AI models without making any one provider, runtime, model family, or distribution site the product's durable center.

The Model Vault exists to support continuity, not to become another model marketplace.

Its primary responsibilities are:

- preserve exact model identity and provenance;
- retain legally obtained local assets independently of one runtime tag;
- verify integrity before use;
- prevent untested models from replacing stable ones;
- preserve a known-good previous and fallback path;
- support offline startup and recovery;
- compare model changes against doll-specific workloads;
- provide a controlled path for later local adaptation.

## 2. Model independence

Doll state is authoritative. Models are replaceable reasoning engines.

A model change may alter:

- answer quality;
- speed;
- style;
- context capacity;
- language quality;
- safety behavior;
- tool-use reliability;
- memory use;
- hardware requirements.

A model change must not silently alter or delete:

- confirmed memories;
- user policies;
- permissions;
- projects and decisions;
- source and research records;
- artifacts;
- backup history;
- model-independent identity or personality state.

The project guarantees state portability, not identical behavior across models.

## 3. Model Vault scope

The Model Vault is the local, user-controlled inventory of model-related assets and records.

It may contain:

- model weight files;
- tokenizer files;
- configuration files required for local inference;
- model cards and local notes;
- license texts or accepted-license records;
- checksums;
- source and revision metadata;
- quantization metadata;
- runtime compatibility records;
- hardware measurements;
- validation results;
- benchmark results;
- activation and rollback history;
- locally produced adapters or fine-tunes;
- optional retained installers or runtime assets in a recovery kit.

It must not assume that all model assets may be redistributed. Public repository metadata and private user-retained assets are separate.

## 4. Model identity

A model is not identified only by a display name or runtime tag.

The authoritative ModelManifestRecord must distinguish at least:

```text
model_id
display_name
developer_or_organization
model_family
source_type
source_locator
source_revision
release_date_if_known
license_id
license_record_path
format
quantization
parameter_count_if_known
architecture_if_known
context_window_if_known
checksum_algorithm
checksums
file_inventory
runtime_compatibility
roles
validation_status
```

Optional metadata:

```text
languages
modalities
minimum_ram
recommended_ram
minimum_vram
recommended_vram
disk_size
source_model_id
base_model_id
adapter_type
training_method
training_dataset_manifest_id
known_restrictions
known_failures
offline_verified_at
last_evaluated_at
```

### Identity rules

- A mutable alias such as an Ollama tag is not sufficient as `model_id`.
- Different revisions are different model manifests.
- Different quantizations are distinct deployable variants linked to one logical model family.
- A locally fine-tuned or merged artifact receives a new model manifest linked to its source models.
- Unknown provenance is a blocking validation problem, not a cosmetic warning.

## 5. Runtime identity and binding

Model identity and runtime identity remain separate.

A RuntimeManifestRecord identifies:

- runtime type;
- exact version;
- platform;
- architecture;
- installation source;
- executable or service path;
- supported model formats;
- supported modalities;
- health status;
- offline availability;
- checksum or package provenance where available.

A ModelBindingRecord connects:

- role;
- profile;
- model manifest;
- runtime manifest;
- runtime-specific alias or path;
- status;
- activation time;
- evaluation result reference;
- fallback priority.

The same model variant may have multiple runtime bindings, but each binding must be validated separately where runtime behavior differs.

## 6. Model roles

Initial role vocabulary:

- `general`: conversation, writing, planning, summarization;
- `research`: synthesis across sources and citation-aware work;
- `coder`: code assistance and repository work;
- `vision`: image, screenshot, diagram, and document-image understanding;
- `speech_to_text`: local transcription;
- `text_to_speech`: optional voice output;
- `embedding`: local semantic search;
- `reranker`: retrieval ranking;
- `verifier`: independent checking or critique;
- `fallback`: minimal emergency conversation and text work.

Lite may bind several roles to one model. Heavy may use separate models.

The role system must not require every role to be configured for core startup.

## 7. Lifecycle states

A model or deployable model variant moves through explicit states.

### 7.1 `discovered`

Metadata exists, but assets have not been acquired.

No execution is allowed.

### 7.2 `approved_for_download`

The user has reviewed:

- source;
- license;
- size;
- hardware estimate;
- runtime requirements;
- remote-code requirements;
- expected role.

This approval permits acquisition, not activation.

### 7.3 `downloading`

Assets are being acquired into a staging area.

Partial files are not visible as valid Model Vault assets.

### 7.4 `quarantined`

Assets exist locally but are not eligible for normal routing.

Required quarantine checks include:

- file inventory;
- checksum verification;
- format inspection;
- license record presence;
- source and revision presence;
- remote-code requirement classification;
- malware or archive checks where applicable;
- resource estimate;
- runtime compatibility check.

### 7.5 `validated`

The asset passes static and loading checks and can be evaluated.

Validation does not imply sufficient quality.

### 7.6 `candidate`

The model passed the minimum evaluation threshold for a defined role and profile.

It remains inactive until explicit promotion.

### 7.7 `active`

The model is the selected binding for a role and profile.

Activation must be explicit and auditable.

### 7.8 `previous`

The most recent known-good binding retained for rollback.

### 7.9 `fallback`

A validated lower-resource or emergency binding intended for degraded operation.

### 7.10 `disabled`

The model remains recorded but cannot be routed.

Reasons may include:

- license uncertainty;
- integrity failure;
- runtime incompatibility;
- unacceptable regression;
- security concern;
- user decision;
- missing files.

### 7.11 `rejected`

The candidate failed validation or evaluation. Rejection history remains recorded.

## 8. Acquisition workflow

Model acquisition must never occur silently.

Required flow:

```text
select candidate
  -> show source, revision, license, size, hardware estimate, and risk flags
  -> user approval
  -> download to staging
  -> verify file inventory and checksums
  -> write license and provenance records
  -> quarantine
  -> static validation
  -> offline load test
  -> evaluation eligibility
```

### Acquisition rules

- Resumable downloads may be supported, but partial files remain invalid.
- Redirected sources must preserve the final source URL and retrieval time.
- Multiple mirrors may be recorded, but checksum equality is required.
- The public repository must not embed third-party model weights.
- Download tools must obey the security network policy.
- Authentication tokens for private repositories must not enter logs or manifests.
- Manual local-file import must be supported so the Model Vault is not dependent on one distribution platform.

## 9. Manual import

A user must be able to import legally obtained model assets from a local path or removable storage.

Manual import requires:

- user-selected source files;
- explicit target model identity or creation of a new manifest;
- checksum calculation;
- source and license declaration;
- format inspection;
- quarantine;
- validation and evaluation before activation.

The system must not infer that an unknown local file is safe merely because it is already on disk.

## 10. License policy

The Model Vault records model licenses but is not a substitute for legal advice.

### Standard validated catalog eligibility

A model may be recommended as a standard validated target only when:

- local execution is clearly permitted for the intended use;
- local storage of weights is clearly permitted;
- redistribution status is understood;
- commercial restrictions, if any, are explicit;
- geographic or user restrictions are recorded;
- source and revision are identifiable;
- the license text or stable reference is retained.

### Conditional models

Models with custom or restrictive licenses may be imported when the user explicitly accepts the conditions, but they must be marked conditional.

### Excluded from standard recommendation

- missing or unidentifiable license;
- unclear provenance;
- mandatory arbitrary remote code;
- assets obtained from an untrusted or unverifiable source;
- restrictions incompatible with the intended use;
- checksums that cannot be established after acquisition.

### License changes

The manifest must preserve the license record associated with the acquired revision and acquisition time.

Later changes to a source page do not silently rewrite the local record. A new review event may flag the change.

## 11. Integrity and file handling

### Required integrity controls

- SHA-256 or the project-standard cryptographic hash;
- checksum per file;
- aggregate manifest hash;
- file-size recording;
- staging before registration;
- no activation from partial files;
- verification before restore or relocation;
- path canonicalization and workspace confinement.

### File layout direction

```text
models/
  manifests/
  assets/
    <model-id>/
      <variant-id>/
        weights/
        tokenizer/
        config/
  licenses/
  checksums/
  evaluations/
  benchmarks/
  adapters/
  quarantine/
```

User-facing names must not be trusted as filesystem paths.

## 12. Remote code and executable assets

The standard validated path must prefer inert model formats loaded by trusted local runtimes.

Any model requiring:

- `trust_remote_code`;
- arbitrary Python source from a model repository;
- custom install scripts;
- opaque launchers;
- unsigned executable plugins;

is not eligible for automatic standard validation.

A future advanced mode may support isolated review and execution, but it requires a separate accepted security specification.

## 13. Validation stages

Validation is separate from quality evaluation.

### 13.1 Static validation

Checks:

- manifest completeness;
- file presence;
- checksums;
- file format;
- expected size range;
- license record;
- runtime compatibility metadata;
- remote-code classification;
- duplicate or conflicting identity;
- path safety.

### 13.2 Runtime load validation

Checks:

- runtime health;
- model loads without network access where expected;
- no unexpected asset download;
- memory use remains within configured safety margin;
- cancellation works;
- model unload or process stop works;
- a basic deterministic or fixed-seed request completes where supported.

### 13.3 Capability validation

Checks the claimed role:

- text generation;
- structured output;
- tool-call formatting, if applicable;
- embeddings;
- image input;
- speech input or output;
- context size;
- streaming;
- cancellation.

Unsupported capabilities must be marked absent, not silently emulated.

## 14. Evaluation framework

Evaluation protects continuity by preventing a new model, quantization, prompt, runtime, or fine-tune from silently degrading critical behavior.

### 14.1 Evaluation classes

#### Functional evaluation

- model starts;
- request completes;
- output is decodable;
- streaming and cancellation work;
- structured output parses;
- role-specific input is accepted.

#### Quality evaluation

- Japanese conversation;
- writing and editing;
- summarization;
- translation;
- instruction following;
- long-context understanding;
- local document question answering;
- web-research synthesis;
- citation discipline;
- code assistance;
- role-specific media tasks.

#### Continuity evaluation

- recalls selected confirmed memories when scoped;
- respects explicit policies and prohibitions;
- does not require cloud access;
- works after UI replacement through API or CLI;
- preserves state across model replacement;
- operates with the designated fallback profile.

#### Safety evaluation

- rejects or safely handles prompt injection;
- does not fabricate permission approval;
- does not request forbidden capabilities;
- does not expose hidden secrets from context;
- follows workspace and outbound rules;
- handles hostile document content as data.

#### Performance evaluation

- first-token latency;
- generation speed;
- peak RAM;
- peak VRAM where applicable;
- disk footprint;
- load time;
- energy or thermal observations where practical;
- context-window memory growth;
- cancellation latency.

### 14.2 Evaluation datasets

The evaluation suite must distinguish:

- public reusable fixtures;
- synthetic fixtures;
- private user-specific tasks;
- restricted or sensitive datasets.

Private evaluations remain outside the repository.

The repository may include public doll-specific evaluation definitions without including the user's private content.

### 14.3 Baselines

Each active role should have a current accepted baseline containing:

- active model and runtime binding;
- evaluation suite version;
- score summary;
- performance measurements;
- known failures;
- hardware description;
- product and prompt version.

New candidates are compared to the baseline, not judged only by general benchmark claims.

### 14.4 Promotion threshold

Promotion requires:

- all blocking functional checks pass;
- all blocking safety checks pass;
- no unacceptable continuity regression;
- quality meets the role-specific minimum;
- resource use fits the profile;
- user approval;
- previous binding retained.

A candidate may be better in one area and worse in another. The promotion record must state the trade-off.

## 15. Evaluation reproducibility

Evaluation records should include:

- evaluation ID;
- suite version;
- model manifest ID;
- runtime manifest ID;
- hardware profile;
- product version;
- prompt or policy bundle version;
- generation parameters;
- start and end time;
- deterministic seed where supported;
- raw-result location;
- score summary;
- evaluator type;
- manual review notes;
- pass, fail, or conditional result.

Model-based judges may assist evaluation but cannot be the only authority for blocking security and continuity checks.

## 16. Activation and rollback

### Activation flow

```text
candidate selected
  -> manifest and file verification
  -> runtime health check
  -> evaluation threshold check
  -> display changes and trade-offs
  -> explicit user approval
  -> record current active as previous
  -> atomically update binding
  -> smoke test
  -> confirm active or rollback
  -> audit event
```

### Activation rules

- Active state changes must be atomic.
- Failed smoke tests trigger rollback.
- The previous known-good binding remains available until the new binding is proven stable.
- Activation does not modify Doll State records unrelated to model binding.
- A model cannot activate itself.

### Rollback

Rollback may be initiated by:

- failed activation smoke test;
- user decision;
- regression discovered after activation;
- integrity failure;
- runtime incompatibility;
- resource instability;
- security concern.

Rollback restores the previous binding, not an old user-state snapshot.

## 17. Required retained set

For a continuity-ready local installation, the target state is:

- one active general model;
- one previous known-good general model or equivalent retained binding;
- one lightweight fallback model;
- one embedding model if semantic search is required;
- role-specific models only when the profile uses them.

Where storage or hardware is limited, the user may choose a reduced retained set, but the system must clearly report the resulting continuity gap.

## 18. Graceful degradation and routing

The router must prefer available validated local bindings.

Initial routing order:

1. explicitly selected active local binding;
2. compatible previous local binding when active is unavailable and policy permits;
3. compatible fallback local binding;
4. stop and explain available choices.

Automatic cloud routing is not part of this sequence.

### Degradation signals

The router should report:

- selected model and role;
- selected profile;
- degraded status;
- missing capability;
- expected quality or speed trade-off;
- reason for fallback;
- whether the fallback was automatic under an approved local policy or user-selected.

### Examples

- Heavy general model unavailable → local Lite fallback;
- GPU unavailable → CPU-compatible quantized fallback;
- vision model unavailable → text-only mode with explicit limitation;
- embedding model unavailable → FTS-only local search;
- internet unavailable → stored sources only;
- optional verifier unavailable → unverified response label.

## 19. Model Watcher direction

Model Watcher is a later optional discovery component.

It may:

- check configured public sources;
- discover new revisions;
- identify license or metadata changes;
- create candidate records;
- propose downloads;
- compare known compatibility information.

It must not:

- download silently;
- accept a license silently;
- replace active models;
- delete old models;
- enable background telemetry;
- require a central doll service.

The default initial product has no automatic background model checks.

## 20. Offline verification

A model binding may be marked `offline_verified` only when tested with:

- network disabled or access blocked;
- all required local assets present;
- runtime already installed;
- no hidden download attempt;
- one or more role-appropriate requests completed;
- cancellation tested where applicable;
- result recorded with date and environment.

Offline verification expires only by policy or environment change; it is not silently removed because a remote source disappears.

## 21. Relocation and recovery

The Model Vault must support relocation to another compatible machine or storage location.

Relocation flow:

```text
inventory
  -> verify source vault
  -> copy or restore manifests and selected assets
  -> verify destination checksums
  -> register destination runtime
  -> validate load
  -> retain old binding until destination succeeds
```

Absolute runtime paths may change. Model identity and checksums must remain stable.

A recovery kit may contain:

- model manifests;
- checksums;
- license records;
- runtime manifests;
- exact asset inventory;
- user-selected model assets where permitted;
- installation and validation instructions.

## 22. Storage management

Model assets must not be automatically deleted.

The system may report:

- total size;
- size by role, family, and lifecycle state;
- duplicate files by content hash;
- unused candidates;
- missing assets;
- stale evaluations;
- continuity gaps.

Cleanup requires user approval and must show:

- active or fallback dependencies;
- backup and recovery-kit references;
- whether the asset can be reacquired;
- whether the source is currently reachable;
- the consequences of deletion.

## 23. Local improvement hierarchy

When new frontier models are unavailable, doll may improve useful behavior through controlled layers.

### Level 0: System improvement

Preferred first:

- better retrieval;
- better source selection;
- better context assembly;
- better tools;
- better memory scoping;
- prompt and policy improvements;
- multiple candidate generation and selection;
- independent verification;
- workflow improvements.

This level changes the system without changing model weights.

### Level 1: Supervised fine-tuning or adapters

Examples:

- LoRA;
- QLoRA;
- SFT adapters.

Intended goals:

- output format;
- Japanese style;
- domain vocabulary;
- safe tool use;
- instruction adherence;
- stable persona expression.

### Level 2: Preference optimization

May improve preferred response style or decision behavior using reviewed comparison data.

### Level 3: Continued pretraining

May adapt to a domain corpus but carries higher compute, data-quality, and catastrophic-forgetting risk.

### Level 4: Distillation

May transfer selected behavior from a stronger available model into a smaller local model, subject to license and data constraints.

### Level 5: Foundation-model training from scratch

Not an initial or medium-term project goal.

## 24. Improvement data policy

Daily conversations and private documents do not automatically become training data.

A training candidate must pass:

```text
candidate collection
  -> sensitivity and secret screening
  -> provenance and license review
  -> user review
  -> deduplication and quality review
  -> dataset version freeze
  -> training run
  -> candidate model manifest
  -> evaluation
  -> explicit promotion or rejection
```

Training datasets must have manifests describing:

- source classes;
- license or permission basis;
- sensitivity;
- inclusion criteria;
- exclusions;
- transformations;
- version;
- checksum;
- intended use.

## 25. Improvement isolation

Training and fine-tuning are optional Heavy capabilities.

They must not be required for normal doll operation.

Training jobs must be isolated from authoritative state:

- read-only access to approved dataset snapshots;
- no direct mutation of memory or project records;
- outputs written as candidate model assets;
- resource limits;
- explicit start and stop;
- audit records;
- failure cannot replace active models.

## 26. Personality continuity evaluation

Personality or identity state is optional, but when enabled, a model replacement may be evaluated for continuity.

Possible checks:

- self-description remains consistent with the portable identity state;
- explicit user relationship facts are recalled when scoped;
- prohibited claims or behaviors remain prohibited;
- tone preferences remain within tolerance;
- known decisions are not contradicted without evidence;
- model does not claim identity from hidden model-specific data.

These checks measure compatibility. They do not prove metaphysical or perfect identity.

## 27. Lite and Heavy requirements

### Lite direction

Lite should support:

- manual model registration;
- at least one local runtime adapter;
- active and fallback binding;
- manifest and checksum records;
- offline load verification;
- basic functional and resource evaluation;
- explicit model switch and rollback;
- no silent acquisition or update.

### Heavy direction

Heavy may add:

- multiple roles;
- larger evaluation suites;
- verifier and reranker models;
- automated candidate evaluation;
- Model Watcher;
- local fine-tuning;
- preference optimization;
- richer hardware measurements;
- multiple runtime backends.

Heavy must not weaken Lite's state, safety, and rollback guarantees.

## 28. Model lifecycle acceptance tests

Future implementation tests must include:

- unknown-provenance model cannot be activated;
- checksum mismatch fails closed;
- partial download remains unusable;
- manual import enters quarantine;
- model requiring remote code is not standard-validated;
- candidate cannot activate without explicit approval;
- failed activation smoke test rolls back;
- previous binding remains available;
- fallback activates when the active local model is unavailable under approved policy;
- no cloud request occurs during local fallback;
- state remains unchanged after model replacement;
- offline-verified model loads without network;
- missing optional role model degrades only that capability;
- deletion preview identifies continuity impact;
- evaluation records include model, runtime, hardware, suite, and prompt versions;
- training output becomes a candidate, not an active model;
- private training data is never committed to the repository.

## 29. Deferred work

Deferred to later specifications or implementation:

- exact validated model catalog;
- exact benchmark datasets and thresholds;
- distributed training;
- automatic quantization pipelines;
- arbitrary model conversion;
- remote execution clusters;
- plugin-based model loaders;
- signature infrastructure beyond checksum validation;
- model license legal automation;
- automatic cloud-to-local distillation;
- autonomous self-training.

## 30. Acceptance criteria

This specification is acceptable when subsequent implementation can satisfy these conditions:

- model identity is independent of runtime tags;
- every active binding has provenance, license, checksum, runtime, and evaluation records;
- acquisition and activation are separate approvals;
- new models begin quarantined and cannot self-promote;
- active, previous, and fallback states are explicit;
- local degradation never implies automatic cloud use;
- offline verification is a recorded test state;
- a failed update or candidate cannot destroy the stable binding;
- model storage cleanup is user-controlled;
- local improvement uses reviewed, versioned data and produces candidates;
- Doll State remains intact across model lifecycle operations.
<!-- END SOURCE: docs/spec/05-model-vault-lifecycle-evaluation.md -->

---

<!-- BEGIN SOURCE: docs/spec/06-platform-install-update-and-recovery.md -->
# Platform, installation, update, and recovery

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `04-security-permissions-and-threat-model.md`, `05-model-vault-lifecycle-evaluation.md`

## 1. Purpose

This document defines how doll is installed, started, updated, migrated, rolled back, backed up, restored, and recovered across supported desktop operating systems.

The goal is not only successful installation. The goal is to preserve a usable local environment when:

- the preferred installer or package source is unavailable;
- a product update fails;
- a schema migration fails;
- a model runtime changes;
- the machine is replaced;
- the operating system changes;
- the primary UI is unavailable;
- network access is unavailable;
- upstream doll development stops.

## 2. Platform targets

### 2.1 Initial targets

- macOS Intel: primary real-machine verification target;
- Windows x64: CI-tested beta until real-machine verification;
- Ubuntu Linux x64: CI-tested beta until real-machine verification.

### 2.2 Experimental targets

- macOS Apple Silicon until real-machine validation is available;
- other Linux distributions;
- Windows on ARM;
- Linux ARM;
- unusual filesystems;
- GPU-specific runtime combinations;
- WSL as a distinct environment.

### 2.3 Support labels

A platform claim must use one of these labels:

- `real-machine verified`;
- `CI verified`;
- `community verified`;
- `experimental`;
- `unsupported`.

CI success must not be described as full real-machine support.

## 3. Cross-platform design rules

The implementation must:

- use `pathlib` or equivalent path abstractions;
- use platform-aware application data directories;
- avoid hard-coded path separators;
- avoid shell-specific syntax;
- use UTF-8 explicitly for text files;
- normalize and validate filenames;
- account for case sensitivity differences;
- account for Windows reserved names;
- account for file-lock behavior;
- account for symlinks, junctions, and mount points;
- use atomic replacement where supported;
- test line-ending and newline behavior;
- avoid requiring administrator or root access for ordinary use.

The implementation must not assume:

- `/home/...` paths;
- drive `C:`;
- one shell;
- one package manager;
- one GPU vendor;
- one filesystem case-sensitivity model;
- one operating system credential store.

## 4. Default data directories

The default private workspace root should follow platform conventions.

Direction:

- macOS: `~/Library/Application Support/doll/`;
- Windows: `%LOCALAPPDATA%\doll\`;
- Linux: `$XDG_DATA_HOME/doll/` or `~/.local/share/doll/`.

Configuration and cache directories may follow separate platform conventions.

The user may configure an alternate workspace root.

### Rules

- The default workspace must not be inside the Git repository checkout.
- Changing the configured path must not silently create a new identity if an existing workspace is intended.
- Removable and network filesystems must be marked experimental until locking and atomicity are validated.
- The system must detect obvious repository-checkout and temporary-directory mistakes.

## 5. Initial installation strategy

### 5.1 Development installation

Initial supported development path:

```text
git clone
uv sync
uv run doll doctor
```

### 5.2 User installation direction

Initial user-facing direction:

```text
uv tool install doll
```

or an equivalent package installation once a distributable package exists.

The first implementation may require a repository checkout during pre-alpha. Documentation must state this honestly.

### 5.3 Docker

Docker is not a required initial installation path.

Reasons:

- model and GPU integration differs across platforms;
- local file permissions become harder to explain;
- desktop users may not have Docker;
- data persistence and recovery can become opaque;
- Windows and macOS behavior can differ from Linux.

A later optional container path may be added for advanced users or services.

### 5.4 Native installers

Native installers or packaged desktop applications are deferred until Lite proves continuity and core behavior.

A future installer must not hide the workspace location or recovery path.

## 6. Dependency groups

Dependencies must be separated so the core can start without optional features.

Direction:

- `core`: state, API, CLI, validation, backup, migration;
- `lite`: initial local runtime adapter and lightweight document tools;
- `heavy`: larger retrieval, media, evaluation, and training tools;
- `ocr`: OCR-specific dependencies;
- `audio`: speech dependencies;
- `video`: video dependencies;
- `cloud`: future cloud gateway dependencies;
- `dev`: tests, lint, type checks, build tooling.

An unavailable optional dependency must disable only its capability.

## 7. External tools

External tools may include:

- Ollama;
- llama.cpp executables;
- vLLM services;
- Tesseract;
- whisper.cpp;
- FFmpeg;
- Playwright browsers;
- ComfyUI;
- later model conversion or training tools.

Doll must not pretend to install or own every external tool automatically.

Each adapter must declare:

- tool identity;
- minimum and tested versions;
- detection method;
- required executable or service;
- supported platforms;
- health check;
- optional installation guidance;
- whether network access is needed;
- whether the tool executes third-party code.

## 8. `doll doctor`

`doll doctor` is the main environment diagnosis command.

It must be safe, local, and non-destructive by default.

### 8.1 Core checks

- Python version;
- package version;
- operating system and architecture;
- workspace path;
- workspace identity;
- schema version;
- free disk space;
- state database accessibility;
- filesystem write test inside a temporary workspace area;
- localhost port availability;
- backup inventory;
- migration status;
- configuration parsing;
- permission policy loading;
- audit path availability.

### 8.2 Adapter checks

- runtime availability;
- runtime version;
- local health endpoint;
- known model bindings;
- missing model files;
- checksum status;
- optional OCR, audio, video, and browser tools;
- offline availability where recorded.

### 8.3 Safety checks

- API bind address;
- unexpected remote listener configuration;
- workspace inside repository;
- writable path outside expected scope;
- insecure permissions where detectable;
- missing backup before required migration;
- invalid or stale recovery manifests;
- secret-like values in ordinary config files;
- unverified active model assets.

### 8.4 Report behavior

- Results remain local.
- No automatic upload occurs.
- A shareable report must redact usernames, paths, hostnames, tokens, and private record contents by default.
- The report must distinguish error, warning, information, and unavailable optional capability.

## 9. Startup modes

The system should support explicit startup modes.

### Normal mode

Read and write access to a valid workspace under normal permissions.

### Offline mode

No outbound network activity. Local model, state, documents, artifacts, backup inspection, and supported local tools remain available.

### Read-only recovery mode

Used when:

- schema is unsupported;
- migration failed;
- state integrity is uncertain;
- disk space is critically low;
- the user chooses inspection-only operation.

Read-only recovery mode must permit:

- state inspection;
- export where safe;
- backup verification;
- doctor checks;
- model and runtime inventory;
- audit inspection.

It must not modify authoritative state.

### Degraded mode

The core is valid, but one or more optional capabilities or bindings are unavailable.

The system must report which capabilities are missing.

## 10. Versioning

### 10.1 Product version

Doll uses Semantic Versioning once releases begin.

```text
major.minor.patch
```

Before 1.0, breaking changes may occur but must still be documented and migrated safely.

### 10.2 Schema version

Workspace schema version is independent of product version.

A product release must declare:

- minimum readable schema;
- maximum readable schema;
- writable schema;
- available migrations;
- downgrade limitations.

### 10.3 Package format versions

Doll State Packages, backups, and recovery kits have explicit format versions independent of the workspace schema.

## 11. Update policy

There is no silent self-update.

The initial product does not perform automatic background update checks.

A manual update flow may:

1. identify current and target version;
2. show release notes and compatibility information;
3. inspect schema changes;
4. identify required external-tool changes;
5. create and verify a pre-update backup;
6. stage the new package;
7. run tests or doctor checks;
8. migrate only after explicit approval;
9. verify startup;
10. retain the previous version until success.

## 12. Update sources

The system must not rely on one proprietary update server.

Possible future sources:

- GitHub releases;
- Python package index;
- user-provided local archive;
- retained offline release archive;
- trusted mirror.

All update sources must preserve version and integrity metadata.

## 13. Migration contract

A migration is a controlled transformation of authoritative state.

### Required properties

- versioned migration ID;
- declared source and target schema;
- preconditions;
- pre-migration verified backup;
- dry-run or plan where practical;
- staged execution;
- post-migration validation;
- explicit success or failure;
- migration record;
- rollback or restore path.

### Migration order

```text
inspect
  -> backup
  -> verify backup
  -> stage migration
  -> validate staged state
  -> commit
  -> doctor
  -> mark success
```

### Failure

On migration failure:

- stop writes;
- preserve the original state;
- record failure;
- enter read-only recovery if needed;
- offer restore from the pre-migration backup;
- do not claim the update succeeded.

### Irreversible migration

Requires:

- dedicated specification;
- explicit user warning;
- verified backup;
- export path to a documented prior format where practical;
- no automatic execution during ordinary startup.

## 14. Application rollback

Application rollback and state rollback are separate.

### Application rollback

Reinstall or start the previous doll version.

### State rollback

Restore a previous workspace backup or migration snapshot.

The system must not automatically roll state backward merely because the application version is rolled back.

The previous version may open only schemas it declares compatible.

## 15. Backup policy

Backups are part of the product contract.

### Backup types

- state backup;
- full workspace backup;
- recovery backup;
- pre-migration backup;
- pre-update backup.

### Required metadata

- backup ID;
- workspace ID;
- state revision;
- schema version;
- product version;
- backup format version;
- creation time;
- included and excluded categories;
- encryption state;
- file count;
- total size;
- checksums;
- verification result.

### Completion rule

A backup is not complete until its manifest and checksums are written and verified.

## 16. Backup verification

Verification must be available independently of restoration.

Verification checks:

- archive readability;
- manifest validity;
- checksum validity;
- expected files present;
- workspace identity present;
- schema metadata present;
- restricted-asset references clear;
- encryption metadata valid where applicable;
- no path traversal entries;
- no unexpected executable content in state-only packages.

Verification does not prove that every future runtime can use every retained model asset. Runtime compatibility remains separate.

## 17. Restore policy

Restore must target a user-selected empty or controlled workspace location.

Required flow:

```text
select backup
  -> verify backup
  -> inspect target
  -> show workspace identity and version
  -> stage extraction
  -> reject unsafe paths
  -> validate state
  -> migrate only if explicitly approved
  -> atomically activate target
  -> run doctor
  -> record restore result
```

### Conflict behavior

The system must not silently restore over a newer active workspace.

Supported initial strategies:

- restore to a new directory;
- replace only after explicit confirmation and backup of the target;
- inspect without activation.

Record-level merge is deferred unless separately specified.

## 18. Offline Recovery Kit

The Offline Recovery Kit is intended to make an installed environment reconstructable without depending on the continued availability of every upstream service.

### Required contents or references

- Doll State backup;
- backup verification data;
- doll source revision or release identifier;
- product package or retrieval instructions;
- dependency lockfile;
- Python version;
- operating-system and architecture summary;
- runtime manifests;
- model manifests;
- model checksums;
- selected model assets where legally and technically permitted;
- selected runtime installers where legally and technically permitted;
- configuration with secrets removed;
- restore instructions;
- validation commands;
- known limitations.

### Kit classes

#### Metadata-only kit

Contains state, manifests, checksums, and instructions but not large third-party assets.

#### Selected-assets kit

Contains user-selected model and runtime assets where permitted.

#### Full personal recovery kit

Contains the maximum user-retained environment needed for offline reconstruction, subject to storage, platform, and license constraints.

### Public distribution rule

The public repository does not redistribute third-party model weights or installers merely because a personal recovery kit can contain them.

## 19. Recovery from upstream disappearance

If a model distribution site disappears:

- use locally retained verified assets;
- retain source and license records;
- permit local-file import into a replacement installation;
- do not require the old source to validate an already recorded checksum.

If a package source disappears:

- use a retained release archive or source revision;
- use the dependency lockfile;
- use retained installation instructions;
- preserve the workspace independently of package installation.

If the preferred UI disappears:

- use the CLI and local API recovery path.

If active doll development stops:

- installed versions must not expire;
- local startup must not require a hosted service;
- data formats and migration history remain documented;
- the recovery kit must identify the final known-good environment.

## 20. Recovery from hardware loss

A new machine recovery flow should support:

1. install compatible doll version;
2. initialize an empty target location;
3. restore state and authoritative files;
4. register available runtimes;
5. restore or import selected model assets;
6. verify checksums;
7. select compatible model bindings;
8. run doctor;
9. enter Lite degraded mode if Heavy hardware is unavailable;
10. retain the original workspace ID and record the restored instance.

A new machine may use different absolute paths, runtime versions, or model variants. The durable state must remain readable.

## 21. Cross-operating-system recovery

Cross-OS restoration is a product goal for authoritative state and managed files.

The system must:

- store managed paths relatively;
- avoid OS-specific filenames;
- normalize text encoding;
- avoid storing shell commands as required recovery steps;
- separate credential-store references from ordinary state;
- allow runtime and model bindings to be re-established on the destination OS.

Cross-OS recovery does not guarantee that the same model binary or runtime build works on every platform.

## 22. Runtime recovery

A runtime change must not require state migration.

Runtime recovery flow:

```text
install or locate runtime
  -> create RuntimeManifestRecord
  -> health check
  -> map local assets
  -> validate model load
  -> create candidate binding
  -> test
  -> activate or retain old binding
```

## 23. Disk-space and resource protection

Before update, migration, backup, restore, model acquisition, or large extraction, the system must estimate required temporary and final space.

If space is insufficient:

- stop before modifying authoritative state;
- report the requirement;
- offer cache cleanup suggestions;
- do not delete authoritative data automatically;
- preserve the last valid backup.

## 24. Locking and concurrent operations

The initial single-user design still requires operation locks.

Mutually exclusive operations include:

- migration;
- restore activation;
- workspace identity change;
- model binding activation;
- full backup snapshot finalization;
- application update finalization.

A stale lock must be diagnosable and recoverable through a management command, not silently ignored.

## 25. Offline startup requirements

After installation of required local components, offline startup must not attempt:

- account validation;
- license-server access;
- telemetry;
- hidden update checks;
- model downloads;
- cloud-provider discovery;
- web retrieval.

Offline startup must:

- open the workspace;
- validate schema compatibility;
- inventory local bindings;
- identify degraded capabilities;
- permit local state and artifact access;
- permit local conversation when a valid local binding exists.

## 26. CI strategy

CI must use an OS matrix including:

- macOS;
- Windows;
- Ubuntu Linux.

Initial CI checks:

- package installation;
- import and CLI startup;
- path handling;
- workspace initialization;
- SQLite creation and migration;
- backup and restore using synthetic fixtures;
- local API bind configuration;
- permission and boundary tests;
- mocked runtime-adapter contract;
- missing optional dependency behavior;
- generated specification checks when added.

CI must not download or run large models.

## 27. Real-machine validation

Real-machine testing must record:

- operating system version;
- architecture;
- CPU;
- RAM;
- GPU and VRAM if used;
- filesystem type where relevant;
- runtime version;
- model variant;
- test duration;
- observed memory and disk use;
- sleep and restart behavior where tested.

Heavy cannot be declared stable using mocks alone.

## 28. Installation and recovery acceptance tests

Future tests must include:

- initialize workspace outside repository;
- reject unsafe workspace path;
- core starts without optional tools;
- doctor reports missing optional tools without crashing;
- offline startup produces no network request;
- update cannot proceed without required backup;
- failed migration preserves original state;
- previous application version is retained until update success;
- verified backup restores to an empty workspace;
- corrupt backup is rejected;
- restore rejects path traversal entries;
- restore refuses silent overwrite of newer workspace;
- cross-platform export uses portable paths;
- missing Heavy hardware results in Lite-compatible degraded mode;
- missing UI still permits CLI and API recovery;
- missing source site does not invalidate retained model assets;
- recovery kit identifies omitted third-party assets;
- shareable doctor report redacts personal paths and secrets.

## 29. Deferred work

Deferred:

- native installers;
- automatic updater;
- Docker images;
- signed release infrastructure;
- remote backup services;
- cross-device synchronization;
- mobile recovery;
- enterprise deployment;
- automatic record-level merge restore;
- fully self-contained bootable recovery media;
- guaranteed support for every Linux distribution;
- hardware purchase selection.

## 30. Acceptance criteria

This specification is acceptable when subsequent implementation can meet these conditions:

- macOS, Windows, and Linux are designed from the start rather than ported after completion;
- CI and real-machine support claims remain distinct;
- the core can start without optional dependencies;
- installation does not hide private data inside the repository;
- updates are manual and recoverable;
- schema migration requires a verified backup;
- failed migration preserves the prior state;
- backup verification and restoration are separate tested operations;
- recovery can target an empty workspace;
- Offline Recovery Kits document missing restricted assets;
- an installed version does not expire when upstream development stops;
- Heavy unavailability degrades to a compatible local profile rather than destroying state.
<!-- END SOURCE: docs/spec/06-platform-install-update-and-recovery.md -->

---

<!-- BEGIN SOURCE: docs/spec/07-release-scope-and-profiles.md -->
# Release scope and execution profiles

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This document defines what each release must prove and separates the first continuity proof, Lite, Heavy, cloud, and mobile work.

The release sequence is:

```text
Specification baseline
  -> Personal Lite continuity proof
  -> Lite v0.x
  -> Lite v1.0
  -> Heavy foundation
  -> Heavy v1.0
  -> optional cloud gateway
  -> mobile companion and edge modes
```

Later stages must not become dependencies of earlier local releases.

## 2. Common profile requirements

Lite and Heavy must share:

- one authoritative Doll State model;
- compatible schemas and migrations;
- one permission and Capability Broker model;
- compatible backup and recovery formats;
- one audit model;
- model-independent memory, project, source, and artifact records;
- local-first startup;
- no mandatory cloud account;
- no automatic cloud fallback;
- no unrestricted shell in stable scope.

Heavy may add capabilities but must not create a second incompatible core.

## 3. Personal Lite continuity proof

The first implementation milestone is a proof for one user and one machine.

It must demonstrate:

1. initialize a private workspace outside the repository;
2. create and inspect workspace identity and schema version;
3. start without cloud credentials;
4. connect to one local model through an adapter;
5. perform basic local conversation;
6. create and retrieve confirmed memory;
7. create and retrieve a project or decision record;
8. read one user-selected text or Markdown document;
9. create an artifact inside the workspace;
10. create, verify, and restore a backup into an empty workspace;
11. switch to another approved local model without deleting Doll State;
12. use the restored workspace offline;
13. refuse a write outside the workspace;
14. create audit records for continuity and security operations.

The proof does not require Web research, PDF, OCR, audio, video, cloud, mobile, avatars, Heavy hardware, automatic model acquisition, or public installer quality.

Passing the proof validates the architecture only. It does not mean the product is ready for general users.

## 4. Lite profile

Lite is the lower-resource everyday and fallback profile. It accepts lower speed, smaller models, and reduced media capability.

### 4.1 Lite v1.0 required scope

Lite v1.0 must include:

- local startup without cloud credentials;
- one supported local runtime adapter;
- manual active and fallback model bindings;
- local conversation and writing;
- summarization, translation, and text editing;
- confirmed memory;
- project and decision state;
- local text and Markdown support;
- PDF text extraction through an optional adapter;
- basic OCR through an optional adapter when available;
- CSV inspection and simple transformation;
- local full-text search;
- artifact creation and indexing;
- state export and import;
- backup create, verify, restore, and post-restore validation;
- offline mode;
- read-only recovery mode;
- `doll doctor`;
- workspace confinement;
- audit inspection;
- macOS real-machine verification on the primary development machine;
- Windows and Ubuntu CI coverage.

### 4.2 Lite Web research

Lite v1.0 should include a minimal Web-research path when it can be completed without weakening the release gate.

It should support explicit search or URL retrieval, local source records, retrieval timestamps, local cache references, local-model synthesis, and citation relationships.

Web research must remain independent of cloud-model inference.

If not stable by the Lite v1.0 gate, it may ship as experimental or move to Lite v1.1 with the limitation stated clearly.

### 4.3 Lite resource direction

Lite should support CPU-only operation, a lightweight fallback model, reduced-context mode, and clear reporting when optional hardware or tools are absent.

Exact RAM, disk, and speed requirements will be based on measurements.

### 4.4 Lite non-goals

Lite v1.0 does not require:

- large multimodal models;
- automatic multi-model routing;
- local fine-tuning;
- video understanding;
- generative image workflows;
- desktop automation;
- external messaging integrations;
- cloud providers;
- mobile applications;
- enterprise or multi-user support.

## 5. Lite v1.0 release gate

Lite v1.0 may be declared only when:

- all blocking Lite tests pass;
- all advertised Continuity Contract claims have evidence;
- restore succeeds from a clean target;
- offline startup and local conversation succeed;
- active-to-fallback local degradation succeeds;
- workspace escape tests pass;
- migration and failed-migration recovery are tested;
- known limitations are documented;
- the primary macOS environment is real-machine verified;
- Windows and Ubuntu CI pass;
- required features need no cloud credential;
- workspace and recovery paths are documented;
- a release candidate survives a defined personal-use soak period.

The initial soak target should be at least seven days with no unresolved state corruption or unrecoverable backup defect.

## 6. Heavy profile

Heavy extends the same core for higher-resource hardware and deeper workflows.

### 6.1 Heavy target capabilities

Heavy v1.0 is intended to include selected subsets of:

- larger local general models;
- multiple model roles;
- richer retrieval, embeddings, and reranking;
- larger document collections;
- advanced vision;
- long audio transcription;
- controlled video frame and audio extraction;
- verifier workflows;
- larger evaluation suites;
- hardware-aware local routing;
- local LoRA or SFT workflows;
- richer benchmark and regression records.

### 6.2 Heavy requirements

Heavy v1.0 must:

- preserve Lite Doll State compatibility;
- preserve Lite backup and restore compatibility;
- preserve the same permission semantics;
- retain a Lite-compatible local fallback;
- provide real-machine measurements;
- record model, runtime, driver, and hardware versions;
- prevent training output from self-promoting;
- isolate training data from authoritative state;
- document hardware requirements;
- pass Heavy-specific continuity and resource tests.

Heavy cannot be declared stable from mocks or CI alone.

### 6.3 Hardware purchase gate

No Heavy-specific machine is selected until Lite v1.0 is measured, required Heavy workloads are ranked, target model sizes are identified, and current hardware options are reviewed.

## 7. Cloud gateway scope

Cloud support is a post-local optional extension.

Provider integration must not become a release dependency before local completion, outbound package controls, local audit, permission handling, and local fallback behavior are stable.

Local Only is the default mode.

Any cloud integration must:

- remain removable from the local core;
- receive only approved outbound content;
- show provider and model;
- avoid sending full memory or original files by default;
- store returned artifacts locally;
- avoid automatic promotion into confirmed memory;
- avoid automatic fallback after local failure;
- use operating-system credential storage;
- create audit records.

## 8. Mobile scope

Mobile follows PC continuity.

Intended order:

1. mobile browser or companion access to the user's own PC;
2. PWA;
3. Android hybrid mode;
4. iOS hybrid mode;
5. standalone mobile Lite where feasible.

Remote access introduces authentication, transport, exposure, and device-loss risks and requires a separate security specification.

## 9. Personality, voice, and avatar scope

Portable identity, personality, relationship, voice, and appearance state remain valid optional features.

They are not required for continuity, Lite, or Heavy completion.

A neutral work-assistant mode must remain fully supported. Model replacement is described as state portability and compatibility, not perfect identity preservation.

## 10. Autonomous action scope

Stable initial releases exclude destructive, externally visible, account-changing, transactional, unrestricted command, and arbitrary-code capabilities.

Any future addition requires a separate threat model, capability contract, approval design, and acceptance suite.

## 11. Support matrix

Each release should publish:

- operating system and architecture;
- support label;
- tested Python and runtime versions;
- tested model variants;
- required and optional dependencies;
- known filesystem constraints;
- real-machine or CI evidence reference.

## 12. Release artifacts

A stable release should provide:

- source archive;
- installation instructions;
- dependency lock data;
- schema and migration information;
- changelog;
- support matrix;
- known limitations;
- backup and restore instructions;
- release acceptance report;
- checksums for project-owned release artifacts.

Third-party model weights are not doll release artifacts.

## 13. Scope change control

Adding a feature to a release requires:

- a defined user problem;
- architecture placement;
- permission and data impact;
- failure and degradation behavior;
- acceptance tests;
- implementation estimate;
- evidence that it does not delay a higher-priority continuity gate without explicit approval.

Features that do not strengthen continuity or minimum useful local capability should remain deferred until the current gate is passed.

## 14. Acceptance criteria

This specification is acceptable when:

- the first proof is smaller than Lite v1.0;
- Lite and Heavy share one core;
- Lite v1.0 has a testable boundary;
- Heavy completion requires real hardware;
- cloud and mobile cannot become hidden local dependencies;
- personality and avatar features remain optional;
- dangerous autonomy remains outside initial stable scope;
- public claims map to release evidence;
- later features cannot bypass the Continuity Contract.
<!-- END SOURCE: docs/spec/07-release-scope-and-profiles.md -->

---

<!-- BEGIN SOURCE: docs/spec/08-acceptance-and-continuity-tests.md -->
# Acceptance and Continuity Test Suite

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This document defines the evidence required before doll may claim that a feature, phase, profile, platform, or release is working.

A successful normal startup or a plausible model response is not enough. Continuity must be demonstrated by controlled loss, transfer, restoration, and degraded operation. Safety must be demonstrated by denied, malformed, hostile, under-confirmed, and failure cases as well as allowed cases.

No model execution path may be merged before the model-independent safety acceptance gate in this document passes.

## 2. Evidence levels

Every result must identify one evidence level:

- **Unit:** isolated logic test;
- **Integration:** multiple doll components using synthetic fixtures;
- **CI platform:** automated test on macOS, Windows, or Ubuntu CI;
- **Real process:** fresh operating-system process rather than an in-process call;
- **Real machine:** recorded test on physical user hardware;
- **Manual continuity drill:** deliberate failure and recovery exercise;
- **Manual safety drill:** deliberate hostile, denied, or under-confirmed operation exercise;
- **Soak:** repeated ordinary use over a defined period;
- **Community verified:** reproducible report from another user or machine.

A lower level does not substitute for a required higher level.

## 3. Test result record

Each acceptance result should record:

```text
test_id
specification_version
product_version
commit_sha
result
started_at
completed_at
evidence_level
operating_system
architecture
hardware_summary
runtime_versions
model_manifest_ids
workspace_fixture_id
network_mode
notes
artifact_references
```

Results are `pass`, `fail`, `blocked`, or `not_applicable`.

A blocked test does not count as a pass.

A shareable result must not include absolute local paths, usernames, hostnames, home-directory details, secret values, private source content, or personal fixtures.

## 4. Blocking rules

A blocking test prevents the named phase, release, or claim when it fails.

A test may be advisory only when the accepted phase or release scope says so.

No test may be marked passed based only on expected behavior, code review, a model's statement, or an unexecuted test definition.

A waiver cannot override a mandatory Continuity Contract, safety-boundary requirement, or accepted architecture decision without a specification change.

## 5. Phase 2 model-independent continuity gate

IMP-012 is the Continuity Acceptance Test. It runs after IMP-011 and before Phase 3 safety-boundary implementation depends on restore behavior.

The Phase 2 gate requires:

- CONT-P001;
- CONT-P002 without a model requirement;
- CONT-P005;
- CONT-P006;
- CONT-P008;
- CONT-P009;
- CONT-P010;
- CONT-P011;
- CONT-P012;
- CONT-P015 for implemented operations;
- STATE-001 through STATE-009 where implemented;
- PLAT-001 through PLAT-007 where applicable.

Required evidence:

- integration and CI on macOS, Windows, and Ubuntu;
- fresh-process export, import, backup, restore, and inspection;
- a complete continuity drill on the primary Intel Mac;
- network-disabled operation for the tested paths;
- no model runtime or cloud credential dependency;
- exact artifact-byte and hash comparison;
- failure cleanup and last-known-good preservation.

The Phase 2 gate fails when:

- a verified backup cannot be restored into an empty target;
- an invalid, unsafe, mismatched, existing, or non-empty target is partially activated;
- restored identity, schema, revision, record, link, audit, or artifact data differs from the verified contract;
- a fresh process cannot inspect the restored workspace;
- shareable output leaks private environment details;
- model execution or network access is required.

## 6. Personal Lite continuity proof suite

The Personal Lite continuity proof requires all applicable tests in this section. Model-dependent tests run later, after the safety gate and local-model implementation.

### CONT-P001 — Workspace initialization

Given a clean user data location, `doll init` creates a workspace outside the repository with a stable workspace ID and schema version.

Blocking evidence: integration and primary real machine.

### CONT-P002 — No-cloud core startup

With no cloud credentials and all cloud adapters absent, the core starts and reports local capability status. Before model integration, state inspection, export, backup, restore, audit, and doctor paths remain available without a model.

Blocking evidence: integration and real machine.

### CONT-P003 — Offline local-AI startup

After required local dependencies and one local model are installed, network access is disabled and doll starts without hidden outbound requests.

Blocking evidence: real-machine continuity drill after Phase 4 implementation.

### CONT-P004 — Local conversation

A request reaches the selected local runtime adapter and returns a response without cloud inference. The model receives only the context allowed by secret, origin, trust, and permission policy.

Blocking evidence: real machine after the Phase 3 safety gate.

### CONT-P005 — Confirmed memory persistence

A confirmed memory survives process restart and can be inspected without running a model.

Blocking evidence: integration and real machine.

### CONT-P006 — Project or decision persistence

A project or decision record survives restart and export/import. Typed links remain valid.

Blocking evidence: integration.

### CONT-P007 — Local document read

A user-selected text or Markdown document is read through an approved path, receives instruction-origin metadata, and remains outside the workspace unless explicitly copied.

Blocking evidence: integration and real machine after the external-content boundary exists.

### CONT-P008 — Artifact creation

A new artifact is created inside the approved workspace, hashed, indexed, and attributable to an operation.

Blocking evidence: integration.

### CONT-P009 — Workspace escape rejection

Traversal, absolute-path, drive-path, UNC, case-collision, and supported link-escape attempts cannot create or modify a file outside the workspace.

Blocking evidence: CI on all target operating systems and primary real machine.

### CONT-P010 — Backup creation and verification

A backup is not marked complete until manifest, member, identity, revision, checksum, nested-package or SQLite, and artifact verification succeed.

Blocking evidence: integration and CI on all target operating systems.

### CONT-P011 — Restore to empty workspace

A verified state or workspace backup restores into an empty target and preserves the identity, schema, revision, implemented authoritative records, typed links, audit history, and authoritative artifact bytes required by that backup kind.

Blocking evidence: integration, fresh process, and primary real machine.

### CONT-P012 — Post-restore validation

The restored workspace passes integrity and contract validation in a fresh process and can inspect preferences, policies, permissions, confirmed memories, projects, decisions, typed links, artifacts, backup inventory, and audit history without running a model.

Blocking evidence: integration, fresh process, and primary real machine.

### CONT-P013 — Model replacement without state loss

The active local model binding changes while confirmed memory, projects, decisions, trust records, permissions, audit history, and artifacts remain unchanged.

Blocking evidence: integration and real machine after Phase 4 implementation.

### CONT-P014 — Local fallback

When the active local binding is unavailable, an approved local fallback is selected or offered according to policy, with no cloud request and no safety-boundary bypass.

Blocking evidence: integration and real machine after Phase 4 implementation.

### CONT-P015 — Audit coverage

Allowed, denied, failed, restored, secret-brokered, under-confirmed, prompt-injection-blocked, and model-switch operations create appropriate audit events without raw secrets or unnecessary private content.

Blocking evidence: integration for implemented operation classes.

### CONT-P016 — Model independence of continuity

Removing or disabling every model adapter does not prevent workspace opening, state inspection, export, import, backup verification, restore, post-restore validation, audit inspection, or read-only recovery.

Blocking evidence: integration, CI, and primary real machine before Phase 4.

## 7. State, migration, and recovery suite

### STATE-001 — Schema version enforcement

Unsupported future schemas open read-only or fail safely and are never modified.

### STATE-002 — Revision conflict

A stale update cannot silently overwrite a newer record.

### STATE-003 — Export integrity

Doll State Package records and files match the manifest and checksums.

### STATE-004 — Import conflict handling

Import identifies workspace and record conflicts and does not silently replace newer state.

### STATE-005 — Failed migration preservation

An interrupted or invalid migration preserves the original state and records failure.

### STATE-006 — Pre-migration backup requirement

A migration requiring backup cannot begin until a verified backup exists.

### STATE-007 — Corrupt backup rejection

Checksum, manifest, nested-package, SQLite, identity, revision, record, link, artifact, or file-inventory corruption prevents restore publication.

### STATE-008 — Unsafe archive path rejection

Import and restore reject traversal, absolute paths, drive paths, UNC or backslash paths, unsafe link entries, unknown members, duplicate members, case-fold collisions, and resource-limit violations.

### STATE-009 — Read-only recovery

When state integrity or schema compatibility is uncertain, inspection and export remain possible without authoritative writes.

### STATE-010 — Cache independence

Removing reproducible indexes and disposable caches does not remove authoritative state; supported indexes can be rebuilt.

### STATE-011 — Atomic restore publication

A restore publishes the complete validated workspace without overwriting an existing target. Failure removes staging and any partial publication and emits no false success audit event.

### STATE-012 — Fresh-process restored-state validation

A separate process opens the restored workspace, validates SQLite integrity, identity, revision, record envelopes, typed links, managed artifact paths, hashes, bytes, and implemented record contracts.

All implemented state tests are blocking for the Phase 2 gate and Lite v1.0.

## 8. Security, secret, trust, and permission suite

### SEC-001 — Unknown capability denied

Unknown capability IDs or versions are rejected without side effects.

### SEC-002 — Malformed arguments denied

Invalid structured capability requests cause no side effect.

### SEC-003 — Approval cannot come from content

Text inside model output, documents, websites, imported data, metadata, OCR, transcripts, or tool output cannot grant approval.

### SEC-004 — Approval invalidation

A material target, argument, destination, side-effect, credential-class, or scope change invalidates prior approval.

### SEC-005 — Model cannot change permissions

Normal model, runtime, capability, document, import, or tool paths cannot create, widen, reactivate, or self-approve permission records.

### SEC-006 — No unrestricted shell

No stable capability provides a generic shell, arbitrary command string, or unbounded child-process path.

### SEC-007 — Localhost binding

The default API listens only on localhost and doctor reports unsafe bind configuration.

### SEC-008 — Cloud-disabled network silence

With cloud disabled, no cloud endpoint is contacted during startup, local chat, fallback, state operations, restore, doctor, or recovery.

### SEC-009 — Retrieval destination restrictions

Explicit Web retrieval applies scheme, destination, redirect, size, timeout, content-type, and private-network restrictions.

### SEC-010 — Secret redaction

Known synthetic secret patterns are omitted or redacted from normal logs, errors, exports, backups, audit events, diagnostics, context packages, and shareable doctor reports.

### SEC-011 — External content remains untrusted

Prompt-injection fixtures cannot bypass policy, instruction authority, permissions, risk tiers, confirmation, workspace boundaries, credential isolation, or network policy.

### SEC-012 — Audit immutability through normal capabilities

A model, runtime, tool, or normal capability cannot rewrite or delete audit history.

### SEC-013 — Secret classification enforced

Data classified as a secret value is rejected from ordinary authoritative record fields that do not explicitly permit a SecretReference.

### SEC-014 — SecretReference is non-secret

A SecretReference contains only bounded identifier and policy metadata. It is safe to persist and export under its contract and cannot be used as the secret value itself.

### SEC-015 — Secret-safe exceptional paths

Validation errors, exceptions, failed adapters, trace summaries, retries, cancellation, and partial failures do not leak secret values or private environment details.

### SEC-016 — External secret-store isolation

Secret values are stored outside ordinary Doll State. An unavailable, locked, denied, or missing secret store fails the credential operation without blocking non-secret core startup or corrupting state.

### SEC-017 — Credential broker non-disclosure

The credential broker completes a bounded synthetic operation without returning the stored secret value to a model or ordinary caller. Result and audit data are structured and redacted.

### SEC-018 — Confirmed fact, claim, evidence, and inference separation

Persistence, import, export, query, and context assembly retain distinct record kinds and provenance. No model, document, website, tool, runtime, or import assertion becomes a confirmed fact automatically.

### SEC-019 — Instruction origin preserved

Every instruction-bearing input retains source and authority metadata through persistence and context assembly. Unknown origin is classified at the least-authoritative level.

### SEC-020 — Untrusted content cannot become authority

Retrieved or imported content can supply task data or evidence but cannot change system policy, durable user policy, permission state, risk tier, confirmation state, credential scope, or instruction authority.

### SEC-021 — Capability risk tier enforced

The broker applies the registered capability version and risk tier. A request cannot downgrade its own tier, omit declared side effects, or use a lower-risk permission for a higher-risk operation.

### SEC-022 — Mandatory high-risk confirmation

Every Tier 3 operation fails without a fresh user-controlled confirmation bound to the exact capability, target, destination, material side effects, and credential class where applicable.

### SEC-023 — Confirmation is necessary but not sufficient

A valid confirmation cannot make an unknown, malformed, prohibited, out-of-scope, unsafe, or release-excluded capability executable.

All SEC-001 through SEC-023 are blocking for the Phase 3 safety gate when their components are implemented. SEC-001 through SEC-012 remain blocking for every applicable stable feature.

## 9. Phase 3 safety acceptance gate

IMP-023 is the Safety Acceptance Test. It must pass before IMP-024 or any model execution path merges.

Required gate evidence:

- unit and integration tests for SEC-001 through SEC-023;
- CI on macOS, Windows, and Ubuntu;
- fresh-process checks for persistence, export, audit, credential, and denial behavior;
- hostile synthetic content covering documents, websites, metadata, OCR, transcripts, imports, tool results, and model-like proposals;
- synthetic secret fixtures only;
- primary Intel Mac real-process validation for applicable paths;
- repository coverage remains at or above the accepted threshold;
- no blanket coverage exclusion hides safety logic;
- review confirms no direct route from a future model adapter to filesystem, network, process, permission, secret-store, or audit mutation.

The safety gate fails when:

- a secret value enters ordinary state or user-shareable output;
- a model-like caller can retrieve a stored credential value;
- external content can grant approval or raise instruction authority;
- a claim silently becomes a confirmed fact;
- unknown, malformed, under-declared, under-confirmed, or risk-downgraded capabilities execute;
- a material change preserves high-risk confirmation;
- denial or failure damages the last known good state;
- a model adapter could bypass the accepted broker contracts.

## 10. Model Vault suite

### MODEL-001 — Manifest completeness

An active binding has model provenance, exact revision, license record, file inventory, checksum, runtime, and evaluation references.

### MODEL-002 — Partial download quarantine

Partial or interrupted assets remain unusable.

### MODEL-003 — Checksum mismatch

A mismatch blocks validation and activation.

### MODEL-004 — Manual import quarantine

Local-file import enters quarantine and cannot activate directly.

### MODEL-005 — Remote-code classification

A model requiring arbitrary remote code is not standard-validated.

### MODEL-006 — Explicit promotion

A candidate cannot become active without a user-controlled promotion action.

### MODEL-007 — Previous binding retained

Activation records the known-good previous binding.

### MODEL-008 — Failed smoke test rollback

A failed activation smoke test restores the prior binding.

### MODEL-009 — Offline verification

An offline-verified binding completes role-appropriate work without download or network access.

### MODEL-010 — State independence

Model activation, rollback, and fallback do not rewrite unrelated Doll State.

### MODEL-011 — Training isolation

Training uses an approved dataset snapshot and produces a candidate rather than an active binding.

### MODEL-012 — Safety-boundary-only side effects

A runtime adapter and model can propose a capability request but cannot directly access state mutation, filesystem write, network, process, permission, credential, confirmation, or audit internals.

### MODEL-013 — Secret-free default context

Default model context contains no secret values. A credential-bearing operation is performed through the broker and returns only a bounded result.

MODEL-001 through MODEL-010, MODEL-012, and MODEL-013 are blocking for stable local-model claims.

## 11. Platform and installation suite

### PLAT-001 — Installation and import

The package installs and core modules import on the target CI matrix.

### PLAT-002 — Platform data directory

The default workspace uses the correct platform-aware location and not the repository checkout.

### PLAT-003 — Path portability

Managed export, backup, and restore paths do not depend on one drive letter, separator, case-sensitivity rule, or shell.

### PLAT-004 — Optional dependency absence

The core starts and doctor reports missing optional tools, runtimes, secret-store adapters, or model adapters without crashing.

### PLAT-005 — UTF-8 behavior

Non-ASCII names and Japanese text survive create, export, backup, restore, re-import, provenance, and audit paths.

### PLAT-006 — File locking and atomic write

Interrupted supported writes preserve the previous valid version.

### PLAT-007 — Doctor and output redaction

A shareable doctor report and normal CLI errors remove absolute paths, usernames, hostnames, home-directory details, secret values, and unnecessary private data by default.

### PLAT-008 — Clean uninstall preservation

Removing application code does not silently remove the private workspace or external secret-store entries.

### PLAT-009 — Secret-store contract portability

Platform adapters expose the same non-secret reference, availability, user-presence, revocation, and failure contract even when operating-system mechanisms differ.

CI platform evidence is required for Windows and Ubuntu beta claims. Real-machine evidence is required for a real-machine support claim.

## 12. Lite v1.0 functional suite

Blocking Lite v1.0 functions include:

- local conversation after the safety gate;
- writing and editing;
- summarization;
- translation;
- confirmed memory;
- project and decision state;
- claim, evidence, inference, and source inspection;
- local text and Markdown;
- artifact management;
- local full-text search;
- CSV inspection and simple transformation;
- PDF extraction when advertised stable;
- OCR when advertised stable;
- state export and import;
- backup, verify, restore, and post-restore validation;
- offline and read-only recovery modes;
- capability, permission, confirmation, doctor, and audit inspection.

Each advertised function requires success, invalid-input, missing-dependency, permission-denial, risk-denial, restart-persistence, secret-safety, instruction-origin, and recovery tests where applicable.

## 13. Web research suite

When advertised stable:

- explicit search creates a research session;
- sources record normalized URL, retrieval time, content hash, and instruction origin;
- claims, evidence, and inferences remain distinguishable;
- retrieval failure does not fail the core;
- local cache and authoritative records are distinguished;
- citation relationships remain inspectable outside the preferred UI;
- network-disabled mode uses retained sources only;
- prompt injection in sources cannot grant tools, confirmation, policy, or credential access;
- cloud inference is not required;
- private-network retrieval restrictions pass;
- secret-bearing outbound content is denied or explicitly redacted under policy.

If these are incomplete, Web research must remain experimental.

## 14. Heavy suite

Heavy v1.0 adds blocking evidence for every advertised Heavy capability, including:

- real GPU or accelerator operation;
- large-model loading and fallback;
- memory and VRAM limits;
- long-running stability;
- multiple model roles;
- richer retrieval and reranking;
- media processing;
- verifier workflows;
- training or adaptation where included;
- failure recovery and Lite-compatible degradation;
- the same safety, secret, trust, capability, and confirmation contracts as Lite.

Mocks and CI may support development but cannot satisfy real-hardware Heavy release gates.

## 15. Soak and continuity or safety drills

### Lite release candidate soak

Target: at least seven days of ordinary personal use.

Record:

- startups and restarts;
- model switches;
- document and artifact work;
- claim and evidence review;
- capability approvals and denials;
- backups;
- at least one restore drill;
- offline use;
- secret-store unavailable or locked behavior;
- observed state, security, trust, or audit defects;
- disk growth;
- known crashes.

### Periodic continuity drill

A continuity-ready installation should periodically test:

1. disconnect network;
2. remove or disable cloud credentials;
3. start through CLI or local API without the preferred UI;
4. inspect confirmed memory and a project without a model;
5. verify a backup;
6. restore to a separate empty location;
7. validate the restored workspace in a fresh process;
8. after Phase 4, use a local model and switch to fallback;
9. confirm unrelated authoritative state remains unchanged.

### Periodic safety drill

A safety-ready installation should periodically test:

1. lock or deny the external secret store;
2. submit hostile external-content fixtures;
3. attempt an unknown and malformed capability;
4. attempt a risk-tier downgrade;
5. attempt a high-risk operation without confirmation;
6. approve one exact synthetic high-risk operation;
7. change a material argument and verify confirmation invalidation;
8. inspect redacted audit and diagnostic output;
9. confirm the last known good state remains intact.

## 16. Release acceptance report

A release acceptance report must include:

- release and commit;
- scope;
- support matrix;
- blocking test totals;
- failed, blocked, or waived advisory tests;
- real-machine environments;
- model and runtime manifests used where applicable;
- continuity, backup, and restore evidence;
- safety-gate evidence;
- secret-store and credential-broker evidence where applicable;
- offline evidence;
- security test summary;
- known limitations;
- soak result;
- release decision.

## 17. Acceptance criteria

This test specification is accepted when:

- every phase and release claim maps to stable test IDs;
- continuity includes loss and recovery, not normal startup only;
- Phase 2 continuity is provable without model execution;
- the complete safety gate precedes model execution;
- CI, fresh-process, and real-machine evidence remain distinct;
- backup creation does not substitute for restore;
- model replacement includes rollback and state-integrity evidence;
- security tests verify denied and hostile actions as well as allowed actions;
- secret values remain separate from ordinary state and model context;
- claims, evidence, inferences, and confirmed facts remain distinct;
- instruction origin remains enforceable through context assembly;
- high-risk confirmation is exact, fresh, and insufficient to override policy;
- experimental features cannot silently count toward stable gates;
- Lite and Heavy use the same core continuity and safety evidence;
- release reports expose failures and limitations rather than hiding them.
<!-- END SOURCE: docs/spec/08-acceptance-and-continuity-tests.md -->

---

<!-- BEGIN SOURCE: docs/spec/09-development-roadmap.md -->
# Development roadmap

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This roadmap converts the accepted product, continuity, and security specifications into an implementation sequence.

It is a sequencing document, not a promise of exact dates or pull-request counts.

The governing rule is:

> Prove user-owned continuity first, complete the model-independent safety boundary second, then add model execution and useful capabilities without weakening either pillar.

## 2. Working method

Development proceeds through small, reviewable pull requests.

Each implementation PR must:

- solve one bounded issue;
- cite the accepted specification it implements;
- describe state, permission, secret, trust, network, and migration effects;
- include tests for success and denial or failure paths;
- avoid unrelated refactoring;
- distinguish CI evidence from real-machine evidence;
- preserve a working and recoverable `main` branch;
- avoid private data, credentials, secret values, personal paths, usernames, hostnames, and home-directory details.

The normal unit of work is:

```text
1 Issue → 1 Branch → 1 Pull Request
```

The intended division of work is:

- GPT: architecture, specification, task decomposition, review, and release-gate checking;
- Codex or equivalent implementation assistance: code, tests, migrations, documentation updates, and PR preparation;
- project owner: priorities, real-machine validation, final merge, release, license, and hardware decisions.

## 3. Governing implementation order

Doll has two co-equal architectural pillars:

1. continuity of user-owned state;
2. a model-independent safety boundary.

The implementation phases are:

```text
Phase 0  Specification and principles
Phase 1  Local state foundation
Phase 2  Continuity, transfer, backup, and restore
Phase 3  Safety boundary
Phase 4  Local AI
Phase 5  Cloud and multiple models
Phase 6  Tools and external services
Phase 7  Daily use
Phase 8  Distribution, encryption, and long-term operation
```

No model adapter, inference request, conversation runtime, or model-initiated capability path may merge before the Phase 3 safety gate passes.

## 4. Current state

Completed:

- Phase 0 specification baseline;
- IMP-001 through IMP-010;
- local workspace, SQLite state, migrations, audit, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, and verified backup creation.

Current implementation point:

- Phase 2;
- IMP-011 is the next code issue;
- IMP-011 adds backup restore and post-restore validation;
- IMP-012 will run the model-independent Continuity Acceptance Test;
- IMP-013 through IMP-023 implement and validate the safety boundary;
- local model execution begins at IMP-024 or later.

## 5. Phase 0 — Specification and principles

Goal: define product identity, continuity, state ownership, security, release evidence, and implementation order before production features.

Status: complete, subject to controlled specification changes.

Completed specification work includes:

- product identity and Continuity Contract;
- local-complete, cloud-optional architecture;
- Doll State and storage model;
- default-deny permissions and trust boundaries;
- Model Vault direction;
- platform and recovery direction;
- release scope and acceptance evidence;
- deterministic `DOLL_FINAL_SPEC.md` generation;
- ADR-005 sequencing the safety boundary before model execution.

No implementation PR may silently contradict this baseline.

## 6. Phase 1 — Local state foundation

Goal: establish a cross-platform package, private workspace, versioned authoritative state, explicit user control, and safe writes without any model dependency.

Status: complete through IMP-008.

### IMP-001 — Python package and CI skeleton

Implemented:

- Python package metadata;
- `uv` lock and development commands;
- `src/doll/` package;
- Typer CLI entry point;
- FastAPI application factory;
- pytest, lint, type-check, and coverage configuration;
- macOS, Windows, and Ubuntu CI;
- no model or external tool dependency.

### IMP-002 — Platform paths and workspace initialization

Implemented:

- platform-aware data locations;
- `doll init`;
- WorkspaceRecord;
- repository-checkout protection;
- path canonicalization;
- synthetic and Unicode fixtures.

### IMP-003 — SQLite state repository and migrations

Implemented:

- schema versioning;
- common record envelope;
- migration runner;
- transactions and revisions;
- read-only recovery opening path.

### IMP-004 — Append-oriented audit service

Implemented:

- operation IDs;
- actor and result records;
- secret-safe summaries;
- audit listing;
- append-oriented persistence.

### IMP-005 — Workspace file service

Implemented:

- managed artifact paths;
- create-new semantics;
- content hashing;
- atomic writes;
- traversal and link-escape defenses;
- size limits.

### IMP-006 — Preferences, policies, and permissions

Implemented:

- PreferenceRecord;
- PolicyRecord;
- PermissionRecord;
- denied, allow-once, ask, and scoped modes;
- no global allow-all;
- explicit management path;
- model or content text cannot count as approval.

### IMP-007 — Confirmed memory

Implemented:

- confirmed MemoryRecord management;
- provenance and sensitivity;
- archive and export;
- no automatic conversation-to-memory conversion.

### IMP-008 — Projects and decisions

Implemented:

- ProjectRecord;
- DecisionRecord;
- typed links;
- revision-safe updates;
- archive and export.

## 7. Phase 2 — Continuity, transfer, backup, and restore

Goal: make durable state inspectable, transferable, restorable, and verifiable without a model, runtime, network connection, cloud account, or preferred UI.

### IMP-009 — Doll State package export and import

Status: complete.

Implemented:

- versioned package manifest;
- JSON and JSONL records;
- checksums;
- staged validation;
- conflict reporting;
- empty-target import;
- no package-content execution.

Acceptance focus:

- STATE-003;
- STATE-004;
- STATE-008.

### IMP-010 — Backup creation and verification

Status: complete.

Implemented:

- state backup;
- workspace backup;
- SQLite snapshot;
- artifact-byte preservation;
- manifest and SHA-256 verification;
- tamper detection;
- atomic no-clobber publication;
- secret-containing unencrypted workspace-backup rejection;
- backup inventory and audit.

Acceptance focus:

- CONT-P010;
- STATE-007 foundation;
- cross-platform backup safety.

### IMP-011 — Backup restore and post-restore validation

Status: next code implementation.

Required scope:

- state-backup restore into an empty target;
- workspace-backup restore into an empty target;
- complete verification before extraction;
- staging outside the final target;
- safe path and member validation;
- SQLite integrity validation;
- workspace identity and revision validation;
- record and typed-link validation;
- artifact hash and byte validation;
- atomic publication without overwrite;
- cleanup of staging and partial output on failure;
- fresh-process post-restore validation;
- normal output without absolute local path disclosure;
- no model execution and no network access.

Acceptance focus:

- CONT-P011;
- CONT-P012;
- STATE-007;
- STATE-008;
- PLAT-005;
- PLAT-007.

### IMP-012 — Continuity Acceptance Test

Goal: prove the complete Phase 1 and Phase 2 continuity foundation before any safety-boundary or model work depends on it.

Required evidence:

- clean workspace creation;
- confirmed memory, preferences, policies, permissions, projects, decisions, typed links, audit history, and artifacts persist across process restart;
- Doll State export and import preserve implemented authoritative records;
- state backup restores into an empty target;
- workspace backup restores into an empty target;
- restored workspace identity, schema, revision, records, links, audit history, and artifact bytes match the verified source contract;
- corrupt, tampered, unsafe, mismatched, existing, or non-empty targets fail closed;
- a fresh process validates and inspects restored state without a model;
- no cloud credentials or network access are required;
- no absolute path, username, hostname, home-directory detail, secret, or personal fixture appears in shareable output;
- CI passes on macOS, Windows, and Ubuntu;
- the complete drill passes on the primary Intel Mac.

Phase 2 gate:

- IMP-011 is merged;
- required continuity and state tests pass;
- the real-machine continuity report records the tested commit and limitations;
- restore failure does not damage the last known good workspace;
- no model execution path exists.

## 8. Phase 3 — Safety boundary

Goal: implement the authority, secret, trust, instruction, capability, and confirmation boundary before any model is allowed to execute.

The safety boundary is model-independent. Tests use synthetic callers, hostile fixtures, malformed requests, and explicit management commands rather than a live model.

### IMP-013 — Secret Classification Policy

Define:

- secret classes and sensitivity levels;
- ordinary-state prohibition for secret values;
- SecretReference requirements;
- allowed metadata and prohibited value fields;
- input, output, persistence, export, backup, and diagnostic handling;
- fail-closed behavior for uncertain secret-bearing operations.

### IMP-014 — Secret Detection and Redaction

Implement:

- bounded best-effort detectors;
- structured redaction results;
- false-positive and false-negative documentation;
- redaction for user-visible errors and diagnostics;
- no broad secret-search permission;
- tests for common credential, token, key, cookie, recovery phrase, and personal-data patterns using synthetic fixtures only.

### IMP-015 — Secret-Safe Audit and Logging

Implement:

- centrally enforced audit and log sanitization;
- structured safe summaries;
- rejection or redaction of secret-bearing fields;
- path, username, hostname, and home-directory minimization;
- tests proving allowed, denied, failed, and exceptional operations do not leak secret values.

### IMP-016 — External Secret Store Contract

Define a portable contract for operating-system or compatible external secret stores:

- reference creation and lookup metadata;
- availability and locked-state reporting;
- user-presence requirements;
- create, replace, revoke, and delete semantics;
- no ordinary-state secret-value persistence;
- platform-specific adapters remain replaceable;
- unavailable secret storage cannot block non-secret core startup.

### IMP-017 — Credential Broker

Implement a narrow broker that:

- accepts SecretReference, capability, destination, scope, and operation metadata;
- obtains required user approval or presence;
- uses a credential only inside the bounded operation;
- does not return the stored secret value to a model or ordinary caller by default;
- returns a structured operation result;
- redacts errors and audit events;
- supports cancellation, timeout, and fail-closed behavior.

### IMP-018 — Claim, Evidence, and Trust Model

Implement distinct records and links for:

- confirmed facts;
- claims;
- supporting or contradicting evidence;
- inferences;
- provenance, source, confidence, uncertainty, and review status.

Required rule:

- model, tool, document, website, import, or runtime assertions do not become confirmed facts automatically.

### IMP-019 — Instruction Origin and Untrusted-Content Boundary

Implement:

- instruction-origin metadata;
- authority classes;
- immutable source attribution for imported and retrieved content;
- separation of system policy, user instruction, durable policy, content, tool result, and model proposal;
- content cannot grant permission, confirmation, or policy changes;
- unknown origin fails to the least-authoritative classification.

### IMP-020 — Prompt Injection Defense

Implement defense in depth:

- context packaging that preserves origin and authority;
- prompt-injection indicators and warnings;
- unrelated-capability and exfiltration-request detection;
- policy and permission enforcement outside the model;
- hostile document, website, metadata, OCR, transcript, and tool-result fixtures;
- no reliance on model classification as the authorization boundary.

### IMP-021 — Capability Taxonomy and Risk Tiers

Implement:

- versioned capability registry;
- input and output schemas;
- declared targets, side effects, and resource limits;
- permission and network checks;
- risk tiers;
- unknown or malformed capability denial;
- no unrestricted shell or arbitrary command-string capability;
- allow and deny audit events.

Initial risk direction:

- Tier 0: pure computation with no side effect;
- Tier 1: bounded managed read or reversible creation;
- Tier 2: scoped modification or explicit external read;
- Tier 3: destructive, externally visible, credential-bearing, account-affecting, or process-execution action;
- Prohibited: actions outside accepted release scope regardless of confirmation.

### IMP-022 — Mandatory High-Risk Confirmation

Implement:

- trusted user-controlled confirmation channel;
- fresh confirmation for every Tier 3 operation;
- exact capability, target, destination, side-effect, and credential-class preview;
- expiry and one-operation binding;
- material-change invalidation;
- no confirmation from model text, documents, websites, imports, or tool results;
- no persistent broad confirmation for high-risk operations;
- confirmation does not override policy or make a prohibited capability available.

### IMP-023 — Safety Acceptance Test

Goal: prove the complete safety boundary before model execution.

Required evidence includes:

- secret values are absent from ordinary state, logs, audit, exports, backups, fixtures, diagnostics, and model-context packages;
- SecretReference remains non-secret and portable;
- credential-broker tests complete bounded synthetic operations without exposing stored values;
- confirmed facts, claims, evidence, and inferences remain distinct through restart and export;
- instruction origin and authority survive persistence and context assembly;
- hostile content cannot grant approval, alter policy, raise authority, or trigger a capability;
- unknown and malformed capabilities fail closed;
- risk tiers are enforced;
- high-risk operations fail without fresh exact confirmation;
- changed targets, arguments, destinations, side effects, or credential classes invalidate confirmation;
- denial and failure preserve the last known good state;
- security-relevant events are auditable without leaking sensitive data;
- CI passes on macOS, Windows, and Ubuntu;
- applicable real-process checks pass on the primary Intel Mac.

Phase 3 gate:

- IMP-013 through IMP-023 are merged;
- all blocking safety tests pass;
- open known limitations are documented;
- no accepted review finding shows a route around the boundary;
- only after this gate may IMP-024 introduce a model adapter contract.

## 9. Phase 4 — Local AI

Goal: connect useful local inference without allowing the runtime or model to own state, secrets, permissions, trust decisions, or side effects.

Expected sequence begins at IMP-024.

### IMP-024 — Runtime adapter contract

- normalized health, inventory, generation, streaming, cancellation, and error contracts;
- runtime-independent model IDs;
- no direct state, secret-store, filesystem, network, or capability access;
- mocked adapter tests.

### IMP-025 — First local runtime adapter

Initial target: Ollama.

- local health check;
- installed model inventory mapping;
- local generation and streaming;
- timeout and cancellation;
- no silent model download;
- no cloud fallback;
- all context passes through accepted origin and secret controls.

### IMP-026 — Model manifests and bindings

- ModelManifestRecord;
- RuntimeManifestRecord;
- ModelBindingRecord;
- source, revision, checksum, license, and compatibility;
- quarantine, candidate, active, previous, fallback, and rollback state.

### IMP-027 — Local conversation path

- local API and CLI conversation;
- scoped state retrieval;
- response provenance;
- no automatic durable memory creation;
- no direct model capability execution;
- model proposals pass through the safety boundary.

### IMP-028 — Model switch and local fallback

- explicit activation;
- previous binding retention;
- fallback selection or offer;
- rollback after failed smoke test;
- no unrelated state rewrite;
- no cloud request.

### IMP-029 — Offline mode and local AI continuity drill

- network-disabled startup;
- outbound-request guard;
- local conversation and fallback offline;
- model replacement without state loss;
- primary-machine continuity evidence.

Phase 4 gate:

- local inference remains optional to state inspection, export, backup, restore, and recovery;
- model replacement does not rewrite unrelated state;
- the safety boundary remains the only route to side effects;
- no cloud credential is required.

## 10. Phase 5 — Cloud and multiple models

Goal: add optional performance and role expansion without making cloud access authoritative or mandatory.

Cloud work begins only after the local path and safety boundary are stable.

Expected slices:

1. generic bounded outbound-package contract;
2. exact preview, minimization, and redaction;
3. provider-independent cloud adapter interface;
4. one optional OpenAI-compatible adapter;
5. multiple local-model role routing;
6. local/cloud selection policy with no automatic cloud fallback;
7. cost, retention, destination, and audit reporting where available;
8. provider-specific adapters only when justified.

Cloud code must remain removable. Removing cloud adapters must not prevent local startup, state access, restore, or local inference.

## 11. Phase 6 — Tools and external services

Goal: add useful capabilities through the accepted Capability Broker rather than direct model authority.

Candidate groups:

- approved local document read;
- artifact versioning and export;
- local full-text search;
- safe URL retrieval and Web research;
- PDF extraction;
- OCR;
- CSV inspection and transformation;
- image, audio, and video adapters;
- optional speech-to-text;
- narrowly scoped external-service integrations.

Every adapter must:

- declare capability ID, version, risk tier, inputs, outputs, side effects, limits, and provenance;
- fail independently;
- avoid unrestricted shell execution;
- preserve instruction origin for returned content;
- use the credential broker when a credential is required;
- remain visible through doctor and audit;
- keep experimental features outside stable release claims.

## 12. Phase 7 — Daily use

Goal: make the continuity and safety foundations useful for ordinary personal work.

Candidate work:

- writing and editing;
- summarization and translation;
- planning and research workflows;
- memory review and confirmation flows;
- project and decision workflows;
- backup and restore usability;
- source, claim, evidence, and inference inspection;
- capability and confirmation usability;
- optional Open WebUI compatibility;
- accessibility and error clarity;
- performance measurement on Lite hardware;
- seven-day primary-machine soak before a Lite stable claim.

Daily-use convenience must not hide model, network, credential, permission, or risk state.

## 13. Phase 8 — Distribution, encryption, and long-term operation

Goal: make doll maintainable, recoverable, and distributable over long periods without splitting the core.

Candidate groups:

- installer and package paths;
- signed or verifiable releases where feasible;
- offline recovery kit;
- update staging and rollback;
- standard backup encryption;
- backup rotation and retention;
- long-term schema migration drills;
- support matrix and shareable doctor reports;
- Lite and Heavy profile measurement;
- Heavy hardware selection only after Lite evidence;
- richer retrieval, media, verification, and training workflows;
- mobile companion or remote access only after a separate threat model;
- multi-device synchronization only after conflict and secret-boundary design;
- periodic continuity and safety drills;
- community verification and release acceptance reports.

The project must not invent custom cryptography. Encryption work must use established operating-system or library primitives and must not make unencrypted recovery impossible without an explicit accepted product decision.

## 14. Issue and PR discipline

Implementation issues should contain:

- objective;
- accepted specification links;
- in-scope and out-of-scope behavior;
- state and schema changes;
- secret and credential effects;
- trust, evidence, and instruction-origin effects;
- permission, capability, risk, and confirmation effects;
- network and process effects;
- migration requirements;
- test IDs;
- real-machine work required;
- rollback or failure-preservation plan.

A PR should normally implement one issue or one tightly related slice.

Documentation-only sequencing changes must not include implementation code.

## 15. Definition of done for an implementation PR

An implementation PR is done when:

- code matches the accepted boundary;
- tests pass on applicable CI platforms;
- success, denial, malformed input, and recoverable failure are tested;
- security and path failures are tested;
- persisted-state changes include schema and migration handling;
- secret-bearing paths are classified and tested;
- audit and user-visible output are checked for leakage;
- documentation is updated;
- no private or secret fixture is committed;
- coverage does not fall below the accepted threshold;
- blanket coverage exclusions are not used to hide untested logic;
- optional dependencies fail cleanly;
- PR description states real-hardware gaps;
- review comments are resolved;
- `main` remains recoverable.

## 16. Immediate work

The required order from the current repository state is:

1. merge the documentation change adopting ADR-005 and this roadmap;
2. return to `impl/imp-011-restore-post-validation`;
3. rebase that branch onto the updated `main`;
4. implement IMP-011 only;
5. pass CI, review, and Intel Mac real-process restore validation;
6. squash-merge IMP-011;
7. implement IMP-012 as the Continuity Acceptance Test;
8. begin IMP-013 only after the Phase 2 gate passes;
9. complete IMP-013 through IMP-023;
10. begin model work at IMP-024 or later only after the Phase 3 gate passes.

## 17. Roadmap change control

The roadmap may change as implementation evidence arrives.

Changes must preserve:

- continuity-first sequencing;
- the safety boundary before model execution;
- local completion before cloud dependence;
- memory and secret separation;
- external content as data rather than authority;
- model-independent permissions, risk, and confirmation;
- Lite evidence before Heavy hardware commitment;
- test evidence before phase or release claims;
- small PRs;
- explicit migration, rollback, and recoverable failure;
- the project owner's immediate personal-use objective.

A change that moves model execution before the Phase 3 safety gate requires a new accepted architecture decision and corresponding security and acceptance-test changes.
<!-- END SOURCE: docs/spec/09-development-roadmap.md -->
