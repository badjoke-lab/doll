# IMP-104 primary Intel Mac user-visible latency collection runbook

This runbook is for a later physical evidence collection after the IMP-104 runner and validator have merged. It does not itself accept machine evidence.

## Preconditions

Use the physical primary development Mac only.

Before collection:

- use a clean tracked checkout at the exact approved measurement commit;
- confirm Darwin Intel (`x86_64` / `amd64`);
- ensure the locked development environment is already available;
- ensure Ollama is already running locally;
- select one already-installed non-cloud local text model;
- do not pull, install, update, start, stop, or delete a model/runtime during collection;
- manually disable external networking before the evidence run;
- do not supply machine paths, usernames, hostnames, or other private identifiers as report metadata.

The native model name is required only as a private command-line selector. The successful shareable report converts it to an opaque Doll-facing model ID and revision.

## Collection

From the exact clean checkout, set shell variables privately for the approved commit and already-installed local model, then run:

```sh
uv run python scripts/run_imp_104_user_visible_latency_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp104-user-visible-latency.json
```

The successful run measures exactly one `draft`, one `revise`, and one `summarize` operation at the existing app-ready local-writing boundary. It does not measure startup, first-token, streaming, cold-start classification, or a final latency threshold.

A non-zero exit is a failed collection. Do not edit a failed report into a passing report.

## Deterministic validation

While external networking remains disabled, run:

```sh
uv run python scripts/validate_imp_104_user_visible_latency_measurement.py \
  ../imp104-user-visible-latency.json \
  --expected-commit-sha "$COMMIT_SHA"
```

Both the runner and validator must exit zero before the report is considered eligible for manual privacy review.

## Manual full-file privacy review

Inspect the complete JSON before repository acceptance. It must contain no:

- absolute or local paths;
- username or hostname;
- native model name;
- source identifier;
- request, source, prompt, or response text;
- process ID or command line;
- credential or secret value;
- workspace identifier;
- URL or email address.

The report intentionally keeps `real_machine_measurement_accepted = false`. Validator success means the bounded physical report is structurally valid; project-level acceptance is a separate implementation step.

If unexpected private content appears, discard/regenerate the report after fixing the source. Do not sanitize a failed/private report by hand and then accept it.

## Acceptance boundary

A later acceptance slice may commit only privacy-reviewed evidence and derived acceptance artifacts after exact validation. It must preserve all IMP-104 non-claims, including no first-token/cold-start/streaming claim and no final latency threshold, unless separate evidence establishes them.
