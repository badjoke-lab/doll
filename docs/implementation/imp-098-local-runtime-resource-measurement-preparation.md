# IMP-098 — Local runtime/model resource measurement preparation

Status: implementation preparation for Issue #312.

## Purpose

IMP-098 prepares the next real-machine evidence path after IMP-097 without turning one client-only observation into a Lite hardware requirement.

The accepted release specification says exact Lite RAM, disk, and speed requirements must be based on measurements. IMP-097 therefore left representative local-runtime/model resource evidence and repeatability evidence open. IMP-098 adds a bounded way to collect the next physical observation.

No physical IMP-098 result is accepted by this preparation slice.

## Reused local-only boundary

The real-machine runner reuses the existing `LoopbackOllamaTransport`, `OllamaRuntimeAdapter`, runtime contract, and opaque Ollama model ID mapping.

The runtime endpoint remains fixed to IPv4 loopback `127.0.0.1`. The selected native model name is an explicit local operator input and must already exist in local inventory. Cloud-tagged model names are rejected.

The runner exposes no model installation, model pull, runtime start/stop, arbitrary host, proxy, redirect, credential, or cloud fallback path.

## Measurement workload

Version 1 uses one fixed fabricated short generation prompt and exactly three generation iterations.

For one explicitly selected installed text model it records only:

- local runtime version;
- deterministic opaque model ID;
- exact local model revision digest;
- provider-reported installed model bytes from the local inventory;
- one sampled Ollama process-tree RSS value before generation and one after each generation;
- process counts for those same samples without PIDs or command lines;
- doll-process RSS through the existing Lite RSS adapter;
- three generation durations;
- output character counts.

Prompt and response content are not serialized.

The Ollama process-tree sample is obtained on macOS by finding the single listener PID for the configured local port with `lsof`, reading only PID/PPID/RSS numeric columns from `ps`, and recursively aggregating the listener plus descendants. PIDs and command lines remain transient and are not written to evidence.

The process-tree RSS samples are discrete observations, not a continuous peak monitor. The test also does not force a cold model state or restart the runtime.

## Exact real-machine gate

Real-machine collection fails closed unless:

- the supplied SHA equals the current checked-out HEAD;
- the tracked checkout is clean;
- the machine is Darwin Intel;
- offline and local-only confirmations are explicit;
- one non-cloud local model is explicitly selected;
- the fixed-loopback runtime is ready;
- exact raw inventory metadata and normalized adapter inventory agree on model identity and revision;
- the local listener is unambiguous;
- all RSS samples and repeated durations are positive;
- every generation returns non-empty bounded output.

The wrapper may execute `git`, `lsof`, and `ps` for evidence binding and process inspection. That is explicitly separate from model execution and is recorded as measurement-wrapper process inspection.

## Synthetic CI evidence

CI uses deterministic synthetic observations and performs no Ollama request or OS process inspection. It proves only the report schema, fixed repeat/sample counts, privacy flags, conservative claim flags, and validator behavior.

CI evidence is explicitly marked:

- `evidence_level = ci`;
- `synthetic_observations = true`;
- `real_machine_measurement_collected = false`;
- `loopback_runtime_request_used = false`.

It cannot substitute for the required physical Mac run.

## Validation and privacy

`scripts/validate_imp_098_local_runtime_resource_measurement.py` accepts only a real-machine report that is bound to an explicitly expected commit SHA and has:

- Darwin Intel machine class;
- offline-confirmed mode;
- exact `doll-local-runtime-single-model` scope;
- three generation durations and four runtime RSS/process-count samples;
- internally consistent min/max/mean/spread values;
- opaque model identity and revision only;
- positive provider-reported model bytes;
- all checks true;
- all privacy flags false;
- every performance/release completion claim false.

The validator also rejects evidence keys that would directly carry a native model name, prompt/response text, PID, command line, hostname, username, or absolute path.

Manual privacy review remains mandatory before repository acceptance.

## Non-claims

IMP-098 preparation does not establish or accept:

- a physical runtime/model resource result;
- minimum system RAM;
- total-system peak memory;
- GPU/Metal/shared-memory requirements;
- complete model or installation disk requirements;
- final user-visible latency requirements;
- cold-start performance;
- cross-machine performance;
- supported/default model selection;
- full Lite performance thresholds;
- Lite performance acceptance;
- accessibility acceptance;
- release-candidate soak completion;
- Phase 6 completion;
- Lite v1.0 completion.

The next evidence-acceptance slice must bind an actual reviewed physical Mac JSON to the exact measured commit before the representative local-runtime/model evidence class can move from prepared to accepted.
