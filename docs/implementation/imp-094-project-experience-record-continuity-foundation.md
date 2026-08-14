# IMP-094 — ProjectExperienceRecord continuity foundation

Status: implementation candidate for Issue #286

## Purpose

IMP-094 implements the first bounded `ProjectExperienceRecord` slice required by the accepted memory/continuity specification. The record preserves semantic work history that should survive model, conversation, process, backup, and machine-boundary changes without turning Doll into a global event-sourced system and without replacing revisioned current state.

The governing requirements are:

- `docs/spec/03c-memory-interoperability-recall-and-project-experience.md` §11;
- `docs/spec/08c-memory-interoperability-recall-and-project-experience-acceptance.md` MCON-009;
- `docs/spec/09a-post-imp-083-memory-continuity-roadmap.md` §5.6;
- repository-wide package, backup, restore, secret, and authority rules in `AGENTS.md`.

## Implemented record contract

`src/doll/project_experience.py` adds a version-1 authoritative semantic-history record with these supported event kinds:

- `observation`;
- `hypothesis`;
- `attempt`;
- `outcome`;
- `resolution`;
- `lesson`.

Where an outcome is applicable, the bounded values are:

- `worked`;
- `failed`;
- `partial`;
- `unknown`.

The record keeps explicit links to its project and, when present, its work item, evidence, related records, source records, and a prior experience replaced by a correction.

## Assertion and provenance boundary

The initial assertion classes intentionally distinguish who or what produced the semantic claim:

| Assertion state | Required actor | Doll provenance | Authority meaning |
| --- | --- | --- | --- |
| `user_recorded` | user | `user-created` | user-authored semantic history |
| `user_confirmed` | user | `user-confirmed` | explicitly confirmed semantic history |
| `deterministic_system` | system | `system-generated` | deterministic system observation, not user authority |
| `imported_external` | importer | `imported` | external claim retained with imported provenance |
| `model_proposed` | model | `model-proposed` | model proposal, not trusted current-state authority |

An assertion-state/actor mismatch fails closed.

Creating a ProjectExperienceRecord does not update ProjectRecord scope or objective, change WorkItem status, create a DecisionRecord, approve a procedure or checkpoint, grant a permission, or change policy/capability authority. The MCON-009 test records all initial event/assertion classes and verifies that the linked ProjectRecord and WorkItem revisions and statuses remain unchanged.

## Append-oriented correction

Published semantic experience is not edited in place by this slice.

`ProjectExperienceService.correct()` creates a new version-1 record with a new ID and `supersedes_id` pointing to the prior experience. The original record remains inspectable with its original summary, outcome, and revision. If a correction does not supply a replacement outcome, the prior outcome is preserved in the new linked record rather than silently erased.

This is semantic-history append behavior only. It does not make all Doll state append-only.

## Link validation

Creation validates:

- the referenced project exists and is a valid ProjectRecord;
- an optional work item exists and belongs to the same project;
- evidence links resolve to EvidenceRecords;
- related/source record IDs exist;
- `supersedes_id` resolves to an earlier ProjectExperienceRecord for the same project;
- a non-secret experience cannot link to a secret record;
- summaries cannot contain private absolute host paths.

State Package validation independently re-checks the package-internal project, work-item, evidence, source, related-record, and supersession graph so a package cannot pass merely because each individual JSONL row is structurally valid.

## Secret and sensitivity behavior

Project experience is ordinary Doll State, not secret material storage.

The initial service explicitly rejects `sensitivity="secret"` and directs secret material to the existing `SecretReference` boundary. It also rejects private absolute host paths in semantic summaries and prevents non-secret experience records from linking to secret records.

This keeps ProjectExperienceRecord aligned with the repository-wide rule that secret values do not belong in ordinary Doll State.

## State Package continuity

Package format version 2 gains one optional authoritative record category:

- record type: `project_experience`;
- member: `records/project-experiences.jsonl`;
- validator: ProjectExperienceRecord version-1 validator.

The member is optional so previously valid version-2 State Packages remain compatible. New packages containing project experience export deterministic JSONL and validate the cross-record graph before import.

MCON-009 evidence exports a package containing a failed experience and a later resolution, verifies it, imports it into a new workspace, and confirms that both records and their project/work relationships survive.

## Backup and restore

State backup already wraps a verified Doll State Package. Because the new authoritative category participates in State Package v2, the same slice exercises the existing backup/restore path rather than inventing a parallel backup format.

The focused acceptance test:

1. creates ProjectExperienceRecord data;
2. creates a state backup;
3. restores into a new workspace;
4. requires `fresh_process_validated == true`;
5. reopens the restored state read-only;
6. inspects the experience in a separate Python process with model adapters disabled and proxy/network use disabled.

No model or network is required for inspection.

## Resume Bundle v1 rule

IMP-094 does not silently enlarge Resume Bundle v1 with a new semantic-history payload.

Instead, the bundle now declares the deterministic rule:

- `selection_options.project_experience = "omitted_in_bundle_v1"`;
- `omitted_record_counts.project_experiences` records the number of non-secret project-experience records intentionally omitted for the selected project;
- the omission reason explicitly states that ProjectExperienceRecord content is not included in Resume Bundle v1.

The acceptance test verifies that experience text is absent from the ZIP while the omission remains machine-readable. This preserves the existing bundle format while making the loss boundary explicit rather than accidental.

## MCON-009 evidence

`tests/test_imp_094_project_experience.py` covers:

- every initial semantic event kind;
- every initial assertion/provenance class;
- a failed attempt/outcome and later successful resolution;
- no mutation of linked ProjectRecord/WorkItem authority;
- actor/assertion mismatch rejection;
- append-only correction through `supersedes_id`;
- secret-link and private-host-path rejection;
- explicit rejection of secret ProjectExperienceRecord content;
- State Package export, verification, cross-link validation, and import;
- state backup and restore;
- fresh-process read-only inspection without model/network dependency;
- deterministic Resume Bundle v1 omission and absence of experience text.

The focused validation also reruns the existing State Package, backup, restore, and Resume Bundle suites. Before the normal PR-wide CI, the focused run passed formatting, Ruff, mypy, and 50 focused/regression tests.

## Persisted-state and migration note

IMP-094 adds no new SQLite table and no state-database migration. ProjectExperienceRecord uses the existing common authoritative-record envelope with schema version 1.

The compatibility change is at the State Package inventory layer: package format version 2 accepts the new category as optional. Old version-2 packages without the member remain valid.

## Explicit non-goals

IMP-094 does not implement:

- ContinuityPreflight;
- automatic warning or action blocking from prior experience;
- PROJECTMEM import;
- PLUR import/export;
- MCP;
- automatic model extraction of experience from conversations;
- automatic correction, merge, deletion, or promotion of experience;
- new permission, capability, policy, procedure, checkpoint, decision, or work-completion authority;
- cloud or network behavior.

Those remain separate bounded slices under the accepted roadmap.
