---
title: Portable Memory Is Not AI Continuity: PAM, PLUR, PROJECTMEM, and doll
published: false
tags: ai, opensource, architecture, localfirst
series: doll
canonical_url: https://doll.badjoke-lab.com/notes/portable-memory-not-ai-continuity/
description: PAM, PLUR, PROJECTMEM, and doll address different layers of persistent AI memory and continuity. Here is why interchange, recall, project experience, and authority should stay separate.
---

A few days ago I wrote that AI memory is becoming more portable, but portability is still not the same thing as continuity.

The obvious next question is whether that distinction already exists elsewhere in more concrete technical form.

It does.

Three projects are especially useful to compare with **doll**: Portable AI Memory (PAM), PLUR's Engram specification, and PROJECTMEM. They overlap with parts of what doll is trying to do, but they start from different problems and make different things canonical.

This is not a ranking and it is not a competitor roundup. The useful question is narrower:

> **Which ideas should doll adopt, which boundaries should remain separate, and where should interoperability replace another private format?**

## The short version

The four systems are easiest to understand as different layers:

- **PAM:** how memory can cross system boundaries in a vendor-neutral interchange format.
- **PLUR / Engram:** how persistent memories can be retrieved, activated, reinforced, and allowed to decay over time.
- **PROJECTMEM:** how project experience can be recorded as local event history and used to warn an agent before it repeats a known failure.
- **doll:** how memory, projects, decisions, work state, provenance, permissions, recovery, and model-independent execution state can remain resumable when the model or provider changes.

Those are not mutually exclusive answers.

The most useful result of comparing them is that doll should **not** try to turn all four jobs into one record type or one proprietary memory format.

## PAM: standardize what crosses the boundary

Portable AI Memory is the clearest answer to the interchange problem.

PAM v1.0 defines a vendor-neutral JSON format for moving user memories between systems. Its specification includes provenance, lifecycle state, confidence, relations, access metadata, integrity information, optional conversation files, and optional embeddings.

The most important scope boundary is simple:

> **PAM is an interchange format, not a storage format.**

That distinction fits doll unusually well.

A portable format does not need to become the internal database schema. The internal system can preserve richer local semantics while importing and exporting a stable external contract at the boundary.

That is the approach doll now takes. PAM is treated as an adapter target rather than as Doll State itself. The implemented PAM path is deliberately staged: external data is parsed and mapped, ambiguous or unsupported semantics stay visible, imported memories require explicit review before becoming normal confirmed MemoryRecords, and confirmed non-secret memories can be exported back to bounded PAM v1.0 output.

This matters because a field that exists in two systems is not necessarily authoritative in the same way.

An imported lifecycle label, confidence score, relation, or access declaration may be useful evidence without automatically becoming a doll permission, decision, or policy.

PAM therefore answers an important part of the portability problem without needing to answer the entire continuity problem.

## PLUR: memory is not just stored or retrieved

PLUR's Engram specification starts from a different question.

Its Engram model describes an atomic unit of learned knowledge that is individually addressable, activation-weighted, and decay-aware. It specifies activation, decay, reinforcement, associations, usage feedback, and a search pipeline.

The useful idea here is not merely "store more metadata."

It is that **what a memory says** and **how useful it is to retrieve right now** are different kinds of state.

Consider a durable memory:

> The user prefers local-first tools when the core workflow can remain complete offline.

The content of that memory should not silently change because it was retrieved ten times this week, ignored for a month, or ranked lower by a new search algorithm.

That observation sharpened an important boundary in doll: confirmed MemoryRecord content remains authoritative memory, while recall state is derived and rebuildable.

Ranking, activation-like signals, retrieval scores, and future usage signals belong to the recall layer, not to the truth of the memory itself.

This also means doll does not need to copy PLUR's engine-specific state into its canonical memory schema. A future PLUR adapter can preserve and translate what is meaningful without pretending that every activation or decay parameter is universal memory truth.

## PROJECTMEM: project history can act before the next mistake

PROJECTMEM is closer to a different part of doll.

Its paper describes a local-first, event-sourced memory and judgment layer for coding agents. Development history is recorded as append-only typed events such as issues, attempts, fixes, decisions, and notes. The system then projects that history into compact summaries and includes a deterministic pre-action gate that can warn before a previously failed fix is repeated or a known-fragile file is edited.

The key insight is that project memory is not only something an agent searches after it gets confused.

Prior experience can be checked **before** an action is repeated.

doll now has a related but deliberately separated pair of concepts:

- **ProjectExperienceRecord** stores append-oriented semantic work history such as observations, hypotheses, attempts, outcomes, resolutions, and lessons.
- **ContinuityPreflight** reads accepted project state before a proposed action and can surface a directly relevant prior failure as an evidence-linked warning.

But there is an important authority boundary.

A past failed attempt is not automatically a permanent prohibition. Imported project history is not automatically trusted. A model-proposed lesson does not become a policy. A remembered claim that work is complete does not complete the WorkItem.

In doll, prior experience can warn.

Hard blocking still comes from existing authoritative state such as an applicable policy denial, a blocked or incomplete WorkItem dependency, an unapproved required procedure, a permission decision, or a capability safety boundary.

That separation is intentional:

> **Experience can inform authority without quietly becoming authority.**

## One word, several kinds of state

The comparison makes "memory" look too broad to be a useful architecture by itself.

At least five different layers appear.

### 1. Canonical durable state

Things the system is expected to preserve as authoritative user-owned state: confirmed memory, project scope, accepted decisions, work state, permissions, policies, artifacts, and their provenance.

### 2. Derived recall state

Search indexes, ranking scores, activation-like values, retrieval candidates, and other state that can be rebuilt from authoritative data.

### 3. Experience history

What was tried, what failed, what worked, what was later corrected, and which evidence supports that history.

### 4. Interchange formats

External contracts such as PAM that let some of those semantics cross system boundaries without dictating the local storage engine.

### 5. Pre-action continuity checks

Deterministic checks that ask whether accepted state already contains a blocker, confirmation requirement, incomplete dependency, required procedure, or relevant failure before another action begins.

Combining all five into a single "memory object" would make portability look simpler while making authority harder to reason about.

## The hard part is not mapping fields. It is mapping meaning.

Suppose two systems both have a field called `confidence`.

One may mean model-estimated extraction confidence. Another may mean a user-reviewed trust state. Treating those as interchangeable because the field names look similar would create semantic loss while claiming successful migration.

The same problem appears with:

- active versus authoritative;
- remembered versus confirmed;
- decision versus historical note;
- permission versus imported access metadata;
- failed attempt versus permanent prohibition;
- retrieval score versus memory truth;
- conversation history versus current project state.

A continuity system therefore needs to preserve loss and uncertainty, not hide them.

When an external format cannot express a doll semantic exactly, the safer result is an explicit partial mapping, preserved original evidence, or quarantine—not a fabricated equivalence.

## Why doll should prefer adapters over another universal format

It would be easy for doll to define its own grand interchange format for memory, projects, decisions, experiences, permissions, conversations, and everything else.

That would also be an easy way to create another island.

Where a useful external contract exists, the better default is to adapt to it.

PAM is already the first general memory-interchange target in doll. PLUR and PROJECTMEM are later interoperability candidates where their semantics match a real boundary. MCP is also later work rather than something that should be smuggled into the core state model just because several adjacent projects use it.

The canonical Doll State can remain richer than any one interchange format while still avoiding gratuitous proprietary formats at the edges.

## These projects are more complementary than competitive

PAM is strongest as a portable contract.

PLUR is useful for thinking about retrieval dynamics and memory-use state.

PROJECTMEM demonstrates how local project history can become deterministic pre-action judgment.

doll needs pieces of all three problem areas because its target is broader continuity across models, runtimes, providers, interfaces, and machines.

That does not make doll a superset of those projects. It means its architecture has to decide where their ideas belong without collapsing their different semantics into one internal abstraction.

The resulting rule is simple:

> **Standardize interchange. Derive recall. Preserve experience. Keep authority explicit.**

That is a much more useful foundation for continuity than treating every persistent fact, score, event, and permission as "memory."

## What comes next

The comparison has already changed concrete boundaries in doll:

- MemoryRecord is separated from derived RecallState;
- PAM is an adapter instead of the canonical store;
- ProjectExperienceRecord is append-oriented history rather than current project authority;
- ContinuityPreflight can use prior failures as warnings without allowing imported or model-proposed experience to manufacture a hard denial.

The next article in this series will focus on those design changes themselves: what changed, what was deliberately not adopted, and which interoperability work remains later.

The larger goal remains the same: the model can change, the provider can change, and the interface can change without forcing the user's durable AI environment to start over.

---

## Sources

1. [Portable AI Memory — Specification v1.0](https://portable-ai-memory.org/spec/v1.0/)
2. [PLUR — The Engram Specification v2.1](https://plur.ai/spec.html)
3. [PROJECTMEM paper](https://arxiv.org/abs/2606.12329)
4. [PROJECTMEM source repository](https://github.com/riponcm/projectmem)
5. [doll — Post-IMP-083 Memory & Continuity Roadmap](https://github.com/badjoke-lab/doll/blob/main/docs/spec/09a-post-imp-083-memory-continuity-roadmap.md)
6. [doll — Memory Interoperability, Recall, and Project Experience specification](https://github.com/badjoke-lab/doll/blob/main/docs/spec/03c-memory-interoperability-recall-and-project-experience.md)
7. [doll — ProjectExperienceRecord implementation](https://github.com/badjoke-lab/doll/blob/main/src/doll/project_experience.py)
8. [doll — ContinuityPreflight implementation](https://github.com/badjoke-lab/doll/blob/main/src/doll/continuity_preflight.py)

This is a syndicated version of the canonical doll article:
https://doll.badjoke-lab.com/notes/portable-memory-not-ai-continuity/

External specifications, paper metadata, and current project descriptions were checked on August 16, 2026. PAM claims refer to the published v1.0 specification; PLUR claims refer to the Engram v2.1 specification; PROJECTMEM architecture claims distinguish the cited research paper from the current source repository. Statements about how these ideas should map into doll are doll's design analysis, not claims made by the external projects.

Disclosure: This article was prepared with AI assistance and reviewed, edited, and approved by the project maintainer.
