# IMP-057 — Primary Intel Mac local-portability migration drill

## Status

Implementation and evidence complete for the bounded IMP-057 migration drill. Deterministic synthetic CI and privacy-reviewed primary Intel Mac evidence are accepted and bound to the exact merged implementation commit.

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

CI proves orchestration and failure-preserving contracts. It is not by itself evidence that a real local Ollama installation or model works on the project owner's machine. After the accepted real-machine result was stored, the bounded PORT-001, PORT-003, and PORT-013 entries moved from `ci-pass` to `pass` with both `ci` and `real-machine` listed as passed evidence levels.

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

The accepted run completed at `2026-06-29T15:48:03.615410Z` on Darwin `x86_64` with networking disabled, fixed IPv4 loopback Ollama, one explicitly selected already-installed local model, and exact implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6`. The privacy-reviewed result is stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`.

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

Issue #178 is completed by the separate evidence pull request. That completion:

1. ran the exact merged implementation commit on the primary Intel Mac with networking disabled;
2. reviewed the bounded result for private-data leakage;
3. stored only the accepted privacy-safe result and matrix binding;
4. changed the bounded PORT-001, PORT-003, and PORT-013 entries from `ci-pass` to `pass`;
5. left PORT-015 and the complete Phase 6 gate pending because their separate criteria are not met.

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
- a stable general local-environment portability or anti-lock-in claim beyond the bounded IMP-057 component and evidence surface.
