# Security, permissions, and threat model

**Status:** Draft for acceptance  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`

## 1. Purpose

This document defines the minimum security model required for doll to preserve user state without giving models unrestricted authority over the user's computer, network, accounts, or data.

The security design follows five principles:

1. default deny;
2. least privilege;
3. explicit user control;
4. local authority;
5. recoverable failure.

A local model is not automatically trusted. A cloud model is not automatically trusted. Retrieved documents, websites, plugins, runtimes, and generated tool arguments are not automatically trusted.

## 2. Security objectives

The initial implementation must aim to protect:

- the confidentiality of private workspace data;
- the integrity of authoritative state;
- the availability of the last known good local state;
- the user's control over external communication;
- the workspace boundary;
- backup and restore integrity;
- permission and audit history;
- model and runtime provenance;
- the ability to stop or deny unsafe operations.

## 3. Non-goals and trust assumptions

## 3.1 Initial non-goals

The initial product does not claim to defend against:

- an attacker who already controls the user's operating-system account;
- an attacker with administrator or root access;
- a compromised operating-system kernel;
- malicious hardware or firmware;
- arbitrary untrusted native code executed outside doll;
- public multi-user server attacks;
- hostile users sharing one workspace;
- perfect detection of all secrets or personal information;
- complete prevention of model hallucination;
- safe execution of arbitrary third-party plugins.

## 3.2 Assumed trusted base

The initial trusted computing base includes:

- the user's operating system and local account;
- the installed doll core from a known source;
- the local filesystem and SQLite implementation;
- accepted cryptographic libraries and operating-system credential stores;
- explicit user actions through the local management interface.

Everything else is treated according to its boundary and capability.

## 4. Assets

Security-sensitive assets include:

- confirmed memory;
- personal documents;
- project and decision records;
- research sources and caches;
- generated artifacts;
- model and runtime manifests;
- model files and tokenizers;
- permissions and policies;
- audit events;
- backups and recovery kits;
- local API configuration;
- future cloud credentials;
- optional identity, personality, relationship, voice, and appearance state.

## 5. Threat actors and failure sources

The threat model includes both malicious actors and accidental failure.

### 5.1 Malicious external content

Examples:

- a web page containing prompt injection;
- a PDF instructing the model to reveal secrets;
- a document containing path traversal strings;
- an image or OCR result containing malicious instructions;
- a poisoned research source attempting to alter policy.

### 5.2 Malicious or compromised model

A model may:

- request a forbidden tool;
- fabricate user approval;
- generate unsafe paths;
- attempt to exfiltrate data;
- hide a dangerous action in a plausible plan;
- ignore system policy;
- produce malformed structured output.

### 5.3 Malicious or compromised runtime or tool

A runtime, extractor, browser, OCR engine, audio tool, plugin, or dependency may:

- access unexpected files;
- make unexpected network requests;
- execute code;
- corrupt output;
- return hostile data;
- leak environment variables;
- introduce vulnerable transitive dependencies.

### 5.4 Local application or UI misuse

A UI may:

- request overly broad access;
- store a copy of sensitive data;
- bypass user expectations;
- expose the local API to another process;
- send hidden metadata externally.

### 5.5 Supply-chain compromise

Possible sources:

- modified model files;
- malicious Python packages;
- compromised release archives;
- altered runtime binaries;
- dependency confusion;
- unsafe remote-code model loaders;
- fake update notifications.

### 5.6 Accidental user action

Examples:

- selecting the wrong file;
- approving the wrong destination;
- restoring an old backup over newer state;
- exporting secrets;
- choosing a model too large for the machine;
- opening the local API to the network;
- deleting the only valid backup.

### 5.7 Resource exhaustion

Examples:

- disk exhaustion from cache or media;
- memory exhaustion from a model;
- runaway inference;
- infinite retry loops;
- oversized files or decompression bombs;
- excessively large context assembly;
- denial of service through repeated local requests.

### 5.8 State corruption and partial failure

Examples:

- interrupted migration;
- incomplete backup;
- failed restore;
- power loss during write;
- concurrent mutation;
- incompatible schema;
- stale revision overwrite.

## 6. Security boundaries

## 6.1 Model boundary

Model output is untrusted proposed data.

A model cannot directly:

- open arbitrary files;
- write arbitrary files;
- execute commands;
- make network requests;
- alter permissions;
- approve its own requests;
- delete state;
- change audit records;
- activate a model;
- perform migration or restore.

The model may emit a structured capability request. The Capability Broker validates and decides whether the request is denied, executed, or presented for user approval.

## 6.2 Capability Broker boundary

The Capability Broker is the mandatory authorization point for every side effect.

A capability request must include:

- capability ID;
- capability version;
- operation ID;
- session ID;
- validated arguments;
- declared target;
- declared side effects;
- permission scope;
- approval requirement;
- timeout;
- cancellation token where supported.

The broker must reject:

- unknown capability IDs;
- unsupported versions;
- malformed arguments;
- missing scope;
- paths outside the approved root;
- network destinations outside policy;
- requests requiring unavailable approval;
- model attempts to modify permission state;
- requests that conceal or expand side effects.

## 6.3 Filesystem boundary

The default managed-write boundary is the private workspace.

### Required controls

- canonicalize the requested path;
- resolve relative paths against an approved root;
- reject `..` traversal;
- reject absolute paths unless a user-controlled import or export flow explicitly permits them;
- detect symlink, junction, or mount escapes where supported;
- open files using safe modes;
- create new files without silent overwrite;
- use atomic replacement for approved updates;
- verify the final path after creation where practical;
- apply size limits;
- record the resulting file and hash.

### Read policy

The initial product may read:

- files explicitly selected by the user;
- managed files inside the workspace;
- approved configured read roots, if later enabled.

The initial product must not recursively scan the entire home directory by default.

### Restricted locations

The initial product must not intentionally read locations such as:

- SSH key directories;
- browser password databases;
- system credential stores;
- cryptocurrency wallet secret material;
- `.env` files;
- operating-system account databases;
- application secret stores;

unless a later explicit, narrowly scoped feature is approved. Secret detection does not grant permission to search for secrets.

## 6.4 Network boundary

The local API binds to `127.0.0.1` by default.

### Initial inbound policy

- no public internet listener;
- no LAN listener by default;
- no anonymous remote access;
- no mobile remote access in the initial release;
- no automatic firewall changes;
- no UPnP or router configuration.

### Initial outbound policy

Allowed only when explicitly initiated or enabled:

- user-requested web search;
- user-requested URL retrieval;
- user-approved model acquisition;
- manual update or dependency retrieval outside normal runtime behavior.

Disallowed by default:

- telemetry;
- analytics;
- crash uploads;
- hidden update checks;
- advertising;
- background model discovery;
- automatic cloud inference;
- arbitrary POST, PUT, PATCH, or DELETE requests;
- external file upload.

A later web-research implementation may use required HTTP methods for safe retrieval, but any state-changing external request requires a separately accepted capability.

### Network request controls

Where practical, retrieval capabilities must enforce:

- supported schemes;
- destination normalization;
- redirect limits;
- response-size limits;
- timeouts;
- content-type checks;
- private-network and localhost restrictions to reduce SSRF risk;
- DNS and resolved-address validation where necessary;
- audit of final destination;
- cancellation.

## 6.5 Process execution boundary

The initial product does not expose unrestricted shell execution.

Approved external tools must use dedicated adapters with:

- a fixed executable or validated configured path;
- argument arrays rather than command strings;
- `shell=False` or platform equivalent;
- input and output limits;
- controlled environment variables;
- controlled working directory;
- timeout and cancellation;
- explicit file access scope;
- captured exit status;
- audit records.

A tool adapter may not become a generic command runner.

## 6.6 Cloud boundary

Cloud support is a future optional gateway.

Any later cloud request must be assembled as a bounded outbound package.

Before sending, the system must be able to show:

- provider;
- model;
- exact or summarized outbound content;
- attachments or excerpts;
- redactions;
- estimated size or tokens where possible;
- estimated cost where possible;
- applicable permission mode.

The cloud gateway must not have unrestricted workspace read access. It receives only the approved outbound package.

## 6.7 Backup and recovery boundary

Backups are high-value copies of private state.

Required controls:

- explicit included and excluded categories;
- manifest and checksums;
- verification before completion;
- no secrets in plain configuration exports;
- safe handling of external references;
- conflict detection during restore;
- staging before activation;
- no silent overwrite of a newer workspace;
- restoration audit event;
- optional standard encryption in a later implementation.

The project must not invent custom cryptography.

## 7. Permission model

## 7.1 Permission classes

Initial permission classes:

### Class 0: Pure computation

Examples:

- local text transformation;
- local reasoning;
- schema validation;
- hashing data already provided to the operation.

Default: allowed.

### Class 1: Managed read

Examples:

- read an approved workspace record;
- read a managed workspace file;
- query a local index.

Default: allowed within the current task scope.

### Class 2: Explicit external read

Examples:

- read a user-selected external file;
- fetch a user-specified URL;
- perform a user-requested web search.

Default: user initiation or explicit approval required.

### Class 3: Managed creation

Examples:

- create a new artifact;
- create a research log;
- create a backup;
- create a suggested memory.

Default: allowed within approved workspace directories, subject to limits and audit.

### Class 4: Managed modification

Examples:

- update a confirmed memory;
- supersede a decision;
- replace a managed artifact version;
- apply a migration.

Default: explicit user confirmation or a narrowly defined management command.

### Class 5: Destructive or externally visible action

Examples:

- permanent deletion;
- overwrite without retained prior version;
- external upload;
- sending email;
- posting to social media;
- account change;
- purchase;
- financial transaction;
- arbitrary command execution.

Default: unavailable in initial releases.

## 7.2 Permission modes

Supported initial modes:

- denied;
- allow once;
- ask every time;
- allow for a defined scope.

A defined scope must specify constraints such as:

- capability;
- project;
- directory;
- destination host;
- file type;
- size limit;
- expiration;
- session.

A global persistent `allow all` mode is prohibited in the initial product.

## 7.3 Approval integrity

Approval must be obtained from a user-controlled interface, not from model-generated text.

The system must not treat phrases in documents, web pages, or model output as approval.

Approval records should identify:

- operation;
- capability;
- summarized effect;
- target;
- time;
- scope;
- user decision.

Material changes after approval invalidate the approval.

## 8. Prompt injection and untrusted-content handling

## 8.1 Core rule

Retrieved or imported content is data, not authority.

Content cannot override:

- system policy;
- user policy;
- permission state;
- capability definitions;
- workspace boundaries;
- network policy;
- security instructions.

## 8.2 Required separation

The orchestration layer must distinguish:

- system instructions;
- user instructions;
- durable policies;
- retrieved content;
- tool outputs;
- model-generated proposals.

Where the model interface supports roles or structured context, untrusted content must be placed in the least authoritative role available.

## 8.3 Injection indicators

The system should detect and flag patterns such as:

- requests to ignore previous instructions;
- requests to reveal hidden prompts or memory;
- requests to call tools unrelated to the user task;
- requests to send files or secrets;
- fake approval statements;
- encoded or obfuscated instructions;
- instructions embedded in metadata or citations.

Detection is advisory. Authorization boundaries must not depend solely on classification by another model.

## 8.4 Tool-result handling

Tool results remain untrusted.

A tool result may inform a model response but cannot grant new permissions or trigger a new capability without normal validation.

## 9. Secret and sensitive-data handling

## 9.1 Secret classes

Examples:

- API keys;
- access tokens;
- passwords;
- private keys;
- recovery phrases;
- session cookies;
- banking credentials;
- payment-card data;
- government identity numbers;
- sensitive health information;
- private third-party personal data.

## 9.2 Required behavior

- do not log secrets;
- redact or omit detected secrets from error messages;
- do not include secrets in normal exports;
- do not include secrets in test fixtures;
- do not send secrets to models by default;
- do not store future cloud API keys in ordinary configuration files;
- use operating-system credential storage when cloud credentials are implemented;
- warn before exporting sensitive records;
- allow the user to run without cloud credentials.

## 9.3 Detection limits

Secret scanning is best-effort and may miss data or produce false positives. It supplements but does not replace path, permission, and outbound controls.

## 10. Model and supply-chain security

## 10.1 Model acquisition

Before model acquisition, record or display:

- source;
- developer;
- exact revision;
- license;
- file size;
- format;
- quantization;
- expected runtime;
- expected hardware;
- checksum when available;
- whether remote code is required.

## 10.2 Model loading

The initial validated model path should prefer inert weight formats and runtimes that do not require executing repository-provided code.

Models requiring `trust_remote_code`, arbitrary Python modules, install scripts, or opaque launchers are not standard validated targets.

## 10.3 Quarantine

New model assets enter a quarantine or candidate state until:

- checksums pass;
- format inspection passes;
- license record exists;
- runtime compatibility is known;
- basic offline loading succeeds;
- resource limits are acceptable;
- evaluation is complete for the intended role.

## 10.4 Dependency security

The project should:

- use a lockfile;
- pin release dependencies appropriately;
- minimize core dependencies;
- separate optional dependency groups;
- review new transitive dependencies;
- use automated vulnerability checks when implementation begins;
- avoid executing install-time scripts from untrusted sources where possible;
- record third-party notices and licenses.

## 10.5 Update security

There is no silent self-update.

A future update flow must:

1. identify the source and target version;
2. verify package provenance or checksums where available;
3. show migration implications;
4. create a verified backup;
5. stage the update;
6. run doctor or validation;
7. support rollback.

## 11. Audit requirements

Security-relevant operations must create append-oriented audit events.

Audit events should include:

- operation ID;
- actor type;
- capability ID;
- permission decision;
- target category;
- network destination where applicable;
- model and runtime IDs where applicable;
- result;
- error class;
- created record or artifact IDs.

Audit events must not contain:

- passwords;
- secret keys;
- full private documents;
- unnecessary model prompts;
- raw authentication tokens.

Normal model capabilities cannot modify or delete audit history.

User-controlled retention and export of audit data may be added through management commands.

## 12. Denial of service and resource controls

The implementation must define limits for:

- file size;
- archive expansion;
- HTTP response size;
- redirect count;
- request duration;
- model context size;
- generated output size;
- concurrent operations;
- temporary storage;
- cache storage;
- retries;
- subprocess duration;
- media duration and frame extraction.

The system must avoid infinite automatic retry.

When resources are insufficient, it should stop the operation, preserve state, and report a lower-cost or lower-capability alternative.

## 13. Data integrity and recoverable writes

Required controls:

- schema validation before commit;
- transaction boundaries for structured state;
- revision checks;
- atomic file creation or replacement where supported;
- content hashing;
- pre-migration backup;
- staged import and restore;
- post-operation verification;
- explicit failure status;
- no success message before durable completion.

A failed operation must not destroy the last valid version.

## 14. User deletion versus autonomous deletion

The model and normal autonomous workflows cannot delete authoritative state.

The user may delete through an explicit management path.

Default direction:

- preview the affected records and files;
- show dependent records;
- move to trash or create tombstones;
- retain for the configured period;
- require explicit purge for permanent deletion;
- record the user action.

Secure physical erasure is not guaranteed on SSDs, copy-on-write filesystems, backups, or encrypted storage. The interface must not make a false guarantee.

## 15. Local API protection

The initial API must:

- bind to localhost only;
- avoid permissive cross-origin settings;
- reject unexpected host headers where practical;
- expose no unauthenticated remote mode;
- limit request sizes;
- normalize errors;
- avoid secrets in responses;
- support request cancellation and timeouts;
- provide a clear health endpoint without private state;
- avoid exposing arbitrary host paths.

Even on localhost, the implementation should consider other local processes as potentially untrusted.

A later design may add a local session token or origin-bound authentication for UI clients. Remote authentication is a separate future specification.

## 16. Emergency controls

The project should provide or plan:

- stop accepting new tool operations;
- cancel active cancellable operations;
- stop the local server;
- disable network capabilities;
- disable a model binding;
- enter read-only recovery mode;
- preserve audit and recovery state.

An emergency stop must not delete state or corrupt a backup.

## 17. Security states and user-visible reporting

The system should expose states such as:

- normal;
- degraded;
- offline;
- read-only recovery;
- migration required;
- backup invalid;
- model unavailable;
- capability disabled;
- security warning;
- operation blocked.

Security-relevant failure must not be hidden behind a generic successful chat response.

## 18. Platform considerations

## 18.1 macOS

- use platform data directories;
- respect sandbox and privacy prompts where applicable;
- recommend FileVault for disk encryption;
- use Keychain for future credentials;
- test symlink behavior and application permissions.

## 18.2 Windows

- use platform data directories;
- handle reserved names and drive letters;
- test junction and reparse-point escapes;
- recommend BitLocker where available;
- use Windows Credential Manager for future credentials;
- account for Defender and file-lock behavior.

## 18.3 Linux

- follow XDG directories where practical;
- test symlink and mount behavior;
- recommend LUKS or equivalent disk encryption;
- use Secret Service for future credentials where available;
- avoid assumptions about one shell or distribution.

## 19. Security testing requirements

Implementation acceptance tests must eventually include:

- path traversal rejection;
- symlink or junction escape tests where supported;
- write-outside-workspace rejection;
- unknown capability rejection;
- malformed tool request rejection;
- permission denial;
- approval invalidation after argument change;
- prompt-injection content cannot grant a capability;
- cloud-disabled mode emits no cloud request;
- local API binds to localhost;
- SSRF-oriented destination restrictions;
- response and file size limits;
- subprocess timeout and `shell=False` enforcement;
- secret redaction in logs and errors;
- interrupted write recovery;
- failed migration preservation;
- failed restore preservation;
- checksum mismatch rejection;
- candidate model cannot become active without approval;
- missing optional dependency does not block core startup;
- audit event creation for allowed and denied actions.

Security claims must distinguish CI tests from real-machine validation.

## 20. Threat-to-control matrix

| Threat | Prevent | Detect | Record | Recover |
| --- | --- | --- | --- | --- |
| Prompt injection | instruction/data separation; capability checks | injection indicators; unrelated-tool warning | source and denied request | discard hostile context; continue local task |
| Workspace escape | path canonicalization; approved roots; link checks | boundary violation | denied capability event | no state change |
| Secret exfiltration | no broad reads; outbound package; redaction | secret scanner; destination preview | redacted denial or approval | cancel request; rotate secret outside doll if needed |
| Malicious model request | default-deny broker | unknown or excessive capability request | denied event with model ID | disable binding; switch to fallback |
| Malicious tool/runtime | adapter limits; fixed executable; sandbox later | abnormal exit, network, or file behavior | tool failure and provenance | disable adapter; restore affected state |
| Supply-chain tampering | source and checksum validation; no remote code by default | checksum or signature mismatch | quarantine event | reject asset; keep active version |
| Partial migration | backup and staging | validation failure | migration failure | rollback or restore pre-migration backup |
| Corrupt backup | checksums and verification | verify failure | invalid backup status | use earlier valid backup |
| Resource exhaustion | limits and cancellation | resource threshold | aborted operation | cleanup disposable files; use Lite alternative |
| Local API exposure | localhost binding; no remote mode | doctor check and bind inspection | warning | stop server; restore safe config |
| Unauthorized deletion | deletion unavailable to models | forbidden capability | denial | no change; restore trash if user deletion was accidental |
| Silent cloud fallback | cloud disabled by default; no auto fallback | outbound audit check | blocked or approved cloud event | continue local degraded mode |

## 21. Deferred security work

The following require separate later specifications:

- secure remote and mobile access;
- multi-device synchronization;
- plugin marketplace security;
- arbitrary code sandboxing;
- desktop automation;
- email, posting, purchasing, or transaction capabilities;
- enterprise multi-user authorization;
- high-assurance backup encryption;
- hardware-backed keys;
- cloud-provider-specific data-retention policy handling;
- formal verification;
- secure enclaves or confidential computing.

## 22. Security acceptance criteria

This specification is acceptable when subsequent implementation can be designed so that:

- models cannot bypass the Capability Broker;
- default permissions are deny or narrow allowlists;
- files cannot be written outside the workspace through supported APIs;
- cloud communication is absent unless explicitly enabled;
- external content cannot act as approval;
- unrestricted shell execution is absent;
- model and tool supply-chain metadata is retained;
- state changes are recoverable;
- audit records exist for security-relevant actions;
- secrets are excluded from ordinary logs and exports;
- the local API is not publicly exposed by default;
- optional tools can fail without compromising the durable core.
