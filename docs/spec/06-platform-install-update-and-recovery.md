# Platform, installation, update, and recovery

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `04-security-permissions-and-threat-model.md`, `05-model-vault-lifecycle-evaluation.md`

## 1. Purpose

This document defines how doll is installed, started, updated, migrated, rolled back, backed up, restored, and recovered across supported desktop operating systems.

The goal is not only successful installation. The goal is to preserve a usable local environment when:

- the preferred installer or package source is unavailable;
- a product update fails;
- a schema migration fails;
- a model runtime changes;
- the machine is replaced;
- the operating system changes;
- the primary UI is unavailable;
- network access is unavailable;
- upstream doll development stops.

## 2. Platform targets

### 2.1 Initial targets

- macOS Intel: primary real-machine verification target;
- Windows x64: CI-tested beta until real-machine verification;
- Ubuntu Linux x64: CI-tested beta until real-machine verification.

### 2.2 Experimental targets

- macOS Apple Silicon until real-machine validation is available;
- other Linux distributions;
- Windows on ARM;
- Linux ARM;
- unusual filesystems;
- GPU-specific runtime combinations;
- WSL as a distinct environment.

### 2.3 Support labels

A platform claim must use one of these labels:

- `real-machine verified`;
- `CI verified`;
- `community verified`;
- `experimental`;
- `unsupported`.

CI success must not be described as full real-machine support.

## 3. Cross-platform design rules

The implementation must:

- use `pathlib` or equivalent path abstractions;
- use platform-aware application data directories;
- avoid hard-coded path separators;
- avoid shell-specific syntax;
- use UTF-8 explicitly for text files;
- normalize and validate filenames;
- account for case sensitivity differences;
- account for Windows reserved names;
- account for file-lock behavior;
- account for symlinks, junctions, and mount points;
- use atomic replacement where supported;
- test line-ending and newline behavior;
- avoid requiring administrator or root access for ordinary use.

The implementation must not assume:

- `/home/...` paths;
- drive `C:`;
- one shell;
- one package manager;
- one GPU vendor;
- one filesystem case-sensitivity model;
- one operating system credential store.

## 4. Default data directories

The default private workspace root should follow platform conventions.

Direction:

- macOS: `~/Library/Application Support/doll/`;
- Windows: `%LOCALAPPDATA%\doll\`;
- Linux: `$XDG_DATA_HOME/doll/` or `~/.local/share/doll/`.

Configuration and cache directories may follow separate platform conventions.

The user may configure an alternate workspace root.

### Rules

- The default workspace must not be inside the Git repository checkout.
- Changing the configured path must not silently create a new identity if an existing workspace is intended.
- Removable and network filesystems must be marked experimental until locking and atomicity are validated.
- The system must detect obvious repository-checkout and temporary-directory mistakes.

## 5. Initial installation strategy

### 5.1 Development installation

Initial supported development path:

```text
git clone
uv sync
uv run doll doctor
```

### 5.2 User installation direction

Initial user-facing direction:

```text
uv tool install doll
```

or an equivalent package installation once a distributable package exists.

The first implementation may require a repository checkout during pre-alpha. Documentation must state this honestly.

### 5.3 Docker

Docker is not a required initial installation path.

Reasons:

- model and GPU integration differs across platforms;
- local file permissions become harder to explain;
- desktop users may not have Docker;
- data persistence and recovery can become opaque;
- Windows and macOS behavior can differ from Linux.

A later optional container path may be added for advanced users or services.

### 5.4 Native installers

Native installers or packaged desktop applications are deferred until Lite proves continuity and core behavior.

A future installer must not hide the workspace location or recovery path.

## 6. Dependency groups

Dependencies must be separated so the core can start without optional features.

Direction:

- `core`: state, API, CLI, validation, backup, migration;
- `lite`: initial local runtime adapter and lightweight document tools;
- `heavy`: larger retrieval, media, evaluation, and training tools;
- `ocr`: OCR-specific dependencies;
- `audio`: speech dependencies;
- `video`: video dependencies;
- `cloud`: future cloud gateway dependencies;
- `dev`: tests, lint, type checks, build tooling.

An unavailable optional dependency must disable only its capability.

## 7. External tools

External tools may include:

- Ollama;
- llama.cpp executables;
- vLLM services;
- Tesseract;
- whisper.cpp;
- FFmpeg;
- Playwright browsers;
- ComfyUI;
- later model conversion or training tools.

Doll must not pretend to install or own every external tool automatically.

Each adapter must declare:

- tool identity;
- minimum and tested versions;
- detection method;
- required executable or service;
- supported platforms;
- health check;
- optional installation guidance;
- whether network access is needed;
- whether the tool executes third-party code.

## 8. `doll doctor`

`doll doctor` is the main environment diagnosis command.

It must be safe, local, and non-destructive by default.

### 8.1 Core checks

- Python version;
- package version;
- operating system and architecture;
- workspace path;
- workspace identity;
- schema version;
- free disk space;
- state database accessibility;
- filesystem write test inside a temporary workspace area;
- localhost port availability;
- backup inventory;
- migration status;
- configuration parsing;
- permission policy loading;
- audit path availability.

### 8.2 Adapter checks

- runtime availability;
- runtime version;
- local health endpoint;
- known model bindings;
- missing model files;
- checksum status;
- optional OCR, audio, video, and browser tools;
- offline availability where recorded.

### 8.3 Safety checks

- API bind address;
- unexpected remote listener configuration;
- workspace inside repository;
- writable path outside expected scope;
- insecure permissions where detectable;
- missing backup before required migration;
- invalid or stale recovery manifests;
- secret-like values in ordinary config files;
- unverified active model assets.

### 8.4 Report behavior

- Results remain local.
- No automatic upload occurs.
- A shareable report must redact usernames, paths, hostnames, tokens, and private record contents by default.
- The report must distinguish error, warning, information, and unavailable optional capability.

## 9. Startup modes

The system should support explicit startup modes.

### Normal mode

Read and write access to a valid workspace under normal permissions.

### Offline mode

No outbound network activity. Local model, state, documents, artifacts, backup inspection, and supported local tools remain available.

### Read-only recovery mode

Used when:

- schema is unsupported;
- migration failed;
- state integrity is uncertain;
- disk space is critically low;
- the user chooses inspection-only operation.

Read-only recovery mode must permit:

- state inspection;
- export where safe;
- backup verification;
- doctor checks;
- model and runtime inventory;
- audit inspection.

It must not modify authoritative state.

### Degraded mode

The core is valid, but one or more optional capabilities or bindings are unavailable.

The system must report which capabilities are missing.

## 10. Versioning

### 10.1 Product version

Doll uses Semantic Versioning once releases begin.

```text
major.minor.patch
```

Before 1.0, breaking changes may occur but must still be documented and migrated safely.

### 10.2 Schema version

Workspace schema version is independent of product version.

A product release must declare:

- minimum readable schema;
- maximum readable schema;
- writable schema;
- available migrations;
- downgrade limitations.

### 10.3 Package format versions

Doll State Packages, backups, and recovery kits have explicit format versions independent of the workspace schema.

## 11. Update policy

There is no silent self-update.

The initial product does not perform automatic background update checks.

A manual update flow may:

1. identify current and target version;
2. show release notes and compatibility information;
3. inspect schema changes;
4. identify required external-tool changes;
5. create and verify a pre-update backup;
6. stage the new package;
7. run tests or doctor checks;
8. migrate only after explicit approval;
9. verify startup;
10. retain the previous version until success.

## 12. Update sources

The system must not rely on one proprietary update server.

Possible future sources:

- GitHub releases;
- Python package index;
- user-provided local archive;
- retained offline release archive;
- trusted mirror.

All update sources must preserve version and integrity metadata.

## 13. Migration contract

A migration is a controlled transformation of authoritative state.

### Required properties

- versioned migration ID;
- declared source and target schema;
- preconditions;
- pre-migration verified backup;
- dry-run or plan where practical;
- staged execution;
- post-migration validation;
- explicit success or failure;
- migration record;
- rollback or restore path.

### Migration order

```text
inspect
  -> backup
  -> verify backup
  -> stage migration
  -> validate staged state
  -> commit
  -> doctor
  -> mark success
```

### Failure

On migration failure:

- stop writes;
- preserve the original state;
- record failure;
- enter read-only recovery if needed;
- offer restore from the pre-migration backup;
- do not claim the update succeeded.

### Irreversible migration

Requires:

- dedicated specification;
- explicit user warning;
- verified backup;
- export path to a documented prior format where practical;
- no automatic execution during ordinary startup.

## 14. Application rollback

Application rollback and state rollback are separate.

### Application rollback

Reinstall or start the previous doll version.

### State rollback

Restore a previous workspace backup or migration snapshot.

The system must not automatically roll state backward merely because the application version is rolled back.

The previous version may open only schemas it declares compatible.

## 15. Backup policy

Backups are part of the product contract.

### Backup types

- state backup;
- full workspace backup;
- recovery backup;
- pre-migration backup;
- pre-update backup.

### Required metadata

- backup ID;
- workspace ID;
- state revision;
- schema version;
- product version;
- backup format version;
- creation time;
- included and excluded categories;
- encryption state;
- file count;
- total size;
- checksums;
- verification result.

### Completion rule

A backup is not complete until its manifest and checksums are written and verified.

## 16. Backup verification

Verification must be available independently of restoration.

Verification checks:

- archive readability;
- manifest validity;
- checksum validity;
- expected files present;
- workspace identity present;
- schema metadata present;
- restricted-asset references clear;
- encryption metadata valid where applicable;
- no path traversal entries;
- no unexpected executable content in state-only packages.

Verification does not prove that every future runtime can use every retained model asset. Runtime compatibility remains separate.

## 17. Restore policy

Restore must target a user-selected empty or controlled workspace location.

Required flow:

```text
select backup
  -> verify backup
  -> inspect target
  -> show workspace identity and version
  -> stage extraction
  -> reject unsafe paths
  -> validate state
  -> migrate only if explicitly approved
  -> atomically activate target
  -> run doctor
  -> record restore result
```

### Conflict behavior

The system must not silently restore over a newer active workspace.

Supported initial strategies:

- restore to a new directory;
- replace only after explicit confirmation and backup of the target;
- inspect without activation.

Record-level merge is deferred unless separately specified.

## 18. Offline Recovery Kit

The Offline Recovery Kit is intended to make an installed environment reconstructable without depending on the continued availability of every upstream service.

### Required contents or references

- Doll State backup;
- backup verification data;
- doll source revision or release identifier;
- product package or retrieval instructions;
- dependency lockfile;
- Python version;
- operating-system and architecture summary;
- runtime manifests;
- model manifests;
- model checksums;
- selected model assets where legally and technically permitted;
- selected runtime installers where legally and technically permitted;
- configuration with secrets removed;
- restore instructions;
- validation commands;
- known limitations.

### Kit classes

#### Metadata-only kit

Contains state, manifests, checksums, and instructions but not large third-party assets.

#### Selected-assets kit

Contains user-selected model and runtime assets where permitted.

#### Full personal recovery kit

Contains the maximum user-retained environment needed for offline reconstruction, subject to storage, platform, and license constraints.

### Public distribution rule

The public repository does not redistribute third-party model weights or installers merely because a personal recovery kit can contain them.

## 19. Recovery from upstream disappearance

If a model distribution site disappears:

- use locally retained verified assets;
- retain source and license records;
- permit local-file import into a replacement installation;
- do not require the old source to validate an already recorded checksum.

If a package source disappears:

- use a retained release archive or source revision;
- use the dependency lockfile;
- use retained installation instructions;
- preserve the workspace independently of package installation.

If the preferred UI disappears:

- use the CLI and local API recovery path.

If active doll development stops:

- installed versions must not expire;
- local startup must not require a hosted service;
- data formats and migration history remain documented;
- the recovery kit must identify the final known-good environment.

## 20. Recovery from hardware loss

A new machine recovery flow should support:

1. install compatible doll version;
2. initialize an empty target location;
3. restore state and authoritative files;
4. register available runtimes;
5. restore or import selected model assets;
6. verify checksums;
7. select compatible model bindings;
8. run doctor;
9. enter Lite degraded mode if Heavy hardware is unavailable;
10. retain the original workspace ID and record the restored instance.

A new machine may use different absolute paths, runtime versions, or model variants. The durable state must remain readable.

## 21. Cross-operating-system recovery

Cross-OS restoration is a product goal for authoritative state and managed files.

The system must:

- store managed paths relatively;
- avoid OS-specific filenames;
- normalize text encoding;
- avoid storing shell commands as required recovery steps;
- separate credential-store references from ordinary state;
- allow runtime and model bindings to be re-established on the destination OS.

Cross-OS recovery does not guarantee that the same model binary or runtime build works on every platform.

## 22. Runtime recovery

A runtime change must not require state migration.

Runtime recovery flow:

```text
install or locate runtime
  -> create RuntimeManifestRecord
  -> health check
  -> map local assets
  -> validate model load
  -> create candidate binding
  -> test
  -> activate or retain old binding
```

## 23. Disk-space and resource protection

Before update, migration, backup, restore, model acquisition, or large extraction, the system must estimate required temporary and final space.

If space is insufficient:

- stop before modifying authoritative state;
- report the requirement;
- offer cache cleanup suggestions;
- do not delete authoritative data automatically;
- preserve the last valid backup.

## 24. Locking and concurrent operations

The initial single-user design still requires operation locks.

Mutually exclusive operations include:

- migration;
- restore activation;
- workspace identity change;
- model binding activation;
- full backup snapshot finalization;
- application update finalization.

A stale lock must be diagnosable and recoverable through a management command, not silently ignored.

## 25. Offline startup requirements

After installation of required local components, offline startup must not attempt:

- account validation;
- license-server access;
- telemetry;
- hidden update checks;
- model downloads;
- cloud-provider discovery;
- web retrieval.

Offline startup must:

- open the workspace;
- validate schema compatibility;
- inventory local bindings;
- identify degraded capabilities;
- permit local state and artifact access;
- permit local conversation when a valid local binding exists.

## 26. CI strategy

CI must use an OS matrix including:

- macOS;
- Windows;
- Ubuntu Linux.

Initial CI checks:

- package installation;
- import and CLI startup;
- path handling;
- workspace initialization;
- SQLite creation and migration;
- backup and restore using synthetic fixtures;
- local API bind configuration;
- permission and boundary tests;
- mocked runtime-adapter contract;
- missing optional dependency behavior;
- generated specification checks when added.

CI must not download or run large models.

## 27. Real-machine validation

Real-machine testing must record:

- operating system version;
- architecture;
- CPU;
- RAM;
- GPU and VRAM if used;
- filesystem type where relevant;
- runtime version;
- model variant;
- test duration;
- observed memory and disk use;
- sleep and restart behavior where tested.

Heavy cannot be declared stable using mocks alone.

## 28. Installation and recovery acceptance tests

Future tests must include:

- initialize workspace outside repository;
- reject unsafe workspace path;
- core starts without optional tools;
- doctor reports missing optional tools without crashing;
- offline startup produces no network request;
- update cannot proceed without required backup;
- failed migration preserves original state;
- previous application version is retained until update success;
- verified backup restores to an empty workspace;
- corrupt backup is rejected;
- restore rejects path traversal entries;
- restore refuses silent overwrite of newer workspace;
- cross-platform export uses portable paths;
- missing Heavy hardware results in Lite-compatible degraded mode;
- missing UI still permits CLI and API recovery;
- missing source site does not invalidate retained model assets;
- recovery kit identifies omitted third-party assets;
- shareable doctor report redacts personal paths and secrets.

## 29. Deferred work

Deferred:

- native installers;
- automatic updater;
- Docker images;
- signed release infrastructure;
- remote backup services;
- cross-device synchronization;
- mobile recovery;
- enterprise deployment;
- automatic record-level merge restore;
- fully self-contained bootable recovery media;
- guaranteed support for every Linux distribution;
- hardware purchase selection.

## 30. Acceptance criteria

This specification is acceptable when subsequent implementation can meet these conditions:

- macOS, Windows, and Linux are designed from the start rather than ported after completion;
- CI and real-machine support claims remain distinct;
- the core can start without optional dependencies;
- installation does not hide private data inside the repository;
- updates are manual and recoverable;
- schema migration requires a verified backup;
- failed migration preserves the prior state;
- backup verification and restoration are separate tested operations;
- recovery can target an empty workspace;
- Offline Recovery Kits document missing restricted assets;
- an installed version does not expire when upstream development stops;
- Heavy unavailability degrades to a compatible local profile rather than destroying state.
