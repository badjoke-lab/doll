# IMP-058 — Deterministic Doll shutdown escape bundle

## Status

Implementation harness complete with deterministic synthetic CI evidence. Primary Intel Mac evidence remains pending and must be stored by a separate completion pull request bound to the exact merged implementation commit.

## Purpose

IMP-058 adds the bounded shutdown-recovery surface required before PORT-015 can pass. It composes already accepted contracts into one user-owned archive:

```text
read-only canonical Doll State
        ↓
verified State Package
        +
provider-independent conversation export
        +
project-scoped Resume Bundles
        ↓
versioned shutdown escape ZIP
        ↓
standard-library-only standalone inspection
```

The bundle is designed for a condition where no model, preferred UI, network connection, cloud credential, or running doll service is available. It is an export artifact and never becomes authoritative Doll State.

## Bundle format

The top-level format is `doll-shutdown-escape` version `1`. Its stable members are rooted under `doll-shutdown-escape/` and include:

- `state/state-package.doll.zip` — the complete currently implemented non-secret machine-restorable Doll State surface;
- `conversations/` — deterministic generic JSON, JSONL, Markdown, manifest, and checksum files when fully non-secret canonical conversations exist;
- `projects/<project-id>.resume.zip` — one independently verifiable Resume Bundle for each non-secret implemented project;
- `manifest.json` — bounded inventory, recovery surfaces, omitted-secret counts, inspection requirements, and limitations;
- `checksums.json` — SHA-256 and size inventory for every other outer member;
- `inspect_escape.py` — a standard-library-only verifier with no `doll` import;
- `README.txt` and `RECOVERY.md` — human-readable recovery entry points.

The State Package remains the authoritative complete restore vehicle. Generic conversation files and Resume Bundles are inspectable recovery views and do not replace the State Package.

## Export boundary

Export requires a valid read-only `StateRepository`. The destination:

- must not already exist;
- must be outside the Doll workspace;
- must be outside a doll repository checkout;
- is published through a temporary file, verified before publication, fsynced, and atomically replaced;
- is removed on any failed export or verification path.

Equivalent canonical input and a fixed export timestamp produce byte-identical archives. Export does not change workspace revision, state revision, records, audit log, authoritative files, or source artifacts.

## Secret and authority boundary

Secret records and credential material are omitted and counted. They are never serialized into the State Package, generic export, Resume Bundles, manifest, recovery documents, or acceptance evidence.

All exported content remains data only. It cannot create or modify:

- policy;
- permission;
- credential;
- capability;
- confirmed memory;
- decision authority;
- project state;
- procedure approval;
- checkpoint confirmation;
- work completion;
- model or runtime authority.

The bundle contains no automatic execution path. The bundled inspector verifies bytes and reports recovery surfaces; it does not import, restore, execute, or trust exported content.

## Standalone inspection boundary

`inspect_escape.py` imports only the Python standard library. It verifies:

- safe relative member paths under the declared root;
- duplicate and case-folding-collision rejection;
- regular-file-only members;
- bounded member count, uncompressed size, total size, and compression ratio;
- top-level SHA-256 and size inventory;
- manifest/member agreement;
- embedded State Package checksums and record-count agreement;
- embedded Resume Bundle checksums;
- generic conversation checksums and format identity;
- declared omitted-secret counts and recovery surfaces.

Inspection requires no model execution, model installation, runtime adapter, preferred UI, network access, cloud credential, workspace mutation, or running doll service.

## Evidence levels

### CI

CI builds a synthetic non-private Doll workspace containing one secret preference, confirmed memory, artifact, project, decision, canonical conversation, and two related conversation events. It then verifies:

1. deterministic repeated export;
2. unchanged workspace status and audit history;
3. State Package, generic conversation export, and Resume Bundle presence;
4. visible secret omission counts;
5. required recovery-surface declarations;
6. removal of the source workspace before standalone inspection;
7. successful fresh-process `python -I` inspection with `PYTHONPATH` removed;
8. rejection of outer archive tampering;
9. preservation of an existing destination;
10. absence of model, network, UI, cloud, or doll-service dependency.

CI records PORT-015 as `ci-pass`. It is not primary-machine shutdown evidence and cannot complete PORT-015 or establish stable general anti-lock-in.

### Primary Intel Mac

Real-machine evidence is accepted only when all of the following are explicit:

- the checked-out commit exactly matches `--commit-sha`;
- the operating system is Darwin;
- the architecture is `x86_64` or `amd64`;
- networking is disabled and `--offline-confirmed` is supplied;
- local-only operation is confirmed with `--local-only-confirmed`;
- no model argument, model execution, runtime installation, or doll service is required.

The real-machine run uses only the same synthetic non-private acceptance fixture. It does not read the user's personal Doll State.

## Commands

Synthetic CI-equivalent execution:

```bash
python scripts/run_imp_058_shutdown_escape.py \
  --commit-sha "$(git rev-parse HEAD)"
```

Primary Intel Mac execution after the implementation commit is merged:

```bash
python scripts/run_imp_058_shutdown_escape.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed
```

The bounded output must be reviewed before storage. Accepted evidence must not contain personal record content, project names, conversation text, paths, usernames, hostnames, native model names, credentials, or secret values.

## Acceptance and completion

The implementation harness may merge after Linux, macOS, Windows, dependency-lock, Ruff, formatting, strict mypy, generated-specification, public-status, implementation-numbering, CLI, and coverage checks pass.

Issue #183 remains open after that merge. A separate completion pull request must:

1. run the exact merged implementation commit on the primary Intel Mac with networking disabled;
2. use the synthetic non-private fixture and require no model or doll service;
3. review the bounded JSON result for private-data leakage;
4. store only the accepted privacy-safe result and matrix binding;
5. change PORT-015 from `ci-pass` to `pass` only after accepted real-machine evidence exists;
6. leave the complete Phase 6 gate pending unless all separate Phase 6 criteria are met.

## Explicit non-claims

IMP-058 does not establish:

- ChatGPT history migration or PORT-014;
- native Ollama history discovery;
- target-specific export back to Ollama, ChatGPT, or another application;
- provider-specific round-trip fidelity;
- model or runtime replacement;
- cloud portability;
- secret or credential portability;
- general replacement of every source application;
- the complete Phase 6 gate;
- a stable general anti-lock-in claim before accepted real-machine evidence is stored.
