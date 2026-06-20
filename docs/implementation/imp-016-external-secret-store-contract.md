# IMP-016 — External Secret-Store Contract

## Status

Phase 3 implementation following IMP-015.

## Purpose

IMP-016 defines the replaceable boundary between Doll and an operating-system or compatible external secret store.

The contract makes availability, lock state, user-presence requirements, lifecycle semantics, cancellation, timeout, stable references, transient material ownership, and failure isolation explicit before any platform adapter or Credential Broker is introduced.

The contract is authoritative. A future macOS Keychain, Windows Credential Manager, Linux Secret Service, or compatible adapter must conform to it rather than defining its own Doll-facing behavior.

## Scope

The implementation adds:

- `SecretStoreAdapter`, a runtime-checkable protocol;
- `SecretStoreRegistry`, an immutable adapter registry that may be empty;
- `ExternalSecretStore`, the failure-isolating lifecycle boundary;
- closed availability, lock-state, user-presence, operation, completion, and failure enums;
- bounded `SecretStoreRequest` and `SecretStoreAdapterContext` records;
- transient `SecretMaterial` ownership;
- non-secret operation and lookup result records;
- synthetic conformance, malformed-adapter, cancellation, timeout, and exceptional-path tests.

It does not add a real secret-store adapter or a credential-use path.

## Adapter identity and registry

Each adapter has one stable `adapter_class` matching the closed identifier syntax already used by `SecretReferenceMetadata`.

`SecretStoreRegistry`:

- validates structural conformance to `SecretStoreAdapter`;
- validates adapter-class syntax;
- rejects duplicate classes;
- stores adapters behind an immutable mapping;
- permits zero adapters;
- performs no operating-system discovery, import, prompt, filesystem read, or network request.

An empty registry is a valid core configuration. It reports `adapter_not_configured` for the requested class and does not prevent non-secret Doll startup or state inspection.

The registry does not make an adapter implementation trustworthy beyond the narrow contract. The boundary rechecks adapter identity and normalizes malformed status and return values.

## Non-secret status contract

`SecretStoreStatus` reports only:

- adapter class;
- availability: `available` or `unavailable`;
- lock state: `unlocked`, `locked`, `unknown`, or `not_applicable`;
- user-presence capability: `none`, `optional`, `required`, or `unknown`;
- a sorted unique tuple of supported lifecycle operations;
- an optional closed failure code for unavailable status.

An unavailable status:

- must carry only `adapter_not_configured`, `adapter_failure`, or `store_unavailable`;
- must advertise no operations;
- must report lock state and user-presence state as `unknown`.

Status exceptions, adapter-class mismatches, and malformed status objects become the same non-secret `adapter_failure` status. Raw adapter exception text is discarded.

## Stable SecretReference behavior

Every lifecycle operation requires an exact, revalidated `SecretReferenceMetadata` instance.

The boundary:

- revalidates the record through the IMP-013 closed metadata validator;
- selects the adapter only from `store_adapter_class`;
- uses `reference_id` as the stable external key;
- never accepts an adapter-selected replacement ID;
- rejects forged, subclassed, malformed, or internally inconsistent references;
- rejects create for rotated or revoked references;
- rejects non-delete operations for revoked references;
- permits delete to attempt cleanup of a revoked reference.

The SecretReference remains non-secret metadata. The external value is never added to the reference or returned in ordinary result metadata.

## Lifecycle operations

The protocol defines:

- `create(reference, material, context)`;
- `replace(reference, material, context)`;
- `lookup(reference, context)`;
- `revoke(reference, context)`;
- `delete(reference, context)`.

Adapters return no identifier, metadata, or success message for mutating operations. Successful lookup returns only a `SecretMaterial` object to the trusted boundary.

The boundary returns a non-secret `SecretStoreOperationResult` containing:

- operation;
- stable reference ID;
- adapter class;
- success state;
- closed failure code;
- completion certainty.

Successful operations are always `confirmed`. Failed operations are either:

- `not_completed`, when the boundary knows no accepted operation completed; or
- `unknown`, when an adapter may have performed a mutating operation before timeout, cancellation, or failure became visible.

This prevents a late or ambiguous mutating result from being represented as a definite non-event.

## Transient secret material

`SecretMaterial` is the only contract type that may carry a secret value.

It:

- owns a private `bytearray` copy;
- accepts only bytes-like input;
- rejects empty values;
- is limited to 65,536 bytes;
- exposes only a read-only borrowed `memoryview` inside an explicit context;
- has a constant redacted `str` and `repr`;
- supports context-managed closure;
- performs best-effort in-place zero filling when closed;
- rejects access after closure.

Create and replace consume and close their input material on every path, including validation failure, missing adapter, unavailable or locked store, cancellation, timeout, adapter failure, and success.

Lookup material is returned only after a successful, in-deadline, non-cancelled operation. Late, cancelled, closed, malformed, or failed lookup material is closed before a non-secret failure is returned.

Best-effort zero filling is not a secure-erasure guarantee. Python, the caller, an adapter, the operating system, swap, crash dumps, copy-on-write storage, or a native library may retain other copies outside the owned buffer. The contract minimizes lifetime and ownership; it does not invent cryptography or claim complete memory erasure.

## User presence

A request declares one policy:

- `forbid`: the operation must not trigger user-presence interaction;
- `allow`: the adapter may use user presence when its platform requires it;
- `require`: the operation must use an adapter capable of user-presence interaction.

The boundary compares that policy with the adapter status before invoking the lifecycle operation.

It returns:

- `user_presence_required` when interaction would be required but the caller forbids it;
- `user_presence_unavailable` when the caller requires interaction but the adapter cannot provide it.

IMP-016 does not itself display a prompt or treat operating-system approval as Doll capability confirmation. Future platform adapters implement the operating-system interaction; future Credential Broker and capability work determine whether the operation is authorized.

## Cancellation and timeout

Each request includes:

- a bounded operation ID;
- a timeout greater than zero and no more than 300 seconds;
- a cooperative cancellation token;
- a user-presence policy.

The boundary converts the timeout to a monotonic deadline and passes the deadline and cancellation token to the adapter.

Checks occur:

- before adapter selection;
- after status probing;
- after lookup;
- after mutating operations.

The contract is cooperative. Pure Python cannot forcibly interrupt a blocking operating-system API safely. A conforming adapter must honor the supplied deadline and cancellation token where the platform permits. If an adapter returns after the deadline, lookup material is discarded and mutating completion becomes `unknown`.

There is no automatic retry loop and therefore no repeated unbounded user-presence prompting.

## Failure normalization

Adapters may raise `SecretStoreAdapterFailure` with one closed code and non-success completion certainty.

Accepted failure codes are:

- `adapter_not_configured`;
- `adapter_failure`;
- `already_exists`;
- `cancelled`;
- `invalid_reference_state`;
- `locked`;
- `not_found`;
- `permission_denied`;
- `reference_revoked`;
- `store_unavailable`;
- `timeout`;
- `unsupported_operation`;
- `user_presence_required`;
- `user_presence_unavailable`.

Unknown adapter exceptions, malformed return values, identity mismatches, and status failures are normalized to `adapter_failure` without including raw exception text, platform error text, paths, account names, usernames, hostnames, or secret values.

IMP-016 does not map platform-specific numeric error codes because no platform adapter is added. Each future adapter must map its native errors into this closed set before crossing the contract boundary.

## Audit and logging

IMP-016 adds no audit write and no logger configuration. It defines only non-secret status and result objects suitable for later IMP-017 audit integration.

The following must never be passed to audit or logging:

- `SecretMaterial` contents;
- borrowed memory views;
- raw platform exception text;
- raw operating-system prompt or account details;
- adapter-private metadata.

The public transient-material representation is constant, and normalized failure objects contain only closed codes.

## Failure isolation and startup behavior

Secret-store absence or failure is isolated from the non-secret core.

Doll can still:

- start;
- open and inspect ordinary state;
- verify packages and backups;
- restore non-secret state;
- inspect SecretReference metadata;
- report that the configured adapter is unavailable.

A secret-bearing operation fails closed when the adapter is absent, unavailable, locked, malformed, cancelled, timed out, or unable to satisfy user-presence policy.

No fallback reads an environment variable, plaintext file, browser store, wallet, configuration field, clipboard, or cloud service.

## Platform, package, backup, restore, and migration effects

- macOS, Windows, and Linux: contract and synthetic tests only; no native adapter or platform dependency.
- Dependencies: standard library and existing Doll modules only.
- Network: none.
- Filesystem: none.
- Ordinary Doll State: unchanged; only validated SecretReference metadata remains permitted.
- Database schema: unchanged.
- State package format: unchanged.
- Export and import: unchanged; references remain reference-only.
- Backup and restore: unchanged; references may round-trip, values remain external.
- Migration: none.
- Custom cryptography: none.
- Model execution: none.
- Credential Broker: none; IMP-017 will consume this boundary.
- Phase 4A and Phase 4B: no implementation introduced.

Restoring or importing a SecretReference does not restore its external value. The target machine must separately have a compatible configured adapter and corresponding external entry. Unavailability remains explicit rather than silently creating a replacement value or changing the reference.

## Acceptance evidence

Permanent synthetic tests prove:

- core construction and safe status reporting with no adapters;
- immutable, duplicate-safe, structurally validated registration;
- exact status and result invariants;
- stable reference use through create, replace, lookup, revoke, and delete;
- create and replace input closure on all tested paths;
- successful lookup ownership and deterministic closure;
- late and cancelled lookup disposal;
- unknown completion for late or cancelled mutation;
- user-presence policy enforcement;
- availability, lock, unsupported-operation, and reference-state denial;
- known failure-code normalization;
- unknown exception isolation without raw exception text;
- malformed status and lookup-return rejection;
- adapter-class mismatch isolation;
- forged reference rejection;
- invalid clock, request, context, material, result, and lookup-object rejection;
- no real secret-store, network, filesystem, cloud, model, capability, confirmation, or broker dependency.
