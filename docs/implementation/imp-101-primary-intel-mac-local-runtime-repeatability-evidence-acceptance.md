# IMP-101 — Primary Intel Mac local runtime repeatability/variance evidence acceptance

Status: accepted real-machine repeatability evidence for Issue #319, subject to acceptance PR CI.

## Scope

IMP-101 accepts one privacy-reviewed three-session repeatability aggregate produced by the IMP-100 harness on the physical primary Intel Mac. The accepted evidence is bound to measured commit:

`a861e4bfd85214c6337bb188c3318e90846f5ebf`

Evidence file:

`docs/testing/results/IMP-101-primary-intel-mac-local-runtime-repeatability-variance.json`

The three source sessions were separate IMP-098 runner invocations on Darwin `x86_64`, CPython `3.14.6`, Ollama `0.33.1`, explicit offline/local-only operation, and one unchanged opaque model identity/revision. The native model name is not present in the shareable aggregate.

The source reports are not committed. The aggregate binds them by SHA-256 and retains only the selected privacy-safe measurements required by the IMP-100 contract.

## Source binding

The manually privacy-reviewed source report SHA-256 values are:

1. `8b8f7f081d43f87491436e7cc0764d64e834f5629f5914e313537593d14a47b2`
2. `3ea6d716fcc4bdd151d317a258960620c09aaa6d207ed55c623478ead8598d36`
3. `1f38aa7a186b824b119f5f2a87dd9e191638017a7bcc2d55d3f95ad014b7c547`

All three source reports independently satisfy the IMP-098 evidence contract and are byte-distinct.

## Accepted measurements

The deterministic aggregate reports:

- `result = pass`;
- `evidence_level = real-machine`;
- `measurement_scope = doll-local-runtime-single-model-repeatability`;
- session count: `3`;
- provider-reported installed model bytes: `986061892`;
- maximum sampled runtime process-tree RSS by session: `1202470912`, `1203814400`, `1137139712` bytes;
- runtime RSS cross-session spread: `66674688 bytes`;
- doll-process peak RSS by session: `34045952`, `35110912`, `34877440` bytes;
- doll peak RSS cross-session spread: `1064960 bytes`;
- generation position 1 durations: `10589242907`, `268770737`, `855706395` ns;
- generation position 1 spread: `10320472170 ns`;
- generation position 2 durations: `388068715`, `206806131`, `178651404` ns;
- generation position 3 durations: `389179518`, `153366166`, `205712268` ns;
- generated output character counts remain `2`, `2`, `2` in every source session.

The large position-1 timing spread is preserved as evidence. It is not converted into a product latency or cold-start requirement.

## Privacy review

The complete three uploaded source JSON files and the generated aggregate were manually reviewed before repository acceptance. No absolute local paths, usernames, hostnames, native model name, fixed prompt text, generated response text, process IDs, process command lines, credentials, secret values, workspace identifiers, URLs, or email addresses were found.

The committed aggregate contains source hashes rather than source file paths. Every fixed aggregate privacy flag is false.

The deterministic validator still reports `manual_privacy_review_required = true` by design; repository acceptance records that the required review was completed outside the validator.

## Deterministic validation

CI re-runs:

```sh
python scripts/validate_imp_100_runtime_repeatability_measurement.py \
  docs/testing/results/IMP-101-primary-intel-mac-local-runtime-repeatability-variance.json \
  --expected-commit-sha a861e4bfd85214c6337bb188c3318e90846f5ebf
```

The committed aggregate must continue to validate with three distinct source hashes, all repeatability checks true, and every broader performance/release claim false.

## Acceptance boundary

This evidence demonstrates bounded repeatability/variance for one primary Intel Mac, one current local runtime version, and one exact local model revision across three separate warm/current-runtime measurement invocations. It does **not** establish minimum system RAM, total-system/GPU/Metal memory requirements, full Lite installation/model-storage requirements, final user-visible latency requirements, cold-start requirements, cross-machine performance, supported/default model selection, a release requirement for acceptable variance, full Lite performance thresholds, accessibility acceptance, release-candidate soak completion, Phase 6 completion, or Lite v1.0 completion.
