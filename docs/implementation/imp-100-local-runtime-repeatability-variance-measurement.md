# IMP-100 — Local-runtime repeatability and variance measurement

Status: implementation for Issue #317.

## Purpose

IMP-100 adds a deterministic, privacy-safe way to compare repeated primary Intel Mac local-runtime/model measurements after IMP-099 accepted one bounded IMP-098 observation.

The new layer does not reinterpret the three generations inside one IMP-098 report as independent repeatability evidence. It requires exactly three separately invoked IMP-098 real-machine reports under the same measured identity.

## Measurement identity

All three source reports must already pass the IMP-098 real-machine validator for the same exact doll commit and must share:

- Darwin on Intel (`x86_64` / `amd64`);
- the same Python version;
- the same local runtime version;
- the same opaque Doll-facing model ID;
- the same exact model revision;
- the same provider-reported installed model bytes;
- `doll-local-runtime-single-model` measurement scope;
- offline-confirmed/local-only source conditions.

The source JSON files must also be byte-distinct. This prevents accidental reuse of one report three times. It is not proof of a cold start or process restart.

## Builder

`scripts/build_imp_100_runtime_repeatability_measurement.py` accepts exactly three source reports plus:

- the exact expected commit SHA;
- explicit confirmation that the measurements came from separate runner invocations;
- explicit confirmation that all three source reports received manual privacy review.

Each source is first validated with the existing IMP-098 validator. The shareable aggregate never records source file paths. It records only SHA-256 source fingerprints and bounded selected observations.

The aggregate reports deterministic per-session values and cross-session summaries for:

- maximum sampled Ollama/runtime process-tree RSS;
- doll-process peak RSS;
- generation duration at each of the three fixed generation positions.

Each summary contains the exact three values, minimum, maximum, floor mean, and spread. Provider-reported model bytes remain part of the shared identity rather than being treated as a variable measurement.

## Validator

`scripts/validate_imp_100_runtime_repeatability_measurement.py` validates:

- exact commit binding;
- fixed three-session shape;
- opaque model identity/revision format;
- distinct source hashes;
- positive bounded observations;
- exact deterministic variance summaries;
- all checks true;
- all privacy flags false;
- all release/performance claims false.

The validator does not accept repeatability evidence into the repository by itself. Its passing result keeps `real_machine_repeatability_accepted = false` and `manual_privacy_review_required = true`.

## Privacy boundary

The aggregate must not contain source file paths, absolute paths, usernames, hostnames, native model names, prompts, responses, process IDs, process command lines, credentials, secrets, workspace identifiers, URLs, or email addresses.

The source-report hashes are provenance fingerprints only. They do not authorize publication of unreviewed source files.

## Non-claims

IMP-100 does not define or prove:

- minimum system RAM;
- total-system peak memory;
- GPU or Metal memory requirements;
- full Lite installation/model-storage requirements;
- final user-visible latency requirements;
- cold-start requirements;
- cross-machine performance;
- supported/default model selection;
- a release repeatability threshold;
- full Lite performance thresholds;
- accessibility acceptance;
- release-candidate soak completion;
- Phase 6 completion;
- Lite v1.0 completion.

A separate real-machine collection and evidence-acceptance step is required after this implementation is merged and an exact approved `main` commit is pinned.
