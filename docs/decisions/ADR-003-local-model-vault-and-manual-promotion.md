# ADR-003: Local Model Vault and manual promotion

**Status:** Accepted  
**Date:** 2026-06-14

## Context

Doll is intended to remain usable when cloud providers, model distribution sites, runtimes, or preferred models become unavailable.

Using only mutable runtime tags, remote catalogs, or automatically updated models would make the system dependent on external services and would allow untested changes to replace a stable local environment.

The project therefore needs an explicit model ownership and lifecycle policy.

## Decision

Doll will maintain a local Model Vault containing user-retained model assets and model-independent metadata.

Every deployable model variant must be represented by a versioned ModelManifestRecord containing, at minimum:

- developer or organization;
- source and exact revision;
- license record;
- file inventory;
- checksums;
- format and quantization;
- runtime compatibility;
- validation state;
- evaluation references.

Runtime aliases such as Ollama tags are adapter metadata, not authoritative model identities.

New model assets enter quarantine and may move through:

```text
discovered
  -> approved_for_download
  -> downloading
  -> quarantined
  -> validated
  -> candidate
  -> active
```

Stable continuity states are:

- active;
- previous;
- fallback.

A model cannot promote or activate itself.

Activation requires:

- verified assets;
- known runtime binding;
- required evaluation threshold;
- explicit user approval;
- retention of the previous known-good binding;
- post-activation smoke test;
- automatic rollback on activation failure.

Automatic cloud fallback is not part of model degradation.

## Consequences

### Positive

- Retained models remain usable when a distribution source disappears.
- Model identity survives runtime replacement.
- Unverified downloads cannot replace a stable model.
- Rollback is explicit and testable.
- Lite and Heavy use one lifecycle model.
- User-specific evaluations can determine usefulness rather than relying only on public benchmarks.
- Locally fine-tuned models enter the same controlled candidate path.

### Negative

- Model storage may consume substantial disk space.
- Checksums, licenses, evaluations, and runtime mappings require maintenance.
- The user must review acquisition and promotion decisions.
- Some convenient auto-update behavior is intentionally rejected.
- Runtime-specific catalogs need translation into doll manifests.
- Exact offline reproduction may be limited by platform and third-party license constraints.

## Rejected alternatives

### Use only Ollama or runtime tags

Rejected because tags may be mutable, runtime-specific, and insufficient for provenance, license, checksum, and evaluation history.

### Always use the newest available model

Rejected because newer models may regress, require more hardware, change licenses, fail offline, or behave differently with memory and tools.

### Automatically replace the active model after evaluation

Rejected because evaluation can be incomplete and the user must understand performance, resource, license, and behavior trade-offs.

### Keep only one model to minimize disk use

Rejected as the default because it removes rollback and emergency fallback. Users may accept this continuity gap explicitly.

### Treat cloud models as the emergency fallback

Rejected because cloud loss is one of the core threats doll is designed to survive.

### Automatically train on daily conversations

Rejected because of privacy, data quality, consent, poisoning, catastrophic forgetting, and reproducibility risks.

## Implementation constraints

- Model files are never committed to the public repository.
- Manual local-file import must exist eventually.
- Downloads are staged and cannot be activated partially.
- Checksum failure blocks validation.
- Remote-code requirements are recorded and excluded from the standard validated path.
- Promotion and rollback create audit events.
- Model cleanup shows continuity consequences and requires user approval.
- Offline verification is a recorded environment-specific result.
- Training output is a candidate model, never an automatic active replacement.

## Validation

This decision is validated when tests demonstrate that:

1. a mutable runtime alias does not define model identity;
2. imported assets enter quarantine;
3. checksum failure blocks loading or activation;
4. a candidate cannot self-promote;
5. activation retains a previous binding;
6. failed smoke testing restores the previous binding;
7. fallback remains local and does not invoke cloud services;
8. Doll State is unchanged by model replacement;
9. a verified local asset remains usable when its source is unreachable;
10. locally trained output enters the candidate lifecycle.
