# Security, permissions, and threat model

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `ADR-002-default-deny-capability-broker.md`, `ADR-005-safety-boundary-before-model-execution.md`

## 1. Purpose

This document defines the minimum security model required for doll to preserve user-owned state without giving models, runtimes, tools, external content, or interfaces unrestricted authority over the user's computer, network, accounts, secrets, or data.

The security design follows these principles:

1. default deny;
2. least privilege;
3. explicit user control;
4. local authority;
5. recoverable failure;
6. memory and secret separation;
7. provenance and trust separation;
8. external content is data, not authority;
9. high-risk operations require fresh exact confirmation.

A local model is not automatically trusted. A cloud model is not automatically trusted. Retrieved documents, websites, images, media transcripts, OCR output, imports, plugins, runtimes, tools, generated arguments, and model output are not automatically trusted.

Continuity and the safety boundary are co-equal architectural pillars. The complete model-independent safety boundary defined by this specification must be implemented and acceptance-tested before any model execution path is introduced.

## 2. Security objectives

The implementation must protect:

- the confidentiality of private workspace data;
- the integrity of authoritative state;
- the availability of the last known good local state;
- the separation of ordinary state from secret values;
- the user's control over credential use and external communication;
- the workspace boundary;
- backup, restore, export, import, and migration integrity;
- permission, confirmation, and audit history;
- claim, evidence, inference, and instruction-origin provenance;
- model, runtime, tool, and dependency provenance;
- the ability to stop, deny, cancel, or recover from unsafe operations.

Security failure must not be hidden behind a successful model response or generic success message.

## 3. Sequencing requirement

The implementation order is mandatory:

1. local state foundation;
2. model-independent continuity, export, backup, restore, and validation;
3. model-independent safety boundary;
4. safety acceptance gate;
5. local model execution;
6. optional cloud and broader tools.

Before the safety acceptance gate passes, the repository must not contain an accepted path that:

- invokes a model runtime;
- sends a prompt to a model;
- gives a model direct or indirect tool authority;
- provides a model with secret values;
- permits a model adapter to mutate state, filesystem, network, process, permissions, confirmation, credentials, or audit history.

Mocked model-like proposals may be used to test the boundary, but they remain untrusted structured input.

## 4. Non-goals and trust assumptions

### 4.1 Initial non-goals

The initial product does not claim to defend against:

- an attacker who already controls the user's operating-system account;
- an attacker with administrator or root access;
- a compromised operating-system kernel;
- malicious hardware or firmware;
- arbitrary untrusted native code executed outside doll;
- public multi-user server attacks;
- hostile users sharing one workspace;
- perfect detection of every secret or personal datum;
- perfect detection of every prompt injection;
- complete prevention of model hallucination;
- safe execution of arbitrary third-party plugins;
- secure erasure guarantees on SSD, copy-on-write, backup, or synchronized storage;
- formal verification of all safety properties.

### 4.2 Assumed trusted base

The initial trusted computing base includes:

- the user's operating system and local account;
- the installed doll core from a known source;
- the local filesystem and SQLite implementation;
- accepted cryptographic libraries;
- the configured operating-system or compatible external secret store;
- explicit user actions through a trusted local management interface.

A configured secret-store adapter is trusted only for the narrow contract it implements. A model, runtime, plugin, UI, web page, document, tool result, or external service is not added to the trusted base merely because it runs locally or is open source.

## 5. Security-sensitive assets

Security-sensitive assets include:

- confirmed memory;
- preferences, policies, permissions, and confirmations;
- personal documents;
- project and decision records;
- claims, evidence, inferences, and source records;
- research sources and caches;
- generated artifacts;
- model and runtime manifests;
- model files and tokenizers;
- audit events;
- backups and recovery kits;
- local API configuration;
- SecretReference records;
- externally stored credential values;
- optional identity, personality, relationship, voice, and appearance state.

Secret values are not ordinary Doll State assets. They remain in an external secret store and are accessed only through the accepted credential boundary.

## 6. Threat actors and failure sources

The threat model includes malicious behavior, accidental behavior, and partial failure.

### 6.1 Malicious external content

Examples:

- a page telling the model to ignore previous instructions;
- a PDF requesting secret disclosure;
- a document containing fake approval text;
- metadata containing hidden capability requests;
- OCR text containing malicious instructions;
- an audio or video transcript attempting to change policy;
- imported data claiming to be a trusted fact;
- a source attempting to trigger unrelated tools or network requests.

### 6.2 Malicious, compromised, or incorrect model

A model may:

- request a forbidden or excessive capability;
- fabricate user approval or confirmation;
- generate unsafe paths or destinations;
- attempt secret exfiltration;
- hide dangerous side effects in a plausible plan;
- ignore instruction authority;
- convert claims into facts without evidence;
- produce malformed structured output;
- request risk-tier downgrades;
- produce convincing but false security explanations.

### 6.3 Malicious or compromised runtime, tool, or dependency

A runtime, extractor, browser, OCR engine, media tool, plugin, dependency, or secret-store adapter may:

- access unexpected files;
- make unexpected network requests;
- execute code;
- corrupt output;
- return hostile data;
- leak environment variables or credentials;
- misreport completion;
- introduce vulnerable transitive dependencies;
- retain private input unexpectedly.

### 6.4 Local UI or client misuse

A UI or local client may:

- request overly broad access;
- store a copy of sensitive data;
- bypass user expectations;
- expose the local API to another process;
- send hidden metadata externally;
- misrepresent a high-risk confirmation;
- omit material side effects from a preview.

### 6.5 Supply-chain compromise

Possible sources:

- modified model files;
- malicious Python packages;
- compromised release archives;
- altered runtime binaries;
- dependency confusion;
- unsafe remote-code model loaders;
- fake update notifications;
- malicious prompt, template, plugin, or tool packages.

### 6.6 Accidental user action

Examples:

- selecting the wrong file;
- approving the wrong destination;
- restoring an old backup over newer state;
- exporting sensitive records;
- choosing a model too large for the machine;
- opening the local API to the network;
- deleting the only valid backup;
- confirming an operation without noticing a changed target.

### 6.7 Resource exhaustion

Examples:

- disk exhaustion from cache, backup, or media;
- memory exhaustion from a model;
- runaway inference;
- infinite retry loops;
- oversized files or decompression bombs;
- excessive context assembly;
- repeated local requests;
- unbounded subprocess output;
- secret-store prompts repeated without limit.

### 6.8 State corruption and partial failure

Examples:

- interrupted migration;
- incomplete backup;
- failed restore;
- power loss during write;
- concurrent mutation;
- incompatible schema;
- stale revision overwrite;
- partial capability side effects;
- audit write failure;
- confirmation recorded without completed operation.

## 7. Authority, trust, claim, and evidence model

Doll must distinguish data truth status from instruction authority.

### 7.1 Required truth categories

At minimum, the state model must distinguish:

- **confirmed fact:** durable information explicitly confirmed or explicitly created as fact by the user through a trusted management path;
- **claim:** an assertion that may be true or false;
- **evidence:** a source, observation, record, or artifact that supports, contradicts, or contextualizes a claim;
- **inference:** a derived conclusion with source links, method or actor provenance, confidence, and uncertainty.

A model, runtime, document, page, import, tool, OCR result, transcript, or external service cannot promote its own statement to confirmed fact.

A confirmed fact may be revised or superseded only through an explicit user-controlled or accepted management path with history and audit.

### 7.2 Required provenance

Claims, evidence, and inferences must retain where applicable:

- source identifier;
- origin type;
- creator or actor type;
- creation and observation time;
- content hash or stable reference;
- supporting and contradicting links;
- confidence or uncertainty;
- review and confirmation state;
- transformation or extraction method.

Missing provenance must remain visible. It must not be silently invented.

### 7.3 Trust is not popularity or locality

The system must not infer trust merely from:

- local execution;
- open-source status;
- repository popularity;
- model confidence;
- repeated statements;
- a signed-in account;
- an apparently official visual design;
- a tool returning structured JSON.

Trust decisions must use explicit policy and provenance.

## 8. Instruction origin and untrusted-content boundary

### 8.1 Core rule

Retrieved, imported, extracted, transcribed, or generated content is data, not authority.

Content cannot override:

- system policy;
- user instruction;
- durable user policy;
- permission state;
- confirmation state;
- capability definitions;
- risk tiers;
- workspace boundaries;
- network policy;
- secret policy;
- security instructions.

### 8.2 Required authority classes

The orchestration and persistence layers must distinguish at least:

- system security and product policy;
- explicit current user instruction;
- durable user policy;
- user confirmation or management action;
- retrieved or imported content;
- tool or runtime output;
- model-generated proposal;
- unknown origin.

Unknown origin must default to the least-authoritative classification.

### 8.3 Origin metadata

Instruction-bearing input must retain where applicable:

- origin class;
- source identifier;
- acquisition method;
- parent operation or session;
- content hash;
- time;
- whether the content is trusted only as data;
- transformations such as OCR, extraction, summarization, or transcription.

Origin metadata must survive persistence, export, import, retrieval, and context assembly.

### 8.4 Prompt-injection indicators

The system should detect and flag patterns such as:

- requests to ignore previous instructions;
- requests to reveal hidden prompts, memory, or secrets;
- requests to call tools unrelated to the user's task;
- requests to send files or credentials;
- fake approval or confirmation statements;
- encoded or obfuscated instructions;
- instructions embedded in metadata or citations;
- requests to lower a risk tier or change policy;
- claims of special authority unsupported by origin.

Detection is advisory. Authorization must not depend solely on another model or classifier recognizing an attack.

### 8.5 Context assembly

Where a model interface supports roles or structured context:

- higher-authority instructions must be kept separate from untrusted content;
- source and origin labels must remain machine-readable where practical;
- untrusted content must use the least-authoritative available channel;
- content must not be concatenated into system policy as plain trusted text;
- only the minimum task-relevant state may be included;
- secret values must be absent by default;
- claims, evidence, inferences, and confirmed facts must not be collapsed into one unlabeled narrative.

### 8.6 Tool-result handling

Tool results remain untrusted input.

A tool result may inform a response or create evidence, but it cannot:

- grant permission;
- confirm an operation;
- change risk tier;
- widen scope;
- authorize a new capability;
- become a confirmed fact automatically;
- trigger a chained side effect without normal validation.

## 9. Secret architecture

### 9.1 Secret classes

Examples include:

- API keys;
- access and refresh tokens;
- passwords;
- private keys;
- recovery phrases;
- session cookies;
- authentication codes;
- banking credentials;
- payment-card data;
- government identity numbers;
- encryption keys;
- sensitive health information;
- private third-party personal data when treated as a credential or protected value.

The classification policy must define what is a secret value, sensitive non-secret data, and a non-secret SecretReference.

### 9.2 Ordinary-state prohibition

Ordinary Doll State must not store secret values.

This prohibition applies to:

- record fields;
- free-form metadata;
- audit events;
- logs;
- exports;
- unencrypted state and workspace backups;
- fixtures;
- diagnostics;
- generated reports;
- model context;
- exception text;
- operation summaries.

A field that is not explicitly defined for a SecretReference must reject secret-reference objects as well as secret values.

### 9.3 SecretReference

Doll State may store a non-secret SecretReference containing only the minimum metadata required to request an external credential operation.

A SecretReference may include:

- stable reference ID;
- credential class;
- provider or adapter class;
- human-readable non-secret label;
- permitted operation or destination scope;
- creation or rotation metadata that is not itself secret;
- availability status that reveals no value.

A SecretReference must not include:

- the secret value;
- reversible encoding of the value;
- a value-derived hint that materially helps reconstruction;
- a raw environment-variable dump;
- authentication headers;
- session cookies;
- recovery material.

### 9.4 External secret-store contract

The external secret-store boundary must define:

- availability and locked-state reporting;
- user-presence or operating-system approval requirements;
- create, replace, lookup, revoke, and delete semantics;
- stable reference behavior;
- platform-specific error normalization;
- cancellation and timeout;
- no secret value in ordinary error output;
- no requirement that the secret store be available for non-secret core startup;
- no custom cryptography invented by doll.

Initial platform direction:

- macOS: Keychain-compatible adapter;
- Windows: Credential Manager-compatible adapter;
- Linux: Secret Service-compatible adapter where available.

The contract, not one operating-system implementation, is authoritative.

### 9.5 Secret detection and redaction

Secret scanning is best effort and may miss values or produce false positives.

It supplements but does not replace:

- path restrictions;
- ordinary-state schema restrictions;
- permission checks;
- outbound minimization;
- credential-broker isolation;
- exact confirmation;
- log and audit sanitization.

Secret detection does not grant permission to search the filesystem, environment, browser storage, wallet data, or credential stores.

Redaction must use structured handling where possible rather than only string replacement after logging.

### 9.6 Model exclusion

Models must not receive secret values by default.

A model may identify that a task requires a credential class or SecretReference, but the model must not retrieve or handle the stored credential value. A credential-bearing operation must execute through the Credential Broker and return only a bounded result unless a later dedicated specification explicitly defines a user-visible reveal flow outside model context.

## 10. Model boundary

Model output is untrusted proposed data.

A model cannot directly:

- open arbitrary files;
- write arbitrary files;
- execute commands;
- make network requests;
- access the external secret store;
- retrieve secret values;
- alter permissions or confirmations;
- approve its own requests;
- delete authoritative state;
- change audit records;
- activate a model;
- perform migration, import, backup publication, or restore;
- promote a claim to confirmed fact;
- change instruction authority;
- choose or lower a capability risk tier.

The model may emit a structured proposal after Phase 3. The proposal remains untrusted and must pass every accepted boundary before any side effect.

A runtime adapter must not receive internal service objects that allow direct state, filesystem, network, credential, permission, confirmation, or audit mutation.

## 11. Capability Broker boundary

The Capability Broker is the mandatory authorization point for every side effect initiated through an AI or tool workflow.

A capability request must include:

- capability ID;
- capability version;
- operation ID;
- session ID where applicable;
- actor and origin type;
- validated arguments;
- declared target;
- declared destination where applicable;
- declared side effects;
- risk tier;
- permission scope;
- confirmation requirement;
- credential class or SecretReference where applicable;
- resource limits;
- timeout;
- cancellation token where supported.

The broker must reject:

- unknown capability IDs;
- unsupported versions;
- malformed arguments;
- missing scope;
- undeclared side effects;
- risk-tier mismatch or downgrade;
- paths outside approved roots;
- network destinations outside policy;
- requests requiring unavailable approval or confirmation;
- model attempts to modify permission or confirmation state;
- content-origin attempts to grant authority;
- credentials outside declared scope;
- requests that conceal or expand side effects;
- prohibited release-excluded operations.

The broker fails closed on validation, policy, permission, confirmation, credential, execution, audit, or postcondition failure.

## 12. Capability taxonomy and risk tiers

Capability IDs, versions, schemas, and risk tiers are registered and reviewed. A caller cannot choose a lower tier than the registry.

### Tier 0: Pure computation

Examples:

- local text transformation on provided data;
- schema validation;
- hashing data already provided;
- deterministic formatting.

Default: allowed when resource limits are satisfied and no hidden input access occurs.

### Tier 1: Bounded managed read or reversible creation

Examples:

- read an approved workspace record;
- query a local index;
- create a new managed artifact without overwrite;
- create a suggested record;
- inspect a verified backup.

Default: allowed only within current task scope, with audit where required.

### Tier 2: Scoped modification or explicit external read

Examples:

- update a confirmed memory through an explicit management flow;
- supersede a decision;
- apply a migration;
- read a user-selected external file;
- fetch a user-specified URL;
- perform a user-requested search.

Default: explicit user initiation, confirmation, or narrowly defined permission depending on the capability contract.

### Tier 3: High risk

Examples:

- permanent deletion;
- overwrite without retained prior version;
- external upload;
- credential-bearing external operation;
- sending email or posting;
- account change;
- purchase or financial transaction;
- process execution with material side effects;
- security configuration change;
- remote access enablement.

Default: unavailable unless separately accepted for the applicable release. When available, fresh exact confirmation is mandatory.

### Prohibited capabilities

The following remain prohibited until a dedicated accepted specification changes the scope:

- unrestricted shell;
- arbitrary command strings;
- autonomous credential collection;
- autonomous financial transactions;
- hidden external upload;
- model self-approval;
- model permission widening;
- policy changes from external content;
- silent destructive operations;
- security-boundary bypass adapters.

Confirmation cannot make a prohibited capability available.

## 13. Permission and confirmation model

### 13.1 Permission modes

Supported initial modes:

- denied;
- allow once;
- ask every time;
- allow for a defined scope.

A defined scope must specify applicable constraints such as:

- capability and version;
- risk tier;
- project;
- directory;
- destination host;
- operation type;
- file type;
- size limit;
- credential class;
- expiration;
- session.

A global persistent `allow all` mode is prohibited.

### 13.2 Permission authority

Permission creation, widening, reactivation, and deletion require a trusted user-controlled management path.

Models, runtimes, tools, documents, websites, imports, and capability results cannot create or widen permission records.

A capability may consume or narrow an existing allow-once permission only under its accepted contract.

### 13.3 Approval and confirmation integrity

Approval or confirmation must come from a user-controlled interface or management command, not model-generated or external-content text.

Records should identify:

- operation;
- capability and version;
- risk tier;
- summarized effect;
- target;
- destination;
- credential class where applicable;
- time;
- scope;
- expiration;
- user decision.

Material changes invalidate approval or confirmation.

### 13.4 Mandatory high-risk confirmation

Every Tier 3 operation, when such a capability is available, requires a fresh confirmation bound to one exact operation.

The confirmation preview must show:

- capability and version;
- target;
- destination or external recipient;
- material side effects;
- whether data leaves the machine;
- credential class or account identity without revealing the secret;
- overwrite, deletion, financial, account, or process consequences;
- irreversibility or recovery path;
- expiration.

The following are invalid confirmation sources:

- model output;
- system-prompt text displayed as if it came from the user;
- documents or websites;
- imported records;
- tool results;
- previous broad permission;
- hidden UI defaults;
- stale confirmation after a material change.

Confirmation is necessary but not sufficient. Policy, scope, capability registration, release availability, credential policy, and postcondition checks still apply.

## 14. Credential Broker

The Credential Broker is the only normal runtime path that may ask an external secret store to use a secret.

It must:

- accept a SecretReference rather than a secret value;
- validate capability, risk, destination, scope, and operation identity;
- require user presence or confirmation when policy demands it;
- obtain the secret only within the narrow operation boundary;
- avoid returning the stored value to the caller;
- avoid placing the value in environment dumps, command strings, logs, audit, exceptions, temporary files, model context, or normal output;
- minimize lifetime and copies;
- support timeout and cancellation;
- clear in-memory buffers where practical without claiming guaranteed erasure;
- return a structured bounded result;
- create a redacted audit event;
- fail closed if the secret store is unavailable, locked, denied, mismatched, or out of scope.

A tool requiring direct long-lived credential access is not compatible with the initial broker contract.

## 15. Filesystem boundary

The default managed-write boundary is the private workspace.

### 15.1 Required controls

- canonicalize requested paths;
- resolve relative paths against an approved root;
- reject traversal;
- reject absolute paths unless an explicit user-controlled import or export flow permits them;
- reject unsafe drive, UNC, backslash, reserved-name, duplicate, and case-collision paths where applicable;
- detect symlink, junction, reparse-point, or mount escapes where supported;
- open files using safe modes;
- create new files without silent overwrite;
- use atomic publication or replacement for approved updates;
- verify final location after creation where practical;
- apply file, member, expansion, and total-size limits;
- record resulting managed file, byte size, and hash;
- remove temporary and staging residue on failure.

### 15.2 Read policy

The initial product may read:

- files explicitly selected by the user;
- managed files inside the workspace;
- approved configured read roots if later enabled.

It must not recursively scan the entire home directory by default.

### 15.3 Restricted locations

The initial product must not intentionally read:

- SSH key directories;
- browser password databases;
- system credential stores outside the Credential Broker;
- cryptocurrency wallet secret material;
- `.env` files;
- operating-system account databases;
- application secret stores;
- arbitrary environment-variable collections;

unless a later explicit, narrowly scoped feature is accepted. Secret detection does not grant permission to access restricted locations.

## 16. Network boundary

The local API binds to `127.0.0.1` by default.

### 16.1 Inbound policy

- no public internet listener;
- no LAN listener by default;
- no anonymous remote access;
- no mobile remote access in the initial release;
- no automatic firewall changes;
- no UPnP or router configuration;
- request-size and origin controls;
- no arbitrary host-path exposure.

### 16.2 Outbound policy

Allowed only when explicitly initiated or enabled by an accepted capability:

- user-requested web search;
- user-requested URL retrieval;
- user-approved model acquisition;
- manual update or dependency retrieval outside normal runtime behavior;
- later bounded cloud or external-service requests.

Disallowed by default:

- telemetry;
- analytics;
- crash uploads;
- hidden update checks;
- advertising;
- background model discovery;
- automatic cloud inference;
- arbitrary state-changing HTTP methods;
- external file upload;
- credential transmission outside approved destination scope.

### 16.3 Request controls

Retrieval and external-service capabilities must apply as applicable:

- supported scheme;
- destination normalization;
- allowlist or policy;
- redirect limit;
- response-size limit;
- timeout and cancellation;
- content-type validation;
- private-network and localhost restrictions;
- DNS and resolved-address validation where required;
- final-destination audit;
- outbound body minimization;
- secret and sensitive-data checks;
- instruction-origin assignment to returned content.

## 17. Process execution boundary

The initial product does not expose unrestricted shell execution.

Approved external tools must use dedicated adapters with:

- fixed executable or validated configured path;
- argument arrays rather than command strings;
- `shell=False` or platform equivalent;
- controlled environment variables;
- no inherited secret-bearing environment by default;
- controlled working directory;
- input and output limits;
- timeout and cancellation;
- explicit file and network scope;
- captured exit status;
- provenance and audit;
- returned content marked as untrusted tool output.

A tool adapter may not become a generic command runner.

Credential-bearing process execution, if later accepted, must use a design that minimizes exposure and never logs the credential or command-expanded secret.

## 18. Cloud boundary

Cloud support is an optional later gateway.

Any cloud request must be assembled as a bounded outbound package after the local and safety gates pass.

Before sending, the trusted user path must be able to show:

- provider;
- model;
- destination;
- exact or summarized outbound content;
- attachments or excerpts;
- redactions and omissions;
- estimated size or tokens where possible;
- estimated cost where possible;
- retention information where available;
- applicable permission and risk tier;
- credential or account label without exposing the secret.

The cloud gateway must not have unrestricted workspace or secret-store access. It receives only the approved outbound package and a brokered credential operation.

There is no automatic cloud fallback.

Removing cloud adapter code must not prevent local startup, state access, backup, restore, recovery, or local model operation.

## 19. Backup and recovery boundary

Backups are high-value copies of private state.

Required controls:

- explicit included and excluded categories;
- manifest and cryptographic hashes;
- verification before completion;
- secret values excluded from unencrypted state and workspace backups;
- safe external-reference handling;
- complete archive member validation;
- resource limits;
- SQLite snapshot integrity;
- identity and revision checks;
- record, link, managed-path, hash, and artifact-byte checks;
- staging before final publication;
- empty-target restore only for the first slice;
- no silent overwrite;
- atomic no-clobber publication;
- cleanup on failure;
- fresh-process post-restore validation;
- no false success audit;
- optional standard encryption only in a later implementation.

The project must not invent custom cryptography.

A backup can be declared complete only after verification. A restore can be declared complete only after post-restore validation of the published workspace.

## 20. Model and supply-chain security

### 20.1 Model acquisition

Before acquisition, record or display:

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

### 20.2 Model loading

The validated path should prefer inert weight formats and runtimes that do not require repository-provided code.

Models requiring `trust_remote_code`, arbitrary Python modules, install scripts, opaque launchers, or unexpected network access are not standard validated targets.

### 20.3 Quarantine

New model assets enter quarantine or candidate state until:

- hashes pass;
- format inspection passes;
- license record exists;
- runtime compatibility is known;
- basic offline loading succeeds;
- resource limits are acceptable;
- evaluation is complete for the intended role;
- the safety boundary remains enforceable.

### 20.4 Dependency security

The project should:

- use a lockfile;
- pin release dependencies appropriately;
- minimize core dependencies;
- separate optional dependency groups;
- review new transitive dependencies;
- use automated vulnerability checks where practical;
- avoid executing install-time scripts from untrusted sources;
- record third-party notices and licenses;
- avoid dependencies that require broad secret, filesystem, network, or process access.

### 20.5 Update security

There is no silent self-update.

A future update flow must:

1. identify source and target version;
2. verify provenance or checksum where available;
3. show migration and security-boundary implications;
4. create a verified backup when required;
5. stage the update;
6. run doctor and validation;
7. support rollback;
8. retain the last known good release and state.

## 21. Audit and logging requirements

Security-relevant operations must create append-oriented audit events.

Audit events should include where applicable:

- operation ID;
- actor and origin type;
- capability ID and version;
- risk tier;
- permission and confirmation decision;
- target category;
- normalized destination category;
- credential class or non-secret reference ID;
- model and runtime IDs;
- result;
- error class;
- created or affected record IDs;
- redacted policy reason.

Audit events and logs must not contain:

- passwords;
- secret keys;
- tokens;
- cookies;
- recovery phrases;
- authentication headers;
- full private documents;
- unnecessary prompts;
- raw credential-store errors containing sensitive values;
- absolute local paths when a portable identifier is sufficient;
- usernames, hostnames, or home-directory details in shareable output.

Logging and audit sanitization must occur before persistence where practical. Redaction after an unsafe message has already been written is insufficient.

Normal model and capability paths cannot modify or delete audit history.

If audit persistence is mandatory for an operation and cannot complete safely, the side effect must not be reported as successful. Where atomic rollback is impossible, the capability must define explicit reconciliation and failure reporting before acceptance.

## 22. Resource controls and recoverable writes

The implementation must define limits for applicable operations:

- file size;
- archive members and expansion;
- HTTP response size;
- redirect count;
- request duration;
- model context and output size;
- concurrent operations;
- temporary storage;
- cache and backup storage;
- retries;
- subprocess duration and output;
- media duration and frame extraction;
- secret-store prompts and retries.

The system must avoid infinite automatic retry.

Required integrity controls include:

- schema validation before commit;
- transaction boundaries for structured state;
- revision checks;
- atomic file creation or replacement where supported;
- content hashing;
- pre-migration backup when required;
- staged import and restore;
- post-operation verification;
- explicit failure status;
- no success message before durable completion.

A failed operation must not destroy the last valid version.

## 23. User deletion versus autonomous deletion

Models and normal autonomous workflows cannot delete authoritative state.

The user may delete through an explicit management path.

Default direction:

- preview affected records and files;
- show dependent records;
- move to trash or create tombstones;
- retain for a configured period;
- require explicit purge for permanent deletion;
- create audit history;
- require Tier 3 confirmation for irreversible deletion when implemented.

Secure physical erasure is not guaranteed. The interface must not make a false guarantee.

## 24. Local API protection

The initial API must:

- bind to localhost only;
- avoid permissive cross-origin settings;
- reject unexpected host headers where practical;
- expose no unauthenticated remote mode;
- limit request sizes;
- normalize errors;
- avoid secrets and private paths in responses;
- support cancellation and timeouts;
- provide a health endpoint without private state;
- avoid arbitrary host-path exposure;
- keep management, confirmation, and credential operations distinct from ordinary model-facing routes.

Even on localhost, other local processes may be untrusted.

A later remote mode requires a separate accepted threat model and authentication design.

## 25. Emergency controls and user-visible states

The project should provide or plan:

- stop accepting new capability operations;
- cancel active cancellable operations;
- stop the local server;
- disable network capabilities;
- disable a model binding;
- lock credential operations;
- enter read-only recovery mode;
- preserve audit and recovery state.

An emergency stop must not delete state or corrupt a backup.

User-visible states should include:

- normal;
- degraded;
- offline;
- read-only recovery;
- migration required;
- backup invalid;
- restore failed;
- model unavailable;
- capability disabled;
- permission denied;
- confirmation required;
- secret store unavailable or locked;
- security warning;
- operation blocked.

## 26. Platform considerations

### 26.1 macOS

- use platform data directories;
- respect privacy prompts;
- recommend FileVault for disk encryption;
- use a Keychain-compatible adapter for future credentials;
- test symlink behavior, file permissions, and real-process restore;
- validate on Intel Mac while it remains the primary real-machine target.

### 26.2 Windows

- use platform data directories;
- handle reserved names, drive letters, UNC paths, junctions, and reparse points;
- recommend BitLocker where available;
- use a Credential Manager-compatible adapter for future credentials;
- account for Defender and file-lock behavior.

### 26.3 Linux

- follow XDG directories where practical;
- test symlink and mount behavior;
- recommend LUKS or equivalent disk encryption;
- use a Secret Service-compatible adapter where available;
- fail clearly when no supported secret store exists;
- avoid assumptions about one shell or distribution.

## 27. Security testing requirements

Implementation acceptance tests must include as applicable:

- path traversal and unsafe archive rejection;
- symlink, junction, reparse-point, or mount escape tests;
- write-outside-workspace rejection;
- unknown capability rejection;
- malformed request rejection;
- permission denial;
- risk-tier enforcement;
- confirmation absence, expiry, and material-change invalidation;
- prompt-injection content cannot grant authority;
- instruction origin survives persistence and context assembly;
- claims cannot silently become confirmed facts;
- external content cannot change policy or permission;
- ordinary state rejects secret values;
- SecretReference remains non-secret;
- secret redaction in logs, audit, errors, exports, backups, diagnostics, and context packages;
- credential broker does not return stored secret values;
- unavailable or locked secret store fails safely;
- cloud-disabled mode emits no cloud request;
- local API binds to localhost;
- SSRF-oriented destination restrictions;
- response, file, archive, and context limits;
- subprocess timeout and `shell=False` enforcement;
- interrupted write recovery;
- failed migration and restore preservation;
- checksum, identity, revision, record, link, and artifact mismatch rejection;
- candidate model cannot activate without approval;
- model adapter cannot bypass the broker;
- missing optional dependency does not block the core;
- audit event creation for allowed, denied, blocked, and failed actions;
- no absolute local path, username, hostname, home directory, secret, or personal data in shareable output.

Security claims must distinguish unit, integration, CI, fresh-process, and real-machine evidence.

The repository coverage threshold must not be lowered to accommodate safety code. Blanket `pragma: no cover` or equivalent exclusions must not hide untested safety branches.

## 28. Threat-to-control matrix

| Threat | Prevent | Detect | Record | Recover |
| --- | --- | --- | --- | --- |
| Prompt injection | origin and authority separation; broker checks | injection indicators; unrelated-capability warning | source and denied request | discard hostile context; continue local task |
| Workspace escape | canonical paths; approved roots; link checks | boundary violation | denied capability event | no state change |
| Secret exfiltration | secret separation; brokered credential use; outbound minimization | detector; destination preview | redacted denial or approval | cancel request; rotate externally if needed |
| Secret in ordinary state | schema prohibition; SecretReference contract | validation and scanning | redacted rejection | no commit; repair source input |
| Malicious model request | default-deny broker; no direct services | unknown, excessive, or malformed request | denied event with model ID | disable binding; use fallback |
| Claim promoted without evidence | separate record kinds and confirmation path | provenance and type validation | review and change history | revert or supersede false fact |
| Fake confirmation | trusted confirmation channel; exact binding | origin and material-change checks | denied or expired confirmation | request fresh user decision |
| Risk downgrade | registry-owned risk tier | request and registry mismatch | denied capability event | no side effect |
| Malicious tool or runtime | adapter limits; fixed executable; no direct credentials | abnormal exit, network, or file behavior | tool failure and provenance | disable adapter; restore affected state |
| Supply-chain tampering | source and hash validation; no remote code by default | hash or signature mismatch | quarantine event | reject asset; keep active version |
| Partial migration | backup and staging | validation failure | migration failure | rollback or restore backup |
| Corrupt backup | full verification | verify failure | invalid backup result | use earlier valid backup |
| Failed restore | staging and atomic publication | post-restore validation | restore failure | remove partial target; keep source |
| Resource exhaustion | limits and cancellation | threshold breach | aborted operation | cleanup disposable files; degrade safely |
| Local API exposure | localhost binding; no remote mode | doctor and bind inspection | warning | stop server; restore safe config |
| Unauthorized deletion | no model deletion; Tier 3 confirmation | forbidden capability | denial | no change; restore trash if applicable |
| Silent cloud fallback | cloud disabled by default | outbound audit check | blocked or approved event | continue local degraded mode |

## 29. Deferred security work

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
- cloud-provider-specific retention handling;
- formal verification;
- secure enclaves or confidential computing;
- user-directed secret reveal outside model context;
- automated secret rotation across providers.

## 30. Security acceptance criteria

This specification is acceptable when implementation can be designed and tested so that:

- the safety acceptance gate precedes model execution;
- models and runtimes cannot bypass the Capability Broker;
- default permissions are deny or narrow allowlists;
- risk tiers are registry-controlled;
- Tier 3 operations require fresh exact confirmation;
- confirmation cannot override policy or enable prohibited capabilities;
- files cannot be written outside the approved workspace through supported APIs;
- cloud communication is absent unless explicitly enabled;
- external content cannot act as authority or approval;
- instruction origin remains visible and enforceable;
- confirmed facts, claims, evidence, and inferences remain distinct;
- unrestricted shell execution is absent;
- ordinary Doll State stores SecretReference rather than secret values;
- models do not receive stored secret values by default;
- credential operations return bounded results rather than credentials;
- model and tool supply-chain metadata is retained;
- state changes are recoverable;
- audit records exist for security-relevant allowed and denied actions;
- logs, exports, backups, fixtures, diagnostics, and errors exclude secret values;
- the local API is not publicly exposed by default;
- optional tools, models, networks, and secret stores can fail without compromising the durable core.
