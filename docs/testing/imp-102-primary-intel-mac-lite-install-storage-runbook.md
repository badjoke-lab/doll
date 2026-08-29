# IMP-102 — Primary Intel Mac Lite installation/model-storage runbook

## Status

Preparation only. No physical installation/model-storage result is accepted by this document.

Do not perform the physical collection until the IMP-102 implementation PR is merged and a follow-up acceptance issue pins one exact approved `main` commit. If `main` advances after that pin, do not silently measure a different commit.

## What is measured

IMP-102 measures a bounded storage slice on the primary Intel Mac:

- one fresh temporary doll Python environment installed from the exact tracked checkout;
- base doll dependencies plus all currently supported Lite optional extras (`pdf` and `ocr`);
- no development dependency group;
- regular-file counts, directory/symlink counts, logical bytes, and allocated bytes for that temporary environment;
- one explicitly selected already-installed local Ollama text model by opaque Doll model ID, exact revision, and provider-reported installed size bytes;
- optionally, one explicitly supplied local runtime installation root as aggregate counts/bytes only.

The temporary Python environment is installed with the locked dependency graph in offline mode from already available local/cache material. The harness does not install or download Ollama or model weights.

Symlink targets are not followed or counted. In particular, a Python interpreter reached through a symlink is not silently counted as if it were owned by the temporary doll environment.

## Preconditions

1. A follow-up acceptance issue has pinned the exact commit SHA to measure.
2. The primary development Mac is Darwin Intel (`x86_64` / `amd64`).
3. The tracked checkout is clean and exactly at the pinned commit.
4. Ollama is already running locally.
5. One already-installed non-cloud Ollama text model is selected locally.
6. External networking is manually disabled for the full collection period.
7. The local uv cache already contains every locked dependency needed for the base project plus the `pdf` and `ocr` extras. The evidence run must not fetch missing dependencies.
8. No cloud credential is provided to the measurement harness.
9. The operator does not install, pull, update, start, stop, or delete Ollama or model assets as part of the measurement.

If the offline dependency material is incomplete, the runner must fail. Do not enable networking during the evidence run and do not edit a failed report into a passing report.

## Optional runtime installation aggregate

The Python-environment and selected-model measurements do not automatically include the Ollama application/runtime installation files.

If the operator can identify one canonical local runtime installation root for the exact installed runtime, it may be supplied with `--runtime-install-root`. The shareable report records only aggregate tree counts/bytes; it never records that path or member names.

Do not guess a runtime root. If it is uncertain or split across multiple locations, omit the option. The report will explicitly record `runtime_installation.measured = false`, and the result must not be described as a complete local-stack disk footprint.

## Collect the bounded result

From the pinned checkout:

```sh
COMMIT_SHA="<pinned-exact-commit>"
MODEL="<already-installed-local-model>"

uv run python scripts/run_imp_102_lite_install_storage_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp102-lite-install-storage.json
```

If one explicit runtime installation root is known and intentionally included, add:

```sh
  --runtime-install-root "<explicit-runtime-install-root>"
```

The native model name and optional runtime root are local invocation inputs only. Neither is written into the shareable JSON.

The runner creates a temporary Lite environment, measures it, and removes it before successful completion. A passing report must say `temporary_installation_cleaned = true`.

## Manual privacy review

Before validation or upload, inspect the entire JSON. It must contain no:

- absolute, source, or temporary paths;
- runtime installation path or member names;
- filenames;
- usernames or hostnames;
- native model name;
- process IDs or command lines;
- credentials or secret values;
- workspace identifiers;
- URLs or email addresses.

If any unexpected private content is present, stop and do not upload the report.

## Validate

```sh
uv run python scripts/validate_imp_102_lite_install_storage_measurement.py \
  ../imp102-lite-install-storage.json \
  --expected-commit-sha "$COMMIT_SHA"
```

A passing validator result still reports:

- `real_machine_measurement_accepted = false`;
- `full_install_disk_requirement_defined = false`;
- `full_lite_performance_thresholds_defined = false`;
- `phase6_gate_complete = false`;
- `lite_v1_complete = false`;
- `manual_privacy_review_required = true`.

Repository acceptance is a separate follow-up implementation slice.

## What this still does not prove

Even after later acceptance, this evidence remains one bounded observation on the primary Intel Mac. It does not establish a final minimum disk or RAM requirement, total-system/GPU/Metal memory, installer/package-manager/cache footprint, arbitrary workspace growth, every possible model footprint, a complete local-stack disk footprint when the runtime root is omitted or incomplete, cross-machine support, a supported/default model, user-visible latency, accessibility acceptance, the release-candidate soak, Phase 6 completion, or Lite v1.0 completion.
