# Release scope and execution profiles

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This document defines what each release must prove and separates the first continuity proof, Lite, Heavy, cloud, and mobile work.

The release sequence is:

```text
Specification baseline
  -> model-independent continuity proof
  -> model-independent safety-boundary proof
  -> local AI proof
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
- one secret-reference and Credential Broker contract;
- compatible backup and recovery formats;
- one audit model;
- model-independent memory, project, source, claim, evidence, inference, and artifact records;
- one instruction-origin and untrusted-content boundary;
- one capability risk-tier and high-risk confirmation model;
- local-first startup;
- no mandatory cloud account;
- no automatic cloud fallback;
- no unrestricted shell in stable scope.

Heavy may add capabilities but must not create a second incompatible core.

## 3. Personal continuity and safety proofs

The first implementation milestones are proofs for one user and one machine. They are deliberately split so continuity and the safety boundary are established before model execution.

### 3.1 Model-independent continuity proof

It must demonstrate:

1. initialize a private workspace outside the repository;
2. create and inspect workspace identity and schema version;
3. start without cloud credentials, network access, or a model runtime;
4. create and retrieve confirmed memory;
5. create and retrieve a project or decision record;
6. create and verify a Doll State package;
7. import the package into an empty compatible target;
8. create and verify state and workspace backups;
9. restore both supported backup kinds into empty compatible targets;
10. validate restored identity, revision, records, links, audit history, and artifact bytes in a fresh process;
11. preserve the last known good state when import or restore fails;
12. refuse unsafe archive paths and writes outside the workspace;
13. create audit records for continuity and denial operations.

This proof does not require or permit a model execution path.

### 3.2 Model-independent safety-boundary proof

Before a local model adapter may merge, accepted tests must demonstrate:

1. ordinary Doll State retains only non-secret credential references;
2. secret values are absent from logs, audit, exports, backups, fixtures, diagnostics, and model-context packages;
3. the Credential Broker performs bounded synthetic operations without disclosing stored values;
4. confirmed facts, claims, evidence, and inferences remain distinct;
5. instruction origin and authority survive persistence and context assembly;
6. hostile content cannot grant permission, confirmation, or capability authority;
7. unknown, malformed, risk-downgraded, or under-confirmed capability requests fail closed;
8. high-risk confirmation is fresh, exact, user-controlled, and invalidated by material changes.

### 3.3 First local AI proof

Only after the safety-boundary proof passes, accepted tests must demonstrate:

1. connect to one local model through a replaceable adapter;
2. perform basic local conversation offline;
3. keep model context within secret, trust, origin, and permission policy;
4. prevent direct model side effects;
5. switch to another approved local model without deleting Doll State;
6. disable every model adapter without losing state inspection, export, backup, restore, or recovery.

These proofs do not require Web research, PDF, OCR, audio, video, cloud, mobile, avatars, Heavy hardware, automatic model acquisition, or public installer quality.

Passing them validates the named architecture gates only. It does not mean the product is ready for general users.

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
- use the accepted external secret-store and Credential Broker boundary without exposing stored values to models;
- preserve instruction origin for returned content;
- create secret-safe audit records.

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

Any future addition requires a separate threat model, versioned capability contract, risk tier, exact confirmation design, credential boundary where applicable, and acceptance suite. Confirmation cannot make a prohibited capability available.

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

- the model-independent continuity proof is smaller than Lite v1.0;
- the complete safety-boundary proof precedes the local AI proof;
- Lite and Heavy share one core, secret, trust, instruction, capability, and confirmation boundary;
- Lite v1.0 has a testable boundary;
- Heavy completion requires real hardware;
- cloud and mobile cannot become hidden local dependencies;
- personality and avatar features remain optional;
- dangerous autonomy remains outside initial stable scope;
- public claims map to release evidence;
- later features cannot bypass the Continuity Contract.
