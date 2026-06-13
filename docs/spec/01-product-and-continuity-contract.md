# Product definition and Continuity Contract

**Status:** Draft for acceptance  
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
