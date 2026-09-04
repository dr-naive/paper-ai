# Project Context and Evidence Contract

Status: CURRENT / AUTHORITATIVE

This document defines the current context, evidence and citation semantics.
It does not prescribe a migration plan or hypothetical component layout.

## Context model

Project context consists of distinct records with different lifecycles:

```text
Project Profile
Literature Memory
Paper Profile
Evidence
Writing Context
```

They are not concatenated into a universal Project memory prompt.

## Project Profile

The Project Profile represents the user's research scope: topic, field,
subject, question, goal, keywords, method direction and notes. It is the first
filter for discovery and writing context.

Profile updates are explicit Project updates. Ordinary conversations do not
silently rewrite it.

## Literature Memory

Literature Memory stores durable research decisions and preferences such as
search intent, inclusion/exclusion choices and user-confirmed literature
decisions.

It does not store raw provider payloads, raw reasoning, entire chat histories,
full papers or every transient search result. Entries remain typed and scoped
to the owning Project.

## Paper Profile

A Paper Profile is a compact, project-aware summary used to decide whether an
imported paper is relevant before retrieving full text.

Profiles are generated only for papers attached to the Project and sufficiently
parsed. Their lifecycle is `pending`, `generating`, `ready`, `failed` or
`stale`. Version and source fingerprints make regeneration and invalidation
observable.

Profile failure does not break the Reader, Project Papers or independent paper
QA.

## Evidence

Evidence is source-traceable support extracted from a formally imported Project
paper. It binds to the Project, paper and verifiable source location such as a
section, document element, page, bbox or indexed chunk.

Evidence status is `active`, `stale` or `invalid`. Source fingerprints detect
content drift. Removing a paper from a Project prevents its Evidence from being
used as current Project support.

Evidence is created on demand. The system does not pre-generate all possible
evidence for every paper.

## Writing context selection

Writing narrows context in stages:

```text
Project Profile
→ relevant ready/stale Paper Profiles
→ bounded candidate papers
→ candidate-scoped Hybrid Retrieval
→ Evidence candidates
```

The service limits candidates and retrieved chunks. Full documents, all Project
papers, all chat history and the entire writing document are not placed into
every model request.

When there are no imported papers, no usable profiles or no supporting
evidence, the service returns a typed state. It does not use Discover-only
metadata or model memory as a substitute.

## Citation mapping

Generated citations are structured mappings, not only textual markers. A
mapping identifies the Project paper, Evidence and source locator required to
render and inspect the citation.

Citation nodes in the editor preserve structured attributes through revisions
and export. Referential integrity is checked server-side against current
Project ownership and membership.

## Citation verification

Verification proceeds in layers:

1. Project, paper, Evidence and source-locator integrity.
2. Deterministic lexical/retrieval checks.
3. Structured semantic support verification through the existing LLM client.

Results are `verified`, `weak` or `unsupported`, with a code, reason and
confidence. Deterministic checks alone do not produce `verified`. Timeout,
authorization failure, rate limit, invalid model output and unavailable
verification also do not produce `verified`.

A generation workflow may offer one conservative claim adjustment followed by
re-verification. Citation audit never silently edits existing document content.

## Persistence

Durable truth remains in the existing Project, ProjectPaper, MemoryItem,
EvidenceItem, WritingDocument and analysis-card foundations. Temporary
selection, retrieval candidates and live workflow progress are not promoted to
durable memory by default.

Schema evolution requires Alembic migrations. Startup-time schema mutation and
blind revision stamping are forbidden.

## Ownership and prompt safety

All Project, paper and Evidence identifiers are validated from authenticated
runtime context. Model-supplied identifiers cannot expand the authorized
candidate set.

Prompts receive only the minimum current task context. Raw provider payloads,
secrets, unrelated chats and unrelated papers are excluded.

## Maintenance checks

Changes preserve context separation, candidate narrowing, Evidence provenance,
Project ownership, structured citation mapping and fail-closed verification.
