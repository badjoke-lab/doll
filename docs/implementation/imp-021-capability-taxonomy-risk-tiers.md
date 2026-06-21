# IMP-021 — Capability Taxonomy and Risk Tiers

## Status

Complete.

## Purpose

IMP-021 adds the model-independent authorization preflight that every future capability execution path must pass before an adapter, runtime, model, tool, filesystem service, network client, process, credential operation, or external service can perform work.

This implementation defines capabilities and decides whether one exact structured request is authorized. It does not execute the capability or perform any live side effect.

The boundary has five independent sources of truth:

1. an immutable versioned capability registry defines the accepted operation;
2. the registered risk tier and declared side effects cannot be selected or lowered by the caller;
3. the existing `PermissionService` remains the permission source of truth;
4. an explicit outbound-network policy constrains registered network reads;
5. IMP-022 remains the only future source of fresh exact Tier 3 confirmation.

## Immutable versioned registry

`CapabilityRegistry` is constructed from reviewed `CapabilityDefinition` objects and exposes no mutation API. Construction rejects:

- duplicate capability ID and version pairs;
- unsupported registry schema versions;
- excessive definition or argument counts;
- mutable collection fields inside definitions;
- malformed IDs, versions, descriptions, schemas, targets, limits, and policies;
- generic shell, arbitrary-command, permission-changing, risk-changing, policy-changing, registry-changing, and confirmation-changing definitions;
- inconsistent target, side-effect, network, permission, release, and risk combinations.

Definitions are indexed by the exact `(capability_id, capability_version)` pair. An unsupported version is not silently mapped to another version.

The registry exposes a deterministic SHA-256 fingerprint over a canonical JSON representation. Definition order does not affect the fingerprint. The fingerprint is descriptive integrity metadata, not a signature or custom authentication mechanism.

## Fixed risk tiers

The reviewed risk taxonomy is represented by `CapabilityRiskTier`:

- Tier 0: pure computation over provided input;
- Tier 1: bounded managed read or reversible managed creation;
- Tier 2: scoped modification or explicit external read;
- Tier 3: high-risk operation.

A request must repeat the registered tier exactly so a changed or downgraded request is visible and rejected. The registry, not the caller, decides the tier.

Tier 3 remains unavailable in IMP-021. Even a valid permission record, trusted user origin, release-enabled definition, or permissive network policy cannot authorize Tier 3 until IMP-022 supplies fresh exact confirmation. The built-in Tier 3 adapter example is also release-excluded.

## Structured request and complete preflight

`CapabilityRequest` carries the exact request envelope:

- capability ID and version;
- operation and optional session identity;
- actor and instruction-origin class;
- validated arguments;
- target and optional destination;
- declared side effects;
- declared risk tier;
- permission scope;
- requested resource limits;
- timeout;
- cancellation identifier where required.

`CapabilityPreflightService.preflight` performs a complete fail-closed decision before returning an authorized result. It rejects:

- unknown capabilities and unsupported versions;
- malformed request envelopes and argument schemas;
- target-kind or target-identifier mismatch;
- target, argument, permission-scope, or destination substitution;
- omitted, added, or concealed side effects;
- risk-tier mismatch or downgrade;
- missing, undersized, or excessive resource limits;
- timeout and cancellation mismatch;
- release-excluded operations;
- missing, denied, expired, consumed, or interactive permission states;
- network-policy denial and private or localhost literal destinations;
- actor and origin combinations that cannot directly request a capability;
- Tier 3 while the IMP-022 confirmation boundary is unavailable.

The authorized result is only a preflight decision. It contains no executable function, open handle, credential value, network response, subprocess, mutable registry reference, or side-effecting service object.

## Exact target and permission binding

The initial binding modes prevent a permission for one object from being reused for another:

- `none` requires the exact permission scope `{"kind": "none"}`;
- `record_identity` binds the request argument, state-record target, and permission `record_id`;
- `project_artifact` binds project ID, artifact name, canonical managed target, and project permission scope;
- `destination_host` binds the explicit URL, normalized destination, hostname, and destination-host permission scope.

Permission scope is therefore not only looked up: it is checked against the request's actual target and destination before `PermissionService.resolve` is called.

## Permission handling

`PermissionService.resolve` remains the authoritative permission lookup. IMP-021 does not create, widen, update, archive, reactivate, or consume permission records.

The effective modes are handled as follows:

- `denied`: deny;
- missing, expired, consumed, or archived: deny;
- `ask`: deny preflight because a trusted user action is still required;
- `allow_once`: authorize preflight without consuming the record;
- `scoped`: authorize only after exact capability and scope matching.

Allow-once consumption must happen only inside a later accepted execution boundary after all applicable gates pass. A preflight retry, preview, or failed audit must not spend it.

## Actor and instruction-origin handling

Actor and origin must form one of the accepted explicit pairs. System policy, current user instruction, trusted user-management action, and model proposal may submit a structured request under their corresponding actor identities.

External content, imported data, tool results, runtime output, durable policy text, and unknown-origin content cannot directly request a capability. They may inform a higher-level task, but they cannot become permission, confirmation, registry, risk, network, or execution authority.

A model proposal remains an untrusted proposal. Passing IMP-021 does not let the model change definitions, permissions, policy, confirmation, or network controls.

## Network boundary

The initial network contract supports only an explicit HTTP or HTTPS URL registered by a dedicated capability. Preflight normalizes the destination and checks:

- exact destination equality with the target and URL argument;
- supported scheme;
- hostname syntax;
- absence of user information and fragments;
- absence of unsupported ports;
- private-address, loopback, link-local, multicast, unspecified, reserved, localhost, and local-suffix literal restrictions;
- exact allowlisted scheme and host where an outbound policy is supplied;
- response-byte and timeout limits.

Network-disabled policy denies every network capability. No network request, DNS lookup, redirect, or response read occurs in IMP-021.

## Secret-safe audit behavior

Every structurally valid preflight request produces one secret-safe audit event:

- `capability.preflight.authorized` with result `success`; or
- `capability.preflight.denied` with result `denied`.

Audit metadata contains only bounded identifiers, fixed classification fields, scope kind, side-effect names, and denial reason. It excludes raw arguments, target contents, URL paths or queries, request bodies, credential material, and arbitrary caller text.

If required audit persistence fails, preflight raises `CapabilityAuditError` and returns no authorization decision. Authorization therefore cannot succeed without its required audit record.

Malformed requests that cannot be safely identified are rejected before audit rather than being converted into unsafe audit content.

## Built-in registry

`build_builtin_capability_registry` defines the initial conservative examples:

- `compute.transform` version 1.0, Tier 0, provided-data transformation, no side effect;
- `state.read` version 1.0, Tier 1, one explicitly bound state-record read;
- `artifact.create` version 1.0, Tier 1, create-new managed artifact inside one project scope;
- `network.fetch_url` version 1.0, Tier 2, one explicit bounded URL retrieval;
- `adapter.fixed_process.example` version 1.0, Tier 3, fixed-adapter shape, release-excluded.

The Tier 3 example demonstrates that a fixed adapter can be classified without introducing a generic command runner or executable implementation.

## Tests

Synthetic tests cover:

- deterministic fingerprints and construction-order independence;
- immutability and duplicate registration;
- all four risk tiers;
- unsupported versions and unknown capability IDs;
- argument, target, destination, binding, side-effect, and risk mismatch;
- resource, timeout, and cancellation limits;
- release exclusion and mandatory Tier 3 denial;
- denied, ask, allow-once, scoped, expired, consumed, archived, and missing permission states;
- no allow-once consumption during preflight;
- actor and origin pairing and data-origin denial;
- network-disabled, allowlisted, private, localhost, port, user-information, fragment, and malformed destinations;
- secret-safe authorized and denied audits;
- fail-closed audit persistence failure;
- mutable or malformed registry definitions;
- unrestricted-shell, arbitrary-command, authority-changing argument, hidden-upload, and unsafe-process rejection.

The tests use synthetic repository fixtures and policy objects. They invoke no model, runtime, tool, filesystem mutation, network request, process, credential store, or external service.

## Explicit non-goals

IMP-021 does not add:

- a capability execution adapter;
- model or runtime invocation;
- live filesystem, network, process, credential, or external-service access;
- IMP-022 confirmation records or confirmation UI;
- permission mutation or allow-once consumption;
- a schema migration;
- a new dependency;
- unrestricted shell or arbitrary command execution;
- custom cryptography.

## Known limitations

- The initial argument schema is deliberately small and supports text, integer, boolean, and string-list fields rather than a general JSON Schema implementation.
- The built-in registry is a conservative seed, not the final catalog of useful capabilities.
- URL preflight blocks private and local literal hosts, but performs no DNS resolution. A future execution adapter must revalidate resolved and redirected destinations immediately before and during network use to address DNS rebinding and redirect changes.
- Preflight authorization does not guarantee successful or safe execution. Future adapters must add execution isolation, postconditions, cleanup, cancellation, and failure-preserving audit while preserving this boundary.
- Tier 3 remains categorically unavailable until IMP-022 is implemented and accepted.
