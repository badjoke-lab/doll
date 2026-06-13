# ADR-004: Release gates require evidence

**Status:** Proposed for acceptance with PR-005  
**Date:** 2026-06-14

## Context

Doll's central claim is continuity across loss, replacement, degradation, and recovery.

Source code, screenshots, normal startup, or a successful demo do not prove continuity. A backup that has never been restored does not prove recoverability. CI does not prove real hardware behavior. A feature that works once does not prove that it survives model replacement, migration, or offline use.

The project needs a consistent rule for deciding when a capability, platform, profile, or release may be described as working.

## Decision

Doll will use evidence-based release gates tied to stable acceptance-test IDs.

A release or capability claim must identify the required evidence level, such as:

- unit;
- integration;
- CI platform;
- real machine;
- manual continuity drill;
- soak;
- community verification.

Blocking tests must pass before the applicable stable claim is made.

The project will distinguish:

- planned;
- implemented;
- CI verified;
- real-machine verified;
- community verified;
- experimental;
- stable for a named release.

The Personal Lite continuity proof is a separate gate from Lite v1.0.

Lite v1.0 requires continuity, recovery, security, platform, and personal-use soak evidence.

Heavy v1.0 additionally requires real Heavy hardware evidence. Mocks and CI cannot satisfy that gate.

## Required interpretations

- Backup creation is not equivalent to verified restore.
- Normal startup is not equivalent to offline continuity.
- A model switch is not successful if Doll State changes unexpectedly.
- CI support is not full platform support.
- An experimental feature does not count toward a stable release gate.
- A blocked test is not a pass.
- A manual waiver cannot override a mandatory Continuity Contract or security requirement without changing the specification.

## Consequences

### Positive

- Public claims remain honest and reproducible.
- Continuity failures are found before release.
- Backup and restore receive equal attention.
- Platform support labels become meaningful.
- Heavy hardware cannot be declared complete from architecture alone.
- Regressions can be tied to stable test IDs.
- Release decisions expose known failures and limitations.

### Negative

- Releases take longer.
- Real-machine drills require manual work.
- Some features remain experimental longer.
- Test records and acceptance reports require maintenance.
- A working demo may still fail the release gate.

## Rejected alternatives

### Release when implementation is complete

Rejected because implementation does not prove recovery, offline operation, or safe degradation.

### Treat CI as sufficient for every platform

Rejected because CI does not test all filesystems, hardware, model runtimes, sleep behavior, thermal behavior, or user installation conditions.

### Use only informal manual testing

Rejected because results would be difficult to reproduce and compare across versions.

### Waive failures to preserve a planned date

Rejected for mandatory continuity and security requirements. Scope may be reduced instead.

## Implementation constraints

- Acceptance tests use stable IDs.
- Results record product version, commit, platform, hardware, runtime, model, and evidence level where applicable.
- Stable releases include an acceptance report.
- Known failures and experimental features are published.
- Test definitions are versioned with the specification.
- Private fixtures may remain local, but public test definitions and synthetic fixtures should cover core behavior.

## Validation

This decision is validated when:

1. the Personal Lite proof has a complete acceptance report;
2. a backup is restored into an empty workspace before the proof passes;
3. offline behavior is tested with network access disabled;
4. model fallback is tested without cloud access;
5. Windows and Ubuntu claims identify CI evidence;
6. macOS claims identify real-machine evidence;
7. Heavy claims cannot pass without recorded Heavy hardware;
8. release documentation lists failures, limitations, and experimental scope.
