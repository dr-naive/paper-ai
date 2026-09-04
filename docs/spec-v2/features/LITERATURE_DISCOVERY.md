# Literature Discovery Contract

Status: CURRENT / AUTHORITATIVE

This document describes the current Discover workflow and its durable behavior.
Endpoint details belong in `docs/API.md`.

## Workflow

Discover has two user-visible stages:

```text
Requirement clarification
→ Search Intent
→ editable filters
→ bounded provider search
→ normalized results
```

Clarification may use bounded model reasoning to turn an incomplete research
request into a Search Intent. The user can review and edit the intent and
filters before searching.

Search is finite. The workflow may perform a small bounded re-search when
results are off-topic or insufficient, but it does not loop indefinitely.

## Search Intent and filters

Search Intent contains the research topic plus optional research question,
keywords, inclusion/exclusion preferences and query hints.

Supported filters include:

- start and end year;
- language;
- field;
- publication type.

Provider-supported filters are applied deterministically. Unsupported filters
are enforced during normalized result filtering where reliable metadata is
available and otherwise produce a warning rather than invented certainty.

## Provider boundary

Academic Search Provider and Remote Import Provider are separate interfaces.

The search provider returns normalized metadata. Provider-specific payloads do
not leak into frontend contracts. Normalized results include stable source
identity, title, authors, year, venue, abstract, DOI or equivalent identifiers,
source links and import/download availability.

The backend preserves the complete abstract returned by the provider.
Deduplication uses normalized DOI when present and stable source identifiers or
metadata fingerprints otherwise.

Semantic Scholar's public path is the primary search source and Crossref is a
metadata supplement/fallback. Optional credentials may improve service limits
but are not a V1 startup requirement.

401, 403, 429, timeout and invalid-provider responses are handled once within
the bounded workflow. The system does not repeatedly retry authorization or
quota failures and never creates synthetic papers to fill a result count.

## Result contract

Results are structured paper objects. A result includes enough metadata for
display, favoriting and an import-availability decision. Recommendation reasons
are concise, attributable to the current search intent and never presented as
full-text evidence.

If fewer valid papers are found than requested, the response returns fewer.
Zero and partial results are valid outcomes and include actionable warnings.

## Actions

### Favorite

Favorite stores validated paper metadata and source links in the owning
Project. It is idempotent by source identity. It does not create ProjectPaper,
download a file or start parsing.

### Download

Download is enabled only for an approved, available PDF source. Search-result
links alone do not establish download safety.

### Import

Remote import accepts only supported source identifiers and approved locators.
For V1, remote import is restricted to validated arXiv identity. It preserves
host allowlists, size limits, PDF magic-byte validation, temporary-file cleanup
and publisher access controls.

Successful import reuses the existing upload, parse, index and ProjectPaper
pipeline. Import state reflects real queued/processing/ready/failed state.

### Local upload

Local PDF upload remains a separate path into the same deterministic ingestion
pipeline.

## Persistence and execution state

Search execution state may be buffered in Redis for live progress and result
recovery. Durable favorites and imported Project papers remain in PostgreSQL or
their existing durable model fields.

User-visible stages use task language such as clarifying requirements,
searching papers, filtering results and supplementing the search. Raw provider
payloads, model reasoning and raw runtime events are not exposed.

## Ownership and safety

Every operation validates the authenticated user's Project ownership. Model- or
client-supplied user, Project, paper and result identifiers are never trusted
without server-side validation.

Search URLs are not automatically trusted as download URLs. Import does not
bypass paywalls or publisher access controls.

## Failure behavior

- Invalid filters return typed validation errors.
- Provider unavailability returns a bounded error or valid partial result.
- Unsupported import sources leave Import disabled.
- Failed import does not create a ready Project paper.
- Missing credentials identify the exact configuration action; they do not
  trigger arbitrary provider switching.

## Maintenance checks

Changes to Discover preserve normalized response typing, deterministic filter
behavior, deduplication, bounded search, ownership, import safety and the
independence of Favorite, Download and Import.
