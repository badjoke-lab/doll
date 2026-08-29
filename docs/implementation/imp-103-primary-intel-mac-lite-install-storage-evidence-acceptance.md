# IMP-103 — Primary Intel Mac Lite installation/model-storage evidence acceptance

Status: accepted real-machine evidence for Issue #324, subject to acceptance PR CI.

## Scope

IMP-103 accepts one privacy-reviewed primary Intel Mac execution of the IMP-102 Lite installation/model-storage measurement harness. The accepted evidence is bound to measured commit:

`a323aa0958387dcd746fa9ef9fa95eb519da1e54`

Evidence file:

`docs/testing/results/IMP-103-primary-intel-mac-lite-install-storage-measurement.json`

The exact uploaded source JSON has SHA-256:

`b6378bd247ccf0576da6e474548fe725e8077e1156ba5c6ec0ec727b9301323a`

The physical run used Darwin `x86_64`, CPython `3.14.6`, `uv 0.11.21`, Ollama runtime `0.33.2`, explicit offline/local-only confirmation, the locked no-dev/all-supported-extras Lite profile, and one already-installed local text model. The native model name is not present in the shareable evidence.

## Accepted measurements

The deterministic result reports:

- `result = pass`;
- `evidence_level = real-machine`;
- `measurement_scope = doll-lite-python-install-selected-model-storage`;
- Lite installation profile: `lite-python-no-dev-all-extras`;
- optional extras: `ocr`, `pdf`;
- dependency source mode: `locked-offline-local-cache`;
- editable install used: `false`;
- dev dependencies included: `false`;
- Lite installation regular files: `2029`;
- Lite installation directories: `1135`;
- Lite installation symlinks: `3`;
- Lite installation logical bytes: `64426153`;
- Lite installation allocated bytes: `69378048`;
- symlink target bytes included: `false`;
- provider-reported installed model bytes: `986061892`;
- runtime installation aggregate measured: `false`;
- external network request used: `false`;
- cloud credentials used: `false`;
- automatic model download used: `false`;
- runtime install/start used: `false`;
- temporary installation cleaned: `true`.

The required Lite import/dependency checks all passed. Every fixed measurement check is true, every fixed privacy flag is false, and every broader disk/performance/release claim remains false.

## Privacy review

The complete uploaded JSON was manually reviewed before repository acceptance. It contains no absolute, source, temporary, or runtime-installation paths; filenames or runtime member names; usernames or hostnames; native model name; process IDs or command lines; credentials or secret values; workspace identifiers; URLs; or email addresses.

The evidence intentionally retains only the opaque Doll-facing model ID and exact model revision. The deterministic validator still reports `manual_privacy_review_required = true` and `real_machine_measurement_accepted = false` by design; repository acceptance records that the required manual review and project-level acceptance were completed outside the validator.

## Deterministic validation

CI re-runs:

```sh
python scripts/validate_imp_102_lite_install_storage_measurement.py \
  docs/testing/results/IMP-103-primary-intel-mac-lite-install-storage-measurement.json \
  --expected-commit-sha a323aa0958387dcd746fa9ef9fa95eb519da1e54
```

The committed evidence must continue to validate as exact-commit real-machine Darwin Intel evidence with positive logical and allocated Lite installation bytes, the locked no-dev/all-extras profile, opaque model identity/revision, positive provider-reported model bytes, explicit unmeasured runtime-installation scope, all checks true, all privacy flags false, and all broader claims false.

## Acceptance boundary

This evidence is one bounded installation/model-storage observation on the primary Intel Mac. It does **not** establish a final minimum disk or RAM requirement, installer/package-manager/cache footprint, arbitrary workspace growth, all-model storage requirements, a complete local-stack disk footprint, total-system or GPU/Metal/shared-memory requirements, cross-machine support, supported/default model selection, user-visible latency requirements, accessibility acceptance, release-candidate soak completion, full Lite performance thresholds, Phase 6 completion, or Lite v1.0 completion.

Because the optional runtime installation root was intentionally omitted, this accepted evidence must not be described as a complete local-stack disk footprint.
