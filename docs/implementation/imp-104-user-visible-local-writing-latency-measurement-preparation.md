# IMP-104 — User-visible local-writing latency measurement preparation

Status: implemented for Issue #329, pending PR CI.

## Purpose

IMP-104 prepares the next bounded Lite performance-evidence class identified by the IMP-097 interpretation: `user-visible-latency-workload-measurement`.

The accepted model-evaluation specification lists first-token latency, generation speed, load time, memory/resource use, and cancellation latency as performance dimensions. The currently accepted IMP-063/IMP-064 local-writing path is non-streaming, so this slice does not pretend that a first-token boundary exists in the current product path.

Instead, IMP-104 measures the user-visible completion boundary that exists today:

`LocalWritingWorkflowService.execute()` invocation -> completed `LocalWritingWorkflowResult`

The clock is `time.perf_counter_ns()`.

## Bounded workload

The workload reuses the accepted IMP-064 writing semantics and runs exactly three modes in order:

1. `draft`;
2. `revise` with one bounded inline data-only source;
3. `summarize` with the existing hostile-source/prompt-injection fixture retained as untrusted data.

One positive end-to-end completion duration is recorded for each mode. Workspace initialization, runtime preflight, model/runtime manifest and binding setup are intentionally completed before the measured workflow calls and are explicitly marked as excluded from each duration.

This is an app-ready local-writing workload observation, not application startup time or model cold-start classification.

## Runtime and network boundary

CI uses the existing deterministic IMP-064 transport. It exercises the real writing workflow and canonical state path without opening a socket or invoking a real model.

The later real-machine path requires:

- exact measured commit and clean tracked checkout;
- physical Darwin Intel (`x86_64` / `amd64`);
- external networking manually disabled;
- explicit offline and local-only confirmation;
- an already-running local Ollama runtime;
- one explicitly selected already-installed non-cloud local text model;
- the existing fixed IPv4 loopback transport only.

The runner never pulls a model, installs or starts the runtime, uses cloud credentials, or falls back to an external network path.

## Shareable evidence

The report contains only privacy-safe structural observations:

- exact Doll commit and environment class;
- OS, architecture, and Python version;
- local runtime version;
- opaque Doll-facing model identity and revision;
- fixed workflow mode labels;
- positive completion durations in nanoseconds;
- content-free workflow/event/request/socket counts;
- explicit checks, privacy flags, and non-claims.

It does not serialize native model names, request text, source text, prompt text, response text, absolute paths, usernames, hostnames, source identifiers, process IDs or command lines, credentials, secrets, workspace identifiers, URLs, or email addresses.

## Validation

Later physical evidence must pass:

```sh
python scripts/validate_imp_104_user_visible_latency_measurement.py \
  <artifact> \
  --expected-commit-sha <exact-measured-commit>
```

The validator accepts only real-machine Darwin Intel evidence bound to the exact expected commit. It requires the exact three-mode workload, positive completion durations, fixed measurement boundary, local loopback use, all checks true, every privacy flag false, and every broader performance/release claim false.

CI can synthesize the real-machine envelope in tests only to exercise validator behavior. That does not constitute accepted physical evidence.

## Non-claims

IMP-104 does **not** establish or measure:

- a final user-visible latency requirement or threshold;
- first-token latency;
- streaming latency;
- cold-start latency or cold/warm classification;
- generation throughput requirements;
- application startup latency;
- supported/default model selection;
- cross-machine performance support;
- full Lite performance thresholds or gate completion;
- accessibility acceptance;
- release-candidate soak completion;
- Phase 6 completion;
- Lite v1.0 completion.

Physical primary Intel Mac evidence acceptance remains a separate follow-up implementation after this collection/validation path is merged.
