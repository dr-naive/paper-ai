# Writing Workspace Contract

Status: CURRENT / AUTHORITATIVE

This document defines current Writing behavior. It relies on the existing
WritingDocument, revision, Tiptap, Citation Node, citation audit and export
foundations.

## Workspace

The Project Writing page has three functional areas:

```text
Outline | Editor | Writing Agent / Evidence
```

The outline navigates document structure. The editor owns document content and
selection. The right rail contains Agent actions, proposals and inspectable
Evidence.

Writing does not introduce a second editor or a separate document model.

## Editing and revisions

Document saves create or use the existing append-only revision contract.
Revision checks prevent stale AI proposals or concurrent edits from silently
overwriting newer content.

Standard editor behavior—including formatting, undo, citations, formulas,
tables, figures and export—remains independent of Agent availability.

## Rewrite

When text is selected, the client sends the selection, bounded nearby context,
current section and instruction. The server returns a proposal with its base
revision and structured citation information.

The proposal does not alter the document. The user explicitly chooses:

- Replace, which applies the proposal only if the revision and selection still
  match; or
- Copy, which leaves the document unchanged.

If the document changed, the selection no longer matches or the proposal is
stale, Replace is blocked and the user regenerates or copies manually.

## Generate paragraph

With no selection, V1 generates one paragraph at a time for the current
section. Generation uses bounded Writing Context and returns a proposal rather
than inserting content automatically.

Large section or full-document generation is outside the V1 interaction
contract.

## Evidence and citations

Evidence-backed generation may use only papers that:

- belong to the current Project;
- have been formally imported;
- are sufficiently parsed and indexed for retrieval.

Discover results, favorites, model memory and unverifiable web content are not
citation sources.

Each generated citation includes a structured mapping to its Project paper,
Evidence and source location. Citation Verification reports `verified`, `weak`
or `unsupported`. Unsupported citations are never styled or described as
verified.

If no supporting Evidence exists, the proposal reports that state or produces
appropriately limited uncited text; it does not invent a citation.

## Agent interaction

Quick actions are contextual shortcuts over the same rewrite or paragraph
generation contracts. They do not create separate backend capabilities.

User-visible progress uses task language such as finding supporting evidence
and verifying citations. Raw prompts, chain-of-thought, Tool calls and execution
events are not shown.

Conversation in the Agent panel is not document content and is not
automatically durable Project memory.

## Proposal states

A proposal may be generating, ready, applied, copied, stale, conflicted or
failed. The UI keeps the original selection/instruction context visible enough
for the user to judge the result.

Failures preserve the current document. Timeouts, model errors, missing papers,
missing Evidence and citation-verification failures are shown as distinct,
actionable states.

## Save and export

Save state reflects real persistence state. Export reads the current persisted
document and existing structured citations. Citation style changes rendering,
not citation identity or Evidence provenance.

Agent failure must not block manual editing, saving, revision history or
export.

## Ownership and security

All document, Project, paper and Evidence access is validated server-side.
Requests cannot use model- or client-supplied identifiers to access another
user's data or papers outside the Project.

## Maintenance checks

Writing changes preserve explicit Replace/Copy control, revision conflict
protection, one-paragraph generation, structured citations, Evidence-only
grounding, citation verification, manual editing and export compatibility.
