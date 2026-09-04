# PaperAI V1 Product Contract

Status: CURRENT / AUTHORITATIVE

This document defines the current V1 product boundary. It describes supported
user outcomes, not implementation phases or migration work.

## Product model

PaperAI supports two connected modes:

```text
Independent Paper Reading

Project
→ Discover
→ Papers
→ Writing
```

The independent Reader remains a first-class entrypoint. Project workflows may
open a project paper in the same Reader but do not replace its ingestion,
parsing, retrieval, citation-location or chat behavior.

## Project workspace

A Project has exactly four primary pages:

1. Overview
2. Discover
3. Papers
4. Writing

Overview presents the research scope and entrypoints into the workflow. It is
not a KPI dashboard or a universal Project chat surface.

A Project requires a title and research topic. Its research scope may include
field, subject, question, goal, keywords, method direction and notes. Project
data is private to its owner.

## Discover

Discover turns a research requirement into a bounded academic search:

```text
requirement clarification
→ editable search intent and filters
→ real provider search
→ normalized paper results
```

The minimum filters are year range, language, field and publication type.
Filters are applied deterministically when supported by the provider.

Results are structured paper records, never prose that the client must parse.
The full provider abstract is preserved by the backend; visual truncation is a
frontend concern. The system returns only real results and may return fewer
than the requested count.

Result actions are independent:

- Favorite stores metadata and links only.
- Download is available only when an approved PDF source exists.
- Import obtains approved full text and enters the existing parse/index
  pipeline.
- Details show the normalized metadata and available source links.

Favorite-only and Discover-only records are not Project Papers and cannot be
used as writing evidence.

## Papers

Papers lists formally imported or explicitly attached Project papers. A paper
remains governed by the existing Paper, PDF, parse, section, element, table,
image, retrieval and Reader contracts.

Opening a Project paper uses the existing Reader. Project integration must not
create a second reader, second parser, second vector index or second citation
location model.

## Writing

The Writing workspace is:

```text
Outline | Editor | Writing Agent / Evidence
```

It reuses WritingDocument, append-only revisions, Tiptap, Citation Nodes,
citation audit and export.

When text is selected, the Agent returns a proposal. The user explicitly
chooses Replace or Copy. The Agent never silently edits the document.

With no selection, V1 generates one paragraph at a time. Evidence-backed
generation uses only Project papers that have been formally imported and are
ready for retrieval.

Generated citations use structured mappings to Project Paper and Evidence
records. Citation verification is required before a claim is presented as
verified. Unsupported or unverifiable claims remain visibly unverified.

## Project context

Project context is not a single memory string. The current concepts remain
separate:

- Project Profile
- Literature Memory
- Paper Profile
- Evidence
- Writing Context

Ordinary conversation history does not automatically become long-term Project
memory. Writing narrows context from the Project Profile to relevant Paper
Profiles, candidate papers, full-text retrieval and Evidence.

## Agent visibility

Agent behavior is an internal implementation mechanism. The UI may show clear
task stages such as searching papers, screening results, finding evidence and
verifying citations.

The product does not expose Tool, Skill, ReAct, chain-of-thought, raw provider
payloads or raw execution event logs.

## V1 exclusions

The following are not primary V1 product surfaces:

- Research Map
- Reading Plan
- Evidence Matrix
- Experiment Design
- Submission Suggestion
- Agent Activity or Agent Center
- Tool or Skill management
- universal Project Chat

Compatibility code may remain, but new work must not expand these directions
without an explicit product decision.

## Product invariants

- Never fabricate papers, evidence, progress or citations.
- Never cite Discover-only metadata, model memory or unverifiable web claims.
- Never bypass Project ownership or server-side identifier validation.
- Never turn remote import into an arbitrary URL downloader.
- Never overwrite writing content without an explicit user action.
- Preserve existing Reader, retrieval, citation, revision and export behavior.
