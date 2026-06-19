# IMP-013 — Secret Classification Policy

## Status

Phase 3 implementation foundation.

## Purpose

IMP-013 makes Doll's secret-storage rule executable before secret detection, logging sanitization, external secret-store adapters, credential brokering, or any model path is added.

The central rule is:

> A sensitivity label does not authorize secret-value persistence.

Ordinary Doll State may contain a validated non-secret `SecretReferenceRecord`. It must not contain the password, token, key, cookie, recovery phrase, authorization header, reversible encoding, or reconstruction hint behind that reference.

## Secret classes

The policy defines the following closed classes:

- `credential`;
- `authentication_material`;
- `cryptographic_key`;
- `session_material`;
- `recovery_material`;
- `personal_sensitive`;
- `unknown_secret`.

Unknown classifications fail closed.

## Credential classes

A SecretReference identifies one credential class without containing its value:

- password;
- API key;
- access token;
- refresh token;
- client secret;
- private key;
- session cookie;
- recovery phrase;
- authorization header;
- other explicitly classified credential.

## Handling matrix

### Secret values

Secret values are denied in:

- ordinary state;
- audit;
- logs;
- exports;
- backups;
- diagnostics;
- model context;
- normal output.

Secret values may exist only:

- as transient input awaiting a bounded accepted path;
- inside a bounded operation;
- in an operating-system or compatible external secret store.

The input and bounded-operation decisions are `transient_only`; they do not authorize persistence, logging, export, or output.

### Secret references

A validated SecretReference is non-secret metadata. In ordinary state, exports, and backups it is explicitly `reference_only`. The referenced value remains external.

### Uncertain payloads

Unknown or uncertain secret-bearing requests are denied. Detection heuristics added by IMP-014 will not weaken this default.

## SecretReference contract

Required fields:

- `reference_id`;
- `credential_class`;
- `store_adapter_class`;
- `label`;
- `status`.

Optional non-secret fields:

- `provider_class`;
- `allowed_operation_scope`;
- `allowed_destination_scope`;
- `created_at`;
- `rotated_at`;
- `revoked_at`.

Unknown fields are rejected. Fields representing values, reversible encodings, authentication material, or value-derived reconstruction hints are rejected explicitly.

The accepted metadata contract is deliberately closed. Arbitrary nested metadata is not permitted.

## Ordinary-state boundary

`validate_ordinary_state_record` enforces two rules:

1. a `secret_reference` record must use `sensitive` or `secret` sensitivity and pass the exact SecretReference metadata validator;
2. any other record marked `secret` is rejected because the label cannot be used as permission to persist a secret value.

`StateRepository.create_record` and `StateRepository.update_record` call this policy before serialization or transaction start. A rejected write therefore cannot create or mutate a record, increment a record revision, increment state revision, or update workspace metadata.

Import, export, backup, diagnostic, detection, sanitization, external-store, and broker-specific enforcement continues in later Phase 3 items. Those paths must preserve this policy and may not weaken the ordinary-state boundary.

## Non-goals

IMP-013 does not:

- scan free text for secrets;
- claim complete secret detection;
- redact logs or errors centrally;
- access macOS Keychain, Windows Credential Manager, or Linux Secret Service;
- retrieve or use a credential;
- grant a capability or confirmation;
- execute a model.

## Acceptance

The tests prove:

- `secret` sensitivity never permits secret values in ordinary state;
- generic create and update operations enforce the policy before committing state;
- rejected secret-bearing creates and updates leave database and workspace revisions unchanged;
- the handling matrix denies secret values in every durable, diagnostic, output, and model-context location;
- external-store and bounded-operation handling remain explicit;
- uncertain classifications fail closed;
- valid reference metadata round-trips deterministically;
- prohibited value fields and reconstruction hints are rejected;
- unknown, malformed, duplicate, and unsafe scope fields are rejected;
- lifecycle timestamps are required when rotated or revoked.
