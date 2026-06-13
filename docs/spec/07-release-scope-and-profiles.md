# Release scope and execution profiles

**Status:** Draft for acceptance  
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
