# IMP-102 — Lite installation and model-storage measurement preparation

Status: implementation for Issue #322.

## Purpose

IMP-102 adds the next bounded measurement path identified by the conservative IMP-097 performance interpretation: a privacy-safe primary Intel Mac observation of one fresh Lite Python installation plus one already-installed local model's provider-reported storage.

This slice prepares collection and validation only. It does not accept physical evidence and does not define a Lite disk requirement.

## Lite installation boundary

The real-machine runner creates one temporary Python environment from the exact clean tracked checkout with:

- the locked dependency graph;
- development dependencies disabled;
- all currently supported Lite optional extras enabled (`pdf` and `ocr`);
- editable installation disabled;
- uv offline mode required;
- no package-network fallback.

The runner verifies that doll, pypdf, and ocrmac are importable from the fresh environment and that pytest, Ruff, and mypy are absent. Missing cached dependency material fails the measurement rather than weakening the requested Lite profile or enabling network access.

The environment is deleted before a successful result is emitted.

## Storage accounting

The runner measures bounded filesystem aggregates only. It records:

- regular-file count;
- directory count;
- symlink count;
- other-entry count;
- logical regular-file bytes;
- allocated bytes from `st_blocks * 512` where available;
- whether symlink-target bytes were included, which is fixed to `false`.

Traversal does not follow symlinks and is bounded by entry and byte limits. The primary Intel Mac evidence validator requires positive allocated-byte observations in addition to logical bytes.

These values describe the measured temporary environment. They are not automatically the size of a future installer, package-manager cache, Python distribution, operating-system frameworks, user workspace, or complete local AI stack.

## Local runtime and model boundary

The runner reuses the existing fixed IPv4 loopback Ollama transport and local-only adapter boundary. One caller-selected already-installed non-cloud model is resolved through the local inventory.

The shareable observation records only:

- the local runtime version;
- an opaque Doll-facing model ID;
- exact model revision digest;
- provider-reported installed model size bytes.

The native model name is never serialized. The runner does not install, pull, update, start, stop, or remove runtime/model assets.

An operator may optionally supply one explicit runtime installation root. If supplied, only aggregate tree measurements are emitted. The path and member names are not serialized. If it is omitted, the result records `runtime_installation.measured = false` and cannot be treated as a complete local-stack disk footprint.

## CI boundary

CI mode is deterministic synthetic evidence only. It performs no temporary package installation, no Ollama access, no runtime inspection, no external filesystem traversal, no process inspection, and no network request.

CI proves the evidence schema, fail-closed validation, command policy, and claim/privacy boundaries. It does not replace the required physical primary Intel Mac collection.

## Validator

`scripts/validate_imp_102_lite_install_storage_measurement.py` accepts only real-machine evidence bound to the exact expected commit. It requires:

- Darwin Intel primary-machine class;
- offline-confirmed measurement;
- the exact Lite no-dev/all-extras installation profile;
- positive logical and allocated installation bytes;
- successful import/absence checks for required and development dependencies;
- fixed-loopback runtime inspection;
- opaque model identity, exact revision, and positive provider-reported model bytes;
- an explicit measured/unmeasured runtime-installation shape;
- all measurement checks true;
- every privacy flag false;
- every broader disk/performance/release claim false.

It recursively rejects path, filename, native-model-name, process, host/user, credential/secret, URL, and email keys from shareable evidence.

A passing validator still leaves `real_machine_measurement_accepted = false` and requires manual privacy review before repository acceptance.

## Non-claims

IMP-102 does not define or prove:

- a final minimum disk requirement;
- a full Lite installation disk requirement;
- a minimum RAM requirement;
- total-system peak memory;
- GPU/Metal/shared-memory requirements;
- installer or package-manager/cache footprint;
- arbitrary user workspace growth;
- all possible model storage requirements;
- a complete local-stack disk footprint;
- cross-machine performance or support;
- a supported/default model;
- a user-visible latency requirement;
- accessibility acceptance;
- release-candidate soak completion;
- full Lite performance thresholds;
- Phase 6 completion;
- Lite v1.0 completion.

A separate exact-commit primary Intel Mac collection and evidence-acceptance slice is required after this implementation merges.
