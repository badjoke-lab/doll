# IMP-083 — Lite client resource measurement harness

## Objective

Establish a reproducible privacy-safe measurement path for the resource cost of the doll Lite client itself before the project defines RAM, disk, or speed requirements.

The accepted Lite release specification states that exact RAM, disk, and speed requirements must be based on measurements. IMP-083 supplies the measurement mechanics only. It does not invent thresholds and does not complete the Lite performance or Phase 6 gates.

## Measurement scope

The measured workload is intentionally limited to doll-side client operations that need no model runtime, model weight, cloud account, credential, or network access:

1. initialize one fresh Lite workspace;
2. initialize authoritative state;
3. reload workspace identity;
4. open authoritative state read-only and immutable;
5. run the accepted read-only `doll doctor` diagnostic.

The workload uses a fresh temporary synthetic fixture. Initialization is the only intended state-creating setup. The reload, state-open, and doctor steps are read-only.

External Ollama/runtime memory and model-weight memory are not part of this measurement. Results label the scope `doll-lite-client-only` and explicitly state that external runtime and model memory are excluded.

## Metrics

Every run records:

- one monotonic nanosecond duration for each fixed workload step;
- total measured workload duration;
- doll-process RSS when the current platform exposes it through bounded standard-library adapters;
- explicit workspace regular-file bytes, regular-file count, and directory count;
- state schema version, state revision, and record count;
- operating-system family, architecture, and Python version.

Unix peak RSS uses `resource.getrusage(RUSAGE_SELF)` and normalizes Linux KiB versus Darwin bytes. Linux may additionally expose current RSS through `/proc/self/statm`. Windows uses `GetProcessMemoryInfo` through Python `ctypes` when available. The result distinguishes unavailable RSS instead of substituting Python allocation estimates or another misleading metric.

## Workspace disk traversal

Disk measurement traverses only the explicitly selected workspace root. An existing workspace input that is itself a symbolic link is rejected before workspace initialization, so initialization cannot resolve through that link and create files in its target. Traversal does not follow inner symlinks. Every resolved entry must remain beneath the selected root. Unsupported entries, symlinks, traversal failures, more than 20,000 entries, or depth beyond 32 fail closed. Only aggregate byte/count values are returned; names and paths are excluded.

## Evidence runner

`scripts/run_imp_083_lite_client_measurement.py` binds every run to the checked-out Git commit by requiring the supplied 40-character commit SHA to equal `git rev-parse HEAD` and by separately requiring the tracked index to equal HEAD and the tracked working tree to equal the index. A staged or unstaged tracked change therefore rejects the evidence run before measurement begins. Untracked evidence output is not treated as a source change, so shell redirection or `tee` may create the JSON result file without defeating the tracked-source guard.

After the commit and tracked-state guards pass, a Python audit hook rejects measured-workload socket connection attempts and process-launch attempts. The Git checks therefore remain evidence-wrapper processes, not part of the measured workload. The result reports this distinction explicitly.

CI evidence runs on Ubuntu, macOS, and Windows. A separate primary Intel Mac runbook requires Darwin x86_64/amd64 plus explicit offline and local-only operator confirmation. The real-machine path uses the same workload and schema; it does not require Ollama or a model.

## Privacy

Shareable results contain no native workspace path, workspace identifier, username, hostname, model name, request text, source text, prompt/response text, credential, or secret value. Failure output contains only the test ID, requested commit SHA, failing stage, and exception class.

## Non-claims

IMP-083 does not define minimum or recommended RAM, disk, or latency requirements. It does not measure external Ollama/runtime memory, loaded model weights, GPU/VRAM, model response latency, token throughput, quality, energy use, Heavy workloads, or total-system resource use. It does not add telemetry, analytics, background collection, network reporting, or cloud upload.

Passing IMP-083 means only that a bounded cross-platform measurement harness exists. Primary real-machine measurements, interpretation of those measurements, final Lite resource requirements, accessibility work, release-candidate soak, complete Phase 6, Lite v1.0, and stable general anti-lock-in remain separate work.
