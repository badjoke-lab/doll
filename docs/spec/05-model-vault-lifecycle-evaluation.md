# Model Vault, lifecycle, evaluation, and improvement

**Status:** Draft for acceptance  
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
