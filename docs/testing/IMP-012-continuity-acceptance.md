# IMP-012 Continuity Acceptance Test

**Status:** Blocking Phase 2 gate  
**Evidence level:** Automated CI plus primary Intel Mac real-machine drill

## Purpose

IMP-012 proves the complete model-independent continuity foundation delivered by IMP-001 through IMP-011 before Phase 3 safety-boundary work depends on it.

The acceptance suite uses only synthetic temporary data. It does not require a model runtime, cloud credential, account, network service, personal fixture, or private workspace.

## Blocking specification mapping

The suite records results for the following currently implemented blocking tests:

- `CONT-P001` workspace initialization;
- `CONT-P002` no-cloud core state and recovery paths;
- `CONT-P005` confirmed memory persistence;
- `CONT-P006` project and decision persistence with typed links;
- `CONT-P008` managed artifact creation and verification;
- `CONT-P009` workspace escape and unsafe target rejection;
- `CONT-P010` backup creation and verification;
- `CONT-P011` state and workspace restore into empty targets;
- `CONT-P012` fresh-process post-restore validation and inspection;
- `CONT-P015` audit coverage for implemented continuity operations;
- `CONT-P016` model independence of continuity;
- `STATE-001` through `STATE-012` where implemented;
- `PLAT-001` through `PLAT-007` where applicable.

Tests not yet implementable without later safety or model phases remain explicitly outside this gate.

## Automated command

Run from the repository root:

```text
PYTHONPATH=src python scripts/run_imp_012_continuity_acceptance.py \
  --commit-sha 0000000000000000000000000000000000000000 \
  --evidence-level ci \
  > imp-012-continuity-acceptance.json
```

The supplied SHA must exactly match `git rev-parse HEAD`.

The command exits with `0` only when every blocking check passes. Failure output contains only the test ID, commit SHA, completion time, and error class.

## Primary Intel Mac command

1. Check out the exact PR head.
2. Install the locked development environment while online.
3. Disable Wi-Fi, Ethernet, VPN, and tethering.
4. Run:

```text
PYTHONPATH="$PWD/src" .venv/bin/python scripts/run_imp_012_continuity_acceptance.py \
  --commit-sha 0000000000000000000000000000000000000000 \
  --evidence-level real-machine \
  --offline-confirmed \
  > imp-012-intel-mac-continuity-acceptance.json
```

The real-machine gate additionally requires:

- `operating_system` equal to `Darwin`;
- architecture `x86_64` or `amd64`;
- `network_mode` equal to `disabled-confirmed-by-operator`;
- `model_runtime_used` equal to `false`;
- `cloud_credentials_used` equal to `false`;
- every entry under `checks` equal to `true`;
- every privacy flag indicating that private environment data is absent.

## What the drill proves

The acceptance run performs one complete synthetic continuity lifecycle:

1. initialize a clean workspace and state repository;
2. create a Japanese UTF-8 preference, policy, scoped permission, confirmed memory, managed artifact, project, decision, typed links, and audit history;
3. close and reopen the workspace in a fresh repository process boundary;
4. inspect all implemented authoritative records and verify artifact bytes and hashes;
5. export, verify, inspect, and import a Doll State Package into an empty target;
6. create and verify state and workspace backups;
7. restore both backup kinds into empty targets;
8. reopen imported and restored workspaces in separate Python processes;
9. verify identity, schema, revision semantics, records, links, audit history, backup inventory, artifact paths, hashes, and bytes;
10. reject tampered input and a populated target without damaging its last-known-good content;
11. prove read-only recovery inspection remains available and authoritative writes are denied;
12. emit a privacy-safe JSON report containing no local path, username, hostname, secret, or personal fixture.

## Limitations

- This Phase 2 gate does not execute or evaluate a model.
- Model replacement and local fallback tests remain Phase 4 work.
- Secret-store, credential-broker, external-content, capability, and confirmation tests remain Phase 3 work.
- Windows and Ubuntu are CI-tested beta targets; the real-machine support claim remains limited to the primary Intel Mac.

## Merge rule

IMP-012 may merge only when:

- dependency lock, formatting, lint, strict type checking, generated-spec checks, and the full test suite pass;
- repository coverage remains at or above 95%;
- macOS, Windows, and Ubuntu CI pass;
- the primary Intel Mac real-machine report passes on the exact PR head;
- restore or import refusal leaves the last known good target unchanged;
- no model execution or cloud credential path is required.
