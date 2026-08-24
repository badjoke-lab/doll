# IMP-099 — Primary Intel Mac local runtime/model resource evidence acceptance

Status: accepted real-machine evidence for Issue #314.

## Scope

IMP-099 accepts one privacy-reviewed primary Intel Mac execution of the IMP-098 local runtime/model resource measurement harness. The accepted evidence is bound to measured commit:

`7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c`

Evidence file:

`docs/testing/results/IMP-099-primary-intel-mac-local-runtime-resource-measurement.json`

The physical run used Darwin `x86_64`, CPython `3.14.6`, explicit offline/local-only confirmation, one already-installed local Ollama text model, and the fixed loopback runtime path. The native model name is not present in the shareable evidence.

## Accepted measurements

The deterministic result reports:

- `result = pass`;
- `evidence_level = real-machine`;
- `measurement_scope = doll-local-runtime-single-model`;
- Ollama runtime version: `0.32.15`;
- provider-reported installed model bytes: `986061892`;
- sampled Ollama process-tree RSS bytes: `6991872`, `1251598336`, `1251979264`, `1252057088`;
- maximum sampled Ollama process-tree RSS: `1252057088 bytes`;
- doll-process peak RSS: `36093952 bytes`;
- generation durations: `6763389867 ns`, `129910556 ns`, `147618618 ns`;
- generated output character counts: `2`, `2`, `2`;
- external network request used: `false`;
- cloud credentials used: `false`;
- automatic model download used: `false`;
- runtime install/start used: `false`.

Every required measurement check is true and every fixed privacy flag is false.

## Privacy review

The complete uploaded JSON was manually reviewed before repository acceptance. It contains no absolute local paths, usernames, hostnames, native model name, fixed prompt text, generated response text, process IDs, process command lines, credentials, secret values, workspace identifiers, URLs, or email addresses.

The deterministic validator still reports `manual_privacy_review_required = true` by design; repository acceptance records that the required manual review was completed outside the validator.

## Deterministic validation

CI re-runs:

```sh
python scripts/validate_imp_098_local_runtime_resource_measurement.py \
  docs/testing/results/IMP-099-primary-intel-mac-local-runtime-resource-measurement.json \
  --expected-commit-sha 7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c
```

The committed evidence must continue to validate as real-machine, repeat count 3, bounded single local runtime/model scope, with all broader performance and release claims false.

## Acceptance boundary

This evidence is one representative local-runtime/model observation on the primary Intel Mac. It does **not** establish minimum system RAM, total-system peak memory, GPU/Metal/shared-memory requirements, full Lite installation disk requirements, final user-visible latency requirements, cold-start performance, cross-machine performance, supported/default model selection, full Lite performance thresholds, Phase 6 completion, Lite v1.0 completion, or the release-candidate soak.

The first generation is substantially slower than the two repeated generations, so these three samples are retained as measurement evidence rather than converted into a product latency threshold.
