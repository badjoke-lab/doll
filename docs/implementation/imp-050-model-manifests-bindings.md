# IMP-050 — Model manifests and explicit runtime bindings

## Status

Implemented as the authoritative Phase 5 configuration foundation above the IMP-048 runtime contract and the IMP-049 Ollama adapter.

IMP-050 records what local runtime and exact local model artifact may be used, how that decision was reviewed, and which explicit binding is active, previous, fallback, disabled, or rolled back. It does not install a runtime, download a model, call Ollama, execute inference, or claim real-machine local AI operation.

## Record types

### RuntimeManifestRecord v1

`runtime_manifest` records contain:

- a stable Doll record identity and human label;
- adapter identity and version;
- runtime class and connection kind;
- optional runtime version;
- a deterministic declaration fingerprint;
- supported runtime operations;
- explicit offline-capable, cloud-fallback, and automatic-download declarations;
- platform and compatibility declarations;
- source references;
- lifecycle state, verification evidence, and quarantine reason.

A runtime manifest is an authoritative user-controlled declaration. Runtime discovery and provider-native inventory remain observations and do not create or verify one automatically.

### ModelManifestRecord v1

`model_manifest` records contain:

- a stable Doll record identity;
- a reference to one runtime manifest;
- a bounded runtime-private locator used only to find the artifact;
- display name;
- exact revision;
- named checksums;
- source and provenance references;
- declared license identifier and review state;
- model format, optional size, optional context limit, descriptive capabilities, platforms, and compatibility;
- lifecycle state, verification evidence, and quarantine reason.

The Doll identity is independent of an Ollama or other provider-native model identifier. Exact revision and checksum identity cannot be silently rewritten after verification.

### ModelBindingRecord v1

`model_binding` records contain:

- a stable Doll binding identity;
- scope type and scope key;
- exact runtime and model manifest identities and revisions;
- candidate, active, previous, fallback, disabled, or rolled-back state;
- activation time and evidence;
- previous binding linkage;
- fallback priority and eligibility;
- rollback target and reason;
- smoke-test status.

A binding is configuration state only. Activating one does not execute a model or grant a capability.

## Lifecycle and authority

Runtime and model manifests begin as candidates. User-controlled protected transitions may verify a runtime, review a model license, verify a model, activate a binding, make a binding fallback-eligible, disable a binding, or roll a scope back.

Model, runtime, importer, and untrusted external provenance cannot automatically:

- verify a manifest;
- approve a license;
- activate a binding;
- make a binding fallback-eligible;
- choose a rollback target;
- execute a model or capability.

System provenance may quarantine or mark a manifest unavailable, but cannot perform the user-only approval and activation transitions.

Verification requires a local-only runtime declaration. Model verification requires a verified active runtime, accepted license-review state, exact revision and checksums, and compatible platform declarations. Quarantined, deprecated, unavailable, archived, stale, mismatched, or incompatible records cannot be activated.

## Activation, previous, fallback, and rollback

Only one active binding may exist for a scope key. Activation is transactional:

1. the candidate binding and both exact manifest revisions are revalidated;
2. a previously active binding in the same scope is retained as `previous`;
3. the selected binding becomes `active` with explicit evidence;
4. unrelated scopes and records are not rewritten.

Fallback state is explicit and user-controlled. It requires a passed smoke test and valid verified manifests. Fallback priority is stored deterministically; no automatic failover execution is introduced here.

Rollback is scope-local and transactional. The selected previous binding is revalidated, the current active binding becomes `rolled_back`, and the rollback target becomes active. A failed transition leaves the prior state unchanged.

## State and migration effects

IMP-050 advances the SQLite schema to version 3 and adds expression indexes for manifest state, runtime/model references, binding scope and state, and the one-active-binding-per-scope invariant.

The new records use the existing authoritative `records` table, state revisions, optimistic revision checks, transaction boundaries, and audit history. No provider-native database or runtime-owned state becomes canonical.

## State Package and recovery effects

State Package format v2 gains three optional typed categories:

- `records/runtime-manifests.jsonl`;
- `records/model-manifests.jsonl`;
- `records/model-bindings.jsonl`.

Typed validators reject malformed metadata, duplicate or missing references, wrong runtime/model relationships, invalid previous or rollback references, and missing evidence references. Deterministic ordering is preserved.

Package v1 remains unchanged and readable. The optional-record mechanism is sufficient, so no package-format version increase is required.

Because the records remain in canonical state, existing state backup and restore include them without a new backup format. Tests cover backup round trip and fresh-process inspection with no runtime, model, provider, cloud account, preferred UI, or network route.

## Security, privacy, and secret effects

Manifest and binding metadata are bounded and validated. Runtime-private locators reject URLs, credentials, user-qualified values, query or fragment data, and private absolute paths. Errors and audit metadata do not expose provider response bodies or exception text.

The records grant no access to:

- secrets or credentials;
- files or directories;
- network routes;
- capability or permission brokers;
- project progress or checkpoint authority;
- automatic durable memory;
- side effects.

Model capabilities are descriptive metadata only. License review records a user decision and is not legal advice or an inferred legal approval.

## Validation

Tests cover:

- all three record schemas and corrupt-record rejection;
- migration 0003 and indexes;
- provenance and protected actor restrictions;
- local-only runtime verification;
- exact revision, checksum, license, compatibility, verification, quarantine, deprecation, and unavailable gates;
- immutable verified artifact identity;
- candidate, active, previous, fallback, disabled, and rolled-back transitions;
- one active binding per scope;
- deterministic scope-local rollback;
- stale revision and transaction preservation;
- State Package v2 round trip and package-v1 neutrality;
- state backup and fresh-process validation without a runtime;
- secret-safe locator and failure validation;
- Linux, macOS, and Windows CI.

## Deliberate limitations

IMP-050 does not:

- install, start, stop, update, or configure a runtime;
- download, copy, delete, or convert a model;
- make a real Ollama request;
- execute canonical conversation;
- select a model automatically;
- execute fallback automatically;
- grant a tool or capability;
- add cloud credentials or providers;
- prove real-machine inference.

## Next slice

The next bounded Phase 5 slice is canonical local conversation through the IMP-048 contract and the accepted Phase 3 safety boundary. It receives IMP-051 when opened.

## Issue

Closes #156.
