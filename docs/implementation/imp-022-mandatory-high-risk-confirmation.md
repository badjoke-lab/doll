# IMP-022 — Mandatory High-Risk Confirmation

## Status

Complete in PR #77 for Issue #75.

## Purpose

IMP-022 adds a model-independent confirmation authority for Tier 3 capability requests. A confirmation is a fresh user decision bound to one exact structured operation. It is separate from permission state and cannot make an otherwise invalid capability request acceptable.

The implementation performs no capability execution and introduces no filesystem, network, process, credential, account, financial, or external-service side effect.

## Append-only confirmation ledger

Confirmation state is represented by a closed set of lifecycle events in the existing authoritative append-only audit store:

- `confirmation.issue` records one approved or denied user decision;
- `confirmation.revoke` invalidates a prior decision through a trusted user management path;
- `confirmation.consume` spends an approved decision once inside a future accepted execution boundary;
- `confirmation.preflight` records a secret-safe read-only acceptance or denial check.

This does not treat arbitrary audit text as confirmation. The resolver accepts only exact lifecycle actions with the required target type, target identity, actor class, schema version, fingerprints, risk tier, and bounded metadata. Malformed or contradictory history fails closed.

Using the established audit store preserves confirmation history through the existing state package, state backup, workspace backup, restore, and fresh-process validation paths without introducing a second mutable lifecycle record or a schema migration.

## Exact request binding

A deterministic SHA-256 fingerprint binds confirmation to:

- capability ID and version;
- immutable capability-registry fingerprint;
- operation and optional session identity;
- actor and instruction origin;
- validated arguments;
- target kind and identifier;
- normalized destination;
- complete declared side effects;
- fixed Tier 3 risk;
- permission scope;
- resource limits;
- timeout;
- cancellation identity;
- credential class where applicable.

Any material difference produces a different fingerprint. Fingerprints are descriptive integrity values, not signatures or custom authentication.

Secret-like values are rejected from confirmation fingerprint input. The ledger stores no raw arguments, target contents, URL path or query, credential value, request body, or arbitrary model text.

## Trusted confirmation authority

Only an explicit `user` actor with `user_management_action` origin may issue or revoke confirmation. Models, runtimes, tools, external content, imports, unknown sources, and capability results cannot create approval.

A trusted preview contains bounded secret-safe consequence metadata:

- effect summary;
- whether data leaves the machine;
- target and destination classification without sensitive path or query details;
- material side-effect names;
- credential class and account label without a credential value;
- irreversibility;
- recovery availability and bounded recovery description;
- expiration.

Approvals and denials both remain inspectable. Expired, denied, revoked, consumed, missing, mismatched, and corrupt confirmation states all fail closed.

## Confirmation-aware preflight

`ConfirmedCapabilityPreflightService` retains the IMP-021 boundary for Tier 0 through Tier 2. For Tier 3 it applies, in order:

1. exact registry ID and version;
2. actor and instruction-origin policy;
3. argument schema;
4. target and destination binding;
5. complete side-effect and fixed-risk matching;
6. resource, timeout, and cancellation limits;
7. permission scope and effective permission mode;
8. release availability;
9. network policy where applicable;
10. fresh exact confirmation.

Confirmation is checked only after the other gates pass. It cannot enable an unknown, malformed, prohibited, out-of-scope, unsafe, permission-denied, network-denied, or release-excluded capability.

Preflight never consumes confirmation. Repeated previews and retries therefore do not spend approval. Atomic consumption uses an immediate SQLite transaction and is reserved for a future accepted execution boundary after every applicable gate has passed.

## Audit and failure behavior

Issue, denial, revocation, consumption, and preflight decisions use bounded secret-safe metadata. Required persistence failure returns no authorization and rolls back the state revision. Confirmation lifecycle resolution ignores ordinary preflight events, so repeated preview does not grow or corrupt the lifecycle chain.

## Tests

Synthetic tests cover:

- exact approved confirmation;
- repeated read-only preflight without consumption;
- missing, denied, expired, revoked, consumed, mismatched, and corrupt states;
- material argument, session, cancellation, timeout, resource, credential-class, and registry changes;
- model and external-content attempts to grant confirmation;
- unsafe preview rejection;
- permission and release gates remaining authoritative;
- non-Tier-3 delegation;
- atomic one-time consumption and untrusted-consumer denial;
- audit insertion failure with revision preservation;
- repeated preview beyond the lifecycle event limit;
- state backup, restore, and fresh-process preservation.

## Accepted CI evidence

PR #77 passed:

- dependency-lock verification;
- Ruff lint and formatting;
- strict mypy across `src` and `tests`;
- deterministic generated-specification check;
- 736 tests on Ubuntu, macOS, and Windows;
- 95.04% Linux coverage;
- CLI and module-help checks.

The final PR contains no workflow change or temporary diagnostic file.

## Explicit non-goals

IMP-022 does not add:

- a capability execution adapter;
- model or runtime invocation;
- a live high-risk side effect;
- unrestricted shell or arbitrary commands;
- a credential value path;
- a public confirmation UI;
- a state schema migration;
- a new dependency;
- custom cryptography.

## Known limitations

- There is no live Tier 3 adapter in this slice. The built-in process example remains release-excluded; tests use an immutable synthetic registry variant to prove the confirmation contract.
- The trusted management interface is currently the Python service contract. A later CLI or local UI must preserve the same actor, preview, fingerprint, expiry, and audit rules.
- Confirmation consumption is implemented for the future broker boundary but is not connected to execution because IMP-022 intentionally performs no side effect.
