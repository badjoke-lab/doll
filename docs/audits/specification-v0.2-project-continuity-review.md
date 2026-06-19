# Specification set 0.2 project-continuity review

**Audit status:** Content review complete; final-head CI pending  
**Target specification set:** 0.2  
**Date:** 2026-06-19

## 1. Scope

This review records the controlled specification change that adds project continuity and resumption to doll without replacing the existing detailed 0.1 specifications.

The review covers:

- new ADR-007;
- new normative project-continuity specification `03b`;
- new blocking project-continuity acceptance suite `08b`;
- specification index and deterministic generation order;
- roadmap placement after Phase 4A portability and before local model integration;
- repository-current-state documentation after IMP-014;
- the minimal ADR-006 connection to ADR-007.

## 2. Baseline

The change is based on main commit:

```text
0fa1fb78f49024f3b04dbd8c1b911064c6bdc7a1
```

IMP-014 is complete and IMP-015 is next. No model runtime, cloud model, external secret-store adapter, credential broker, or general tool-execution path is connected.

## 3. Accepted extension

Specification set 0.2 retains the two top-level pillars:

```text
1. Continuity
2. Safety boundary
```

Project continuity is a required component of Continuity.

The new normative documents define:

- Continuity Contract extension C-13;
- ProjectRecord v2 while valid ProjectRecord v1 remains readable;
- WorkItemRecord;
- ProcedureRecord;
- ProjectCheckpointRecord;
- relevant-record checkpoint freshness and deterministic basis fingerprints;
- deterministic read-only project status;
- deterministic project-scoped Resume Bundle;
- generated, non-authoritative `HANDOFF.md`;
- Doll State Package format v2;
- supported package-v1 read compatibility;
- PROJ-001 through PROJ-012.

DecisionRecord remains v1 during the first project-continuity implementation.

## 4. Authority conclusion

Models, runtimes, tools, imports, retrieved content, conversations, issue descriptions, procedures, and handoff files may create proposals or review candidates where the target contract allows it.

They cannot by themselves:

- complete or cancel work;
- approve, deprecate, or supersede a procedure;
- clear an authoritative blocker;
- confirm a checkpoint;
- change the project objective, scope, exclusions, or success criteria;
- create permission, confirmation, credential scope, or instruction authority.

A deterministic verifier may record bounded evidence. It does not automatically complete the entire work item in the first implementation.

## 5. State, package, and recovery conclusion

WorkItemRecord, ProcedureRecord, and ProjectCheckpointRecord are authoritative state.

The first implementation that makes one of them creatable must also preserve it through:

- package export, inspection, verification, and import;
- state and workspace backup;
- restore to an empty target;
- record-count, checksum, and typed-link validation;
- fresh-process inspection.

The current package rejects unsupported authoritative record types. Package format v2 is therefore a blocking prerequisite rather than a later cleanup.

New doll versions implementing v2 retain supported v1 inspection, verification, and import. Missing project-continuity state in v1 is not fabricated. Lossy downgrade or target export requires explicit mapping or loss reporting.

## 6. Checkpoint and derived-view conclusion

Checkpoint freshness is based on relevant basis record revisions and a deterministic fingerprint. An unrelated workspace mutation does not make every checkpoint stale merely because the global state revision advanced.

A stale checkpoint remains inspectable and is never silently rewritten.

Project status, roadmap views, Resume Bundle files, and `HANDOFF.md` are generated views rather than parallel authoritative records.

## 7. Implementation-order conclusion

```text
IMP-014 complete
  -> IMP-015 through IMP-023
  -> Phase 3 safety gate
  -> Phase 4A canonical portability and PORT gate
  -> Phase 4B project continuity and PROJ gate
  -> IMP-024 through IMP-029 local model integration
```

The active Phase 3 sequence is not renumbered or interrupted. This pull request contains no runtime implementation.

## 8. Preservation of existing specifications

The existing detailed product, architecture, state, security, recovery, release, and core acceptance documents remain intact.

The new `03b` and `08b` documents extend them under the conflict-resolution rules in `00-index.md`. They do not weaken or replace earlier detailed requirements.

The change updates only the governing and discovery material needed to make the extension visible and correctly sequenced:

- `README.md`;
- `AGENTS.md`;
- `SECURITY.md`;
- ADR-006 and new ADR-007;
- `00-index.md`;
- new `03b` and `08b`;
- `09-development-roadmap.md`;
- deterministic specification generation;
- this audit record.

## 9. Deferred decisions

The change does not select exact Phase 4B implementation identifiers, exact CLI flags, automatic conversation extraction, automatic procedure execution, automatic completion, DecisionRecord v2, issue-tracker synchronization, multi-user collaboration, portfolio management, or mandatory live-model semantic scoring.

## 10. Content verification

Content review confirms:

- ADR-007 is indexed;
- `03b` and `08b` are normative generated-spec sources;
- C-13 and all three new record types are defined;
- package v2 and supported v1 compatibility are explicit;
- authority and import boundaries are explicit;
- checkpoint freshness avoids global-revision invalidation;
- generated status and `HANDOFF.md` remain non-authoritative;
- Phase 4A and Phase 4B precede local model integration;
- current status is complete through IMP-014 with IMP-015 next;
- no Python runtime code, dependency change, physical schema migration, package-v2 implementation, or model path is added.

## 11. Remaining merge checks

- deterministic generated specification is current on the final head;
- normal CI passes on the final head;
- specification workflow passes on the final head;
- the pull request is reviewed and marked ready.

## 12. Freeze rule

After merge, specification set 0.2 becomes the project-continuity implementation baseline.

Weakening model independence, trusted completion authority, procedure approval, blocker integrity, checkpoint confirmation or freshness, package preservation, Resume Bundle integrity, recovery coverage, supported v1 compatibility, or explicit loss reporting requires a new normative specification change and, where architectural, a new ADR.
