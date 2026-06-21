# IMP-020 — Prompt Injection Defense

## Status

Complete.

## Purpose

IMP-020 adds a model-independent prompt-injection defense layer above IMP-019 instruction-origin records. It prepares context safely without granting a model, detector, classifier, source, tool result, runtime output, or generated proposal any authority.

The defense has three independent layers:

1. IMP-019 origin and authority classification remains the authorization source of truth;
2. bounded pattern detection records advisory indicators without retaining matched text;
3. context packaging preserves channels, removes detected secrets, and fails completely when it cannot scan or package all selected content within configured limits.

A detector miss does not make untrusted content authoritative. A detector hit does not demote a valid current user instruction or system policy. Authorization never depends on detector output.

## Advisory detection

`scan_prompt_injection` scans only the string explicitly supplied by the caller. It does not inspect files, directories, environment variables, browsers, secret stores, process memory, network traffic, or model state.

The initial detector set flags selected patterns for:

- attempts to ignore, replace, bypass, or override higher-authority instructions;
- requests to reveal hidden prompts, private context, memory, or internal instructions;
- requests to send, expose, upload, or forward secrets, credentials, or private files;
- unsupported claims that a user, administrator, owner, or security team already approved an action;
- requests to weaken or change policy, permissions, confirmation, or safety rules;
- requests to lower or override a risk tier;
- requests for unrestricted or expanded scope;
- requests to invoke unrelated shell, tool, browser, network, email, upload, deletion, or subprocess capabilities;
- encoded or obfuscated instruction claims;
- instruction-like role or policy labels in titles and source metadata.

Detection is deliberately best-effort and cannot prove that content is safe. False positives and false negatives are expected.

## Finding safety

A `PromptInjectionFinding` retains only:

- finding kind;
- confidence class;
- detector identifier;
- scanned field identifier.

It does not retain:

- matched text;
- snippets;
- offsets;
- prefixes or suffixes;
- content hashes;
- secrets;
- reconstruction hints.

The same input, field, detector version, and limits produce the same ordered findings.

## Context packaging

`PromptDefenseService.package_context` accepts selected IMP-019 instruction-origin record IDs and returns a structured `PromptContextPackage`.

The package keeps these channels separate:

- system policy;
- current user instruction;
- durable user policy;
- user management action;
- untrusted content;
- model proposals;
- unknown origin.

There is no method that flattens these channels into one trusted string. A future model adapter must map the channels to the least-authoritative supported provider or runtime representation without changing their effective authority.

Each packaged item preserves:

- record ID;
- channel;
- title and content;
- declared origin and authority;
- effective authority after archive and durable-policy freshness checks;
- data-only state;
- authority-active state and failure reason;
- source identifier where present;
- transformation history;
- advisory prompt-injection findings;
- secret-redaction count.

Archived instructions remain available only as `unknown_data`. A stale or disabled durable policy remains visible but is downgraded to `untrusted_data` before packaging.

## Secret boundary

Before title, content, or source identifier enters a context package, IMP-014 deterministic redaction is applied.

If secret scanning exceeds its character limit or finding limit, packaging raises `PromptContextLimitError` and returns no partial package. Detected secret values are replaced by typed redaction markers. Findings and package summaries retain counts only, not secret material.

IMP-020 does not weaken the existing prohibition on storing secret values in instruction-origin records. The additional redaction layer protects synthetic bundles and future callers at the context boundary.

## Resource limits

The caller must remain within explicit bounds for:

- selected record count;
- characters per title or content item;
- total packaged characters;
- characters scanned per field;
- findings per field and item.

Exceeding a package limit raises an error and returns no partially truncated package. The service does not silently omit selected records or silently shorten content.

## Authorization guard

`PromptDefenseService.authority_decision` delegates directly to IMP-019. `require_authority` raises `PromptAuthorizationError` when the selected instruction origin is not authorized for the requested purpose.

The guard does not consult:

- prompt-injection findings;
- model output;
- classifier output;
- confidence values;
- role-like wording;
- repeated claims;
- locality;
- structured formatting.

External content, imported data, tool results, runtime output, model proposals, and unknown-origin content cannot grant permission, confirmation, capability definitions, risk changes, workspace expansion, network policy changes, secret policy changes, security instructions, or chained side effects.

IMP-021 will define the capability registry and risk tiers. IMP-022 will define exact fresh confirmation for high-risk operations. IMP-020 does not pre-approve either boundary.

## Tests

Synthetic tests cover:

- all initial indicator categories;
- field-aware metadata detection;
- finding structures that retain no matched content;
- deterministic packaging;
- structural channel separation;
- advisory findings that do not change effective authority;
- secret redaction before packaging;
- secret-scan and prompt-scan exhaustion;
- per-item, total-character, and selected-item limits;
- protected-purpose denial for external and model content;
- accepted current-user and management authority paths;
- archived instruction downgrade;
- stale durable-policy downgrade;
- duplicate record IDs;
- malformed fields, limits, purposes, sequence types, and bundle types.

## Explicit non-goals

IMP-020 does not add:

- a live model or classifier;
- model adapter or prompt transmission;
- tool or capability execution;
- a capability registry or risk-tier implementation;
- high-risk confirmation;
- network access;
- a new dependency;
- a persistence schema or migration;
- custom cryptography;
- a claim of perfect prompt-injection detection.

## Known limitations

- Pattern matching is English-oriented and intentionally incomplete.
- Obfuscation, multilingual attacks, images, audio, and novel social-engineering forms may not be detected.
- A clean scan is not evidence of benign content.
- Context relevance and provider-specific role mapping remain future orchestration concerns.
- The package is a model-independent data structure, not an executable prompt.

These limitations do not weaken the core guarantee because origin-based authorization remains outside the model and outside the detector.
