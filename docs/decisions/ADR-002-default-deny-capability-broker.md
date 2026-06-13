# ADR-002: Default-deny Capability Broker

**Status:** Accepted  
**Date:** 2026-06-13

## Context

Doll will use language models that may be incorrect, compromised, prompt-injected, or deliberately manipulative. It will also process untrusted websites, documents, images, and tool outputs.

Giving a model direct access to the filesystem, shell, network, accounts, or external services would allow model errors or hostile content to become computer actions.

The project therefore needs one mandatory authorization boundary between model intent and side effects.

## Decision

All side-effecting model requests must pass through a versioned, default-deny Capability Broker.

The broker validates:

- capability identity and version;
- input schema;
- target and scope;
- filesystem boundary;
- network policy;
- permission state;
- required user approval;
- timeout and cancellation;
- declared side effects;
- audit requirements.

Unknown, malformed, out-of-scope, or unapproved requests are denied.

Models cannot:

- grant permissions;
- approve their own requests;
- use document or web content as approval;
- bypass the broker through a runtime adapter;
- directly mutate audit records;
- invoke an unrestricted shell;
- silently expand an approved operation.

Initial capabilities are limited to narrow reads, explicit retrieval, managed creation, backup, and inspection.

Destructive or externally visible capabilities are unavailable in initial releases.

## Permission model

Initial permission modes are:

- denied;
- allow once;
- ask every time;
- allow within a defined scope.

The initial product has no persistent global `allow all` mode.

Approvals are invalidated when material operation details change.

## Consequences

### Positive

- Model quality does not determine operating-system authority.
- Prompt injection cannot directly grant permissions.
- Side effects become attributable and auditable.
- Lite and Heavy share the same permission semantics.
- Cloud and local models can be governed by one boundary.
- Optional tools can be added through narrow contracts.

### Negative

- Tool integration requires more engineering than direct function exposure.
- Permission prompts may add friction.
- Capability schemas and versions must be maintained.
- Some third-party agent frameworks cannot be connected directly.
- Incorrectly narrow capabilities may limit useful workflows.

## Rejected alternatives

### Trust the system prompt

Rejected because models can ignore or misinterpret instructions, and prompt injection can influence model output.

### Let each tool enforce its own permissions

Rejected because policy, approval, audit, and error behavior would become inconsistent.

### Use unrestricted shell with confirmation

Rejected for initial releases because one confirmation cannot reliably describe the effects of arbitrary commands, scripts, pipes, environment variables, and child processes.

### Give local models more authority than cloud models

Rejected because local execution does not make model output trustworthy.

### Allow all actions inside the workspace

Rejected because destructive overwrite, data corruption, malicious archives, and secret exfiltration can still occur inside the workspace.

## Implementation constraints

- Capability IDs and schemas are versioned.
- Capability adapters cannot expose generic command execution.
- Every allowed or denied side-effecting request creates an audit event.
- Filesystem targets are canonicalized and checked after link resolution where supported.
- Network capabilities declare request method and destination policy.
- User approval comes from a trusted local interface or management command.
- Approval scope and expiration are explicit.
- The broker fails closed on errors.

## Validation

The decision is validated when tests demonstrate that:

1. unknown capabilities are rejected;
2. malformed arguments are rejected;
3. workspace escape attempts are rejected;
4. model-generated approval text has no authority;
5. changed arguments invalidate approval;
6. cloud-disabled mode prevents outbound cloud requests;
7. allowed and denied operations create audit events;
8. no unrestricted shell capability exists;
9. optional tool failure does not bypass the broker;
10. the last known good state remains intact after denial or failure.
