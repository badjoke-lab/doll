# IMP-014 — Bounded Secret Detection and Redaction

## Status

Phase 3 implementation following IMP-013.

## Purpose

IMP-014 provides a reusable, model-independent best-effort detector for explicitly supplied text and a deterministic redaction layer for user-visible errors and structured diagnostics.

It does not claim perfect secret detection. It does not grant permission to search for secrets.

## Boundary

The detector accepts only a caller-supplied Python string. It does not:

- walk directories;
- read files;
- inspect environment variables;
- access browsers, wallets, keychains, credential stores, or application databases;
- make network requests;
- inspect process memory;
- retrieve a SecretReference value.

Future conversation, attachment, configuration, and import adapters may pass bounded extracted text to this API after their own path, archive, size, content-type, provenance, and instruction-origin checks. IMP-014 does not implement those adapters or canonical portability records.

## Structured findings

A `SecretFinding` records only:

- finding kind;
- confidence class;
- detector ID;
- start and end offsets within the scanned prefix.

It never records the matched value, a value hash, a prefix, a suffix, last characters, or another reconstruction hint.

Overlapping detector results are normalized into deterministic, non-overlapping ranges before redaction.

## Resource limits

Default limits are:

- 65,536 input characters scanned;
- 64 normalized findings returned.

Configured limits also have hard upper bounds. The API never silently scans an unbounded suffix.

When the input exceeds the scan limit, the redaction API returns only:

```text
[UNSCANNED_CONTENT_OMITTED]
```

It does not return the inspected prefix or the unscanned suffix. A secret may cross the scan boundary, so no portion of an over-limit input is considered safe to echo.

When the finding limit is reached, the redaction API returns only:

```text
[REDACTION_FINDING_LIMIT_REACHED]
```

It does not return any portion of the original text, because unreported findings could otherwise remain visible.

Structured diagnostics additionally limit recursion depth and aggregate item count. Binary values are omitted without decoding, and unknown objects are represented only by type name rather than `repr()` or `str()` output.

## Initial detector set

The initial bounded patterns cover synthetic examples of:

- Authorization Bearer and Basic values;
- common credential assignments such as password, API key, access token, refresh token, client secret, session token, and private key fields;
- selected known token shapes;
- PEM-style private-key blocks;
- Cookie and Set-Cookie header values;
- labeled seed, recovery, and mnemonic phrases;
- email addresses;
- labeled telephone numbers;
- common macOS, Linux, and Windows home-directory paths in diagnostic text.

The pattern set is versioned internally through stable detector IDs.

## User-visible error boundary

Existing CLI paths that included exception text now pass the exception message through `redact_exception_text` before display. Existing command prefixes and exit codes remain unchanged.

CLI paths already exposing only an exception class remain unchanged. Central audit and logging enforcement is deliberately reserved for IMP-015.

## False positives

Best-effort detection may redact non-secret text, including:

- example token strings that resemble real provider tokens;
- email addresses intentionally included in ordinary content;
- labeled telephone numbers;
- text that resembles a credential assignment;
- paths under conventional user home directories;
- JWT-shaped non-authentication data.

Callers must not use a detector match as proof that a credential is valid or belongs to the user.

## False negatives

The detector may miss:

- unknown provider-specific formats;
- split, encoded, encrypted, compressed, obfuscated, or transformed values;
- secrets embedded in unsupported binary formats;
- unlabeled recovery phrases;
- short or unusual credential values;
- personal data outside the selected patterns;
- values beyond configured scan or finding limits.

A clean scan is not proof that content is safe. Unknown or uncertain secret-bearing persistence remains governed by the fail-closed IMP-013 policy.

## Portability effects

Imported source material must not be silently discarded because a detector found a possible secret. A future portability adapter may quarantine, preserve externally, omit from a derived view, or request review according to the accepted import contract and must report the mapping or loss outcome.

Detector findings do not grant instruction authority, confirmed-memory status, permission, capability, confirmation, or credential scope.

## Acceptance

Permanent tests prove:

- common synthetic patterns are detected and redacted;
- finding objects do not retain secret values;
- ordinary text remains unchanged;
- overlapping matches normalize deterministically;
- scan and finding limits are enforced;
- scan-limit exhaustion returns no original text;
- finding-limit exhaustion returns no original text;
- nested diagnostic keys and values are redacted;
- recursion, item, binary, and unknown-object limits are explicit;
- user-visible CLI exception text crosses the redaction boundary;
- no model, cloud, network, filesystem scanning, or secret-store dependency is introduced.
