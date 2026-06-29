# IMP-057 — Primary Intel Mac local-portability migration drill

## Status

Implementation harness complete. Deterministic synthetic CI is accepted for the implementation boundary. Primary Intel Mac evidence remains pending and must be stored by a separate completion pull request bound to the exact merged implementation commit.

## Purpose

IMP-057 composes the accepted Phase 4A and Phase 5 boundaries with the IMP-055 Ollama API session source adapter and the IMP-056 explicit loopback chat capture service. It proves the bounded migration sequence:

```text
explicit local capture
        ↓
source validation and content-free inventory
        ↓
reviewed canonical import with provenance and source preservation
        ↓
alternate fresh-process retrieval and generic export
        ↓
original capture component absent
        ↓
State Package transfer and backup restore remain usable
```

The implementation does not add a second source format, new authoritative record type, schema migration, State Package version, model download path, cloud path, or tool authority.

## Evidence levels

### CI

CI uses an injected deterministic Ollama transport. It performs no socket operation and returns synthetic text. The complete capture, import, idempotency, conflict, generic export, State Package, backup, restore, and alternate fresh-process inspection flow runs on Linux, macOS, and Windows.

CI proves orchestration and failure-preserving contracts. It is not evidence that a real local Ollama installation or model works on the project owner's machine. Matrix entries therefore remain `ci-pass`, with only `ci` listed under passed evidence levels, until accepted real-machine evidence is stored.

### Primary Intel Mac

Real-machine mode is accepted only when all of the following are explicit:

- the checked-out commit exactly matches `--commit-sha`;
- the operating system is Darwin;
- the architecture is `x86_64` or `amd64`;
- networking is disabled and `--offline-confirmed` is supplied;
- local-only operation is confirmed with `--local-only-confirmed`;
- one already-installed local Ollama model is selected with `--model`;
- Ollama is already running on the declared fixed IPv4 loopback port.

The runner installs, downloads, deletes, activates, or selects no model automatically.

## Capture boundary

The capture phase uses the IMP-056 service and permits only:

```text
GET  /api/tags
GET  /api/version
POST /api/chat
```

The host is fixed to `127.0.0.1`. Proxy, redirect, credential, remote host, cloud endpoint, subprocess, application-database read, log read, shell-history read, terminal-history read, arbitrary-file read, streaming, tools, images, attachments, and multimodal paths are absent.

The test session contains one user message, one assistant message, and their parent relationship. The returned bundle is revalidated through IMP-055 before import.

## Import and publication boundary

The returned bytes remain external source data until the existing reviewed generic publication path accepts them. The drill verifies:

- exact source-environment identity;
- source hash and content-free inventory;
- preview without state mutation;
- exact approved plan hash;
- atomic canonical publication;
- imported provenance and source-object mappings;
- managed original-source preservation;
- explicit mapping, quarantine, and loss results;
- unchanged-source idempotency;
- changed-source conflict without overwrite;
- no automatic authority or confirmed-memory promotion.

Imported model identifiers remain source metadata. Imported text cannot create policy, permission, credential, capability, confirmation, procedure approval, project checkpoint, work completion, or confirmed memory.

## Alternate retrieval and removal boundary

After publication, the probe removes its references to the capture service, transport, and source adapter before starting three independent inspectors.

The inspector imports none of the following:

- `doll.ollama_adapter`;
- `doll.ollama_chat_capture`;
- `doll.ollama_session_import`;
- local or streaming conversation execution services.

It reads canonical Doll State, verifies the imported conversation and parent relationship, validates the preserved original-source artifact, and rebuilds a generic export through `GenericExportBuilder`.

The same inspection runs against:

1. the source workspace;
2. an empty target populated through State Package v2;
3. an empty target restored from a verified backup.

This is an interface and component replacement check. It does not claim that a second model or runtime adapter executed the imported text.

## Privacy-safe evidence

The result may contain only bounded facts such as:

- implementation commit;
- evidence level, operating-system class, and architecture;
- adapter and component identifiers;
- opaque or additionally hashed model identity;
- runtime version;
- source, generic-export, State Package, and backup hashes;
- record and request counts;
- named boolean checks;
- gate status and limitations.

The result must not contain prompts, responses, native model names, personal conversation content, absolute paths, usernames, hostnames, credentials, secret values, or reconstructable private fixtures.

## Commands

Synthetic CI-equivalent execution:

```bash
python scripts/run_imp_057_local_portability.py \
  --commit-sha "$(git rev-parse HEAD)"
```

Primary Intel Mac execution after the harness commit is merged:

```bash
python scripts/run_imp_057_local_portability.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model '<already-installed-local-model>'
```

The output must be reviewed before it is stored. The native model argument and any private local details are never copied into the accepted evidence file.

## Acceptance and completion

The harness may merge after all cross-platform, dependency-lock, Ruff, formatting, strict mypy, specification, public-status, numbering, CLI, and coverage checks pass.

Issue #178 remains open after that merge. A separate completion pull request must:

1. run the exact merged implementation commit on the primary Intel Mac with networking disabled;
2. review the bounded result for private-data leakage;
3. store only the accepted result and matrix binding;
4. change the bounded PORT-001, PORT-003, and PORT-013 entries from `ci-pass` to `pass` only after accepted real-machine evidence exists;
5. leave PORT-015 and the complete Phase 6 gate pending unless their full separate criteria are met.

## Explicit non-claims

IMP-057 does not establish:

- native Ollama history export or discovery;
- attachments, images, tools, multimodal, thinking, or streaming fidelity;
- target-specific export back to Ollama;
- a second runtime or model migration;
- ChatGPT history migration;
- general application replacement beyond this declared capture component;
- PORT-015;
- the complete Phase 6 gate;
- a stable local-environment portability or anti-lock-in claim before accepted real-machine evidence is stored.
