# IMP-017 — Credential Broker

## Status

Phase 3 implementation following IMP-016.

## Purpose

IMP-017 implements the only normal runtime boundary permitted to use an externally stored credential.

The broker accepts a validated non-secret `SecretReferenceMetadata`, validates one exact credential-bearing operation, obtains a transient value through the IMP-016 external secret-store contract, lends a read-only view to one registered trusted handler, closes the material, and returns only a bounded non-secret result.

No model, ordinary caller, audit event, log, exception, result, state record, export, backup, diagnostic, environment variable, command string, or temporary file receives the stored value.

## Scope

The implementation adds:

- `CredentialUseIntent`, the exact non-secret operation declaration;
- `CredentialAuthorizationAuthority`, an in-memory trusted-management issuer for exact, expiring, one-time grants;
- `CredentialAuthorizationGrant`, a non-secret grant token;
- `CredentialHandlerRegistry`, an immutable exact-version registry;
- `CredentialOperationHandler`, the narrow trusted execution contract;
- `CredentialHandlerContext` and `CredentialHandlerResult`;
- `CredentialBroker`, the failure-isolating execution boundary;
- `CredentialBrokerResult`, the only ordinary caller result;
- `CredentialAuditEvent` and `CredentialAuditSink`;
- `AuditServiceCredentialAuditSink`, the adapter to the IMP-015 secret-safe audit service;
- synthetic success, denial, replay, expiry, mismatch, timeout, cancellation, malformed-handler, secret-store, audit-failure, and exceptional-path tests.

It does not add a real provider operation, real network access, a model path, or a general Capability Broker.

## Exact operation declaration

A `CredentialUseIntent` contains only non-secret fields:

- operation ID;
- capability ID and exact integer version;
- actor type and optional bounded actor ID;
- validated SecretReference;
- exact operation scope;
- exact destination host with optional port;
- fixed `tier3` risk;
- bounded timeout;
- user-presence policy;
- cooperative cancellation token.

The broker rejects malformed or forged intent objects before any secret-store lookup or handler execution.

Credential-bearing external operations are Tier 3 under the accepted threat model. The caller cannot request Tier 0, Tier 1, or Tier 2. A handler that does not declare Tier 3 cannot be registered.

## Scope and destination behavior

The selected operation scope must be an exact member of `SecretReferenceMetadata.allowed_operation_scope`.

The selected destination must be an exact member of `SecretReferenceMetadata.allowed_destination_scope`.

IMP-017 deliberately provides no wildcard expansion. A scope containing `*` cannot be selected by an intent or handler. A stored wildcard does not authorize a concrete operation or destination because exact membership is required.

The initial destination syntax is a bounded host name with an optional valid TCP port. Schemes, paths, query strings, fragments, credentials in URLs, arbitrary recipients, and free-form destination descriptions are outside this contract.

## Authorization grant

Before execution, a trusted user-controlled management path must issue a `CredentialAuthorizationGrant` through `CredentialAuthorizationAuthority`.

The authority keeps the authoritative grant state in memory. A grant is:

- bound to the complete intent signature, including operation, capability, actor, exact SecretReference snapshot, scope, destination, risk, timeout, user-presence policy, and cancellation-token identity;
- bounded to a maximum lifetime of 300 seconds;
- one-time;
- consumed atomically under a lock;
- rejected when missing, forged, mismatched, expired, or already consumed.

A grant object is not authoritative by itself. The authority must contain the matching live state. Constructing or modifying a grant object does not create approval.

The IMP-017 authority is intentionally narrow, in-memory, and replaceable. It is not the general persistent ConfirmationRecord model. IMP-021 and IMP-022 must later provide the versioned capability registry and general mandatory high-risk confirmation system. They may replace the grant issuer, but must not weaken exact binding, expiry, one-time use, or trusted-management authority.

An initial audit-write failure occurs before grant consumption so the same still-fresh grant may be retried after audit availability is restored. Once authorization is consumed, a later secret-store or handler failure does not restore it.

## Handler registry

The broker never accepts a caller-supplied function.

`CredentialHandlerRegistry` is immutable and keyed by exact `(capability_id, capability_version)`.

Every registered handler must expose:

- exact capability ID;
- exact capability version;
- exact operation scope;
- fixed Tier 3 risk;
- one `execute(context, credential_view)` method.

Duplicate registrations, wildcard scopes, structural mismatches, mutable identity changes, and risk downgrades fail closed.

The registry is a narrow credential-operation dispatch table, not the general capability taxonomy required by IMP-021.

## Transient credential use

The broker retrieves the value only through `ExternalSecretStore.lookup`.

On successful lookup:

1. the broker owns the `SecretStoreLookupResult` context;
2. it verifies cancellation and the broker-wide monotonic deadline;
3. it constructs a bounded `CredentialHandlerContext`;
4. it borrows a read-only `memoryview` from `SecretMaterial`;
5. it calls exactly one registered handler;
6. the borrowed view is released;
7. the lookup result closes and best-effort wipes its owned material;
8. only a `CredentialBrokerResult` leaves the boundary.

The handler can technically copy bytes because it is inside the trusted computing base for that one accepted contract. The protocol, lifetime control, review, and tests minimize exposure; Python cannot prevent a malicious trusted handler from copying memory. A handler requiring direct long-lived credential possession is incompatible with this contract.

No environment-variable injection, command-line construction, plaintext file, temporary file, clipboard, browser store, wallet, or fallback credential source is provided.

## Timeouts and cancellation

The intent timeout is greater than zero and no more than the IMP-016 maximum of 300 seconds.

The broker uses one monotonic deadline across:

- preflight;
- authorization consumption;
- secret-store lookup;
- handler execution;
- result processing.

The remaining time is passed to the secret-store lookup. The same cooperative cancellation token is passed through the broker, secret store, and handler context.

Cancellation or timeout before handler invocation returns `not_started`. Cancellation, timeout, malformed output, or exception after handler invocation returns `unknown` unless the handler already returned a bounded completed result and only terminal audit writing failed.

Python cannot safely force-stop a blocking native or external operation. Handlers and secret-store adapters must honor the deadline and token where their platform permits.

## Bounded results

A `CredentialBrokerResult` contains only:

- operation ID;
- capability ID and version;
- SecretReference ID;
- operation scope;
- destination;
- success state;
- closed failure code;
- completion certainty;
- optional bounded handler result code.

It never contains:

- secret material;
- headers;
- cookies;
- tokens;
- passwords;
- request or response bodies;
- raw exception text;
- arbitrary handler metadata;
- account dumps;
- environment data;
- command strings.

Completion is one of:

- `not_started`: the handler did not begin;
- `completed`: the handler returned a bounded completed result, or a completed result was followed by terminal audit failure;
- `unknown`: the handler may have produced a side effect before cancellation, timeout, exception, or malformed output became visible.

A failed broker result may therefore truthfully report `completed` or `unknown`. Failure must not be represented as proof that no side effect occurred.

## Failure normalization

The broker uses a closed failure set covering:

- authorization missing, mismatch, expiry, and replay;
- inactive or revoked reference state;
- operation and destination scope denial;
- handler absence, identity mismatch, bounded denial, malformed result, and exception;
- external secret-store absence, lock, denial, failure, timeout, cancellation, and user-presence failure;
- audit failure.

Raw adapter, handler, audit, clock, operating-system, or provider exception text is not returned.

## Audit behavior

The broker requires a `CredentialAuditSink`.

It writes:

1. a secret-free `credential.use.attempt` event before authorization consumption, secret lookup, or handler execution;
2. a secret-free `credential.use.result` event for success, denial, failure, cancellation, partial or unknown completion.

Audit fields are restricted to non-secret operation identity, actor, capability, SecretReference ID, credential class, exact scope, exact destination, Tier 3 risk, closed result, failure code, completion, and bounded handler result code.

If the attempt event cannot be written:

- no grant is consumed;
- no secret lookup occurs;
- no handler runs;
- the broker returns `audit_failure` with `not_started`.

If the terminal event cannot be written after execution:

- the broker returns `audit_failure`;
- the original completion certainty is preserved;
- a completed or possibly completed external side effect is not hidden.

The audit sink itself receives no SecretMaterial or borrowed view.

## Model and ordinary-caller exclusion

The broker API does not accept a raw secret value and does not expose a lookup result.

A future model may propose the non-secret identity of an operation after the Phase 3 gate, but it must not receive:

- the authorization authority;
- the handler registry;
- the external secret-store object;
- SecretMaterial;
- a borrowed credential view;
- AuditService mutation authority.

The model or ordinary caller receives only the bounded `CredentialBrokerResult`.

## Platform, data, continuity, and dependency effects

- macOS, Windows, and Linux: synthetic contract tests only; no native secret-store or provider dependency.
- Dependencies: standard library and existing Doll modules only.
- Network: none.
- Filesystem: none.
- Ordinary Doll State: unchanged.
- Database schema: unchanged.
- State package format: unchanged.
- Export and import: unchanged.
- Backup and restore: unchanged.
- Migration: none.
- Custom cryptography: none.
- Model execution: none.
- Real capability execution: none.
- Real credential collection: none.
- Phase 4A and Phase 4B: no implementation introduced.

Authorization grants are intentionally not durable state and do not survive restart, export, backup, restore, or transfer. A restarted process requires a new trusted-management authorization.

## Acceptance evidence

Permanent synthetic tests prove:

- successful use returns no secret and closes transient material;
- the handler receives a read-only view that is released after execution;
- missing, forged, mismatched, expired, and consumed grants fail closed;
- initial audit failure prevents execution and preserves the unconsumed grant;
- terminal audit failure preserves truthful completed or unknown side-effect state;
- exact operation and destination scope enforcement;
- wildcard widening is unavailable;
- inactive and forged SecretReferences fail closed;
- missing and mutated handlers fail closed;
- absent, locked, exceptional, and malformed secret-store paths fail closed;
- handler denial, malformed result, exception, timeout, and cancellation are bounded;
- raw exception text and synthetic secret values do not enter ordinary results or audit events;
- no real network, filesystem, provider, model, capability registry, persistent confirmation, platform secret store, or custom cryptography is required.
