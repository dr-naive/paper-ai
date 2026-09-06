# PaperAI Frontend UI System

Status: CURRENT / AUTHORITATIVE

This document combines the durable frontend information architecture, visual
system and interaction rules. It describes the implemented UI contract, not a
redesign phase.

## Product navigation

The global application provides Projects, Independent Reading and Settings.
A Project provides exactly four primary pages:

```text
Overview | Discover | Papers | Writing
```

No Agent Center, Tool/Skill UI, Research Map, Evidence Matrix or universal
Project Chat appears in primary navigation.

Reader navigation has two explicit business contexts while reusing one Reader
implementation:

- Independent Reading enters `/paper/:id` and returns to `/library`.
- Project Papers enters `/projects/:projectId/papers/:paperId/read` and returns
  to the current Project Papers page with the project identity intact.

Shared headers accept typed Vue Router locations for Back and breadcrumbs.
Navigation must not infer the destination from browser history or an arbitrary
`return_to` string. The legacy `/paper/:id?project_id=...` form remains a
compatibility bridge and is normalized to the semantic project route.

## Visual direction

The interface is an editorial research workspace: restrained, professional,
paper-like, readable for long sessions and dense without feeling crowded.

The implemented visual baseline uses:

- neutral gray-white surfaces;
- a restrained terracotta brand accent;
- semantic success, warning and error colors;
- compact typography and controls;
- consistent spacing, radius, shadow and focus tokens;
- Arco Design Vue components and icons.

Exact token values live in `frontend/src/styles/` and related global component
styles. Code tokens are the current numeric source of truth; this document owns
their semantics and constraints.

Do not introduce gradients, glassmorphism, neon effects, decorative dashboard
metrics, emoji icons or Unicode glyphs as product icons.

## Application shell

Desktop uses a fixed global sidebar and a stable main-content surface. Active
navigation is visually distinct without excessive decoration. Project context
is shown in the header, followed by the four Project tabs.

At narrower widths, navigation and multi-column workspaces collapse without
removing core actions or creating horizontal page overflow.

## Shared interaction rules

- Buttons use consistent primary, secondary, ghost and destructive hierarchy.
- Icon-only controls have accessible labels and tooltips where meaning is not
  obvious.
- Focus-visible styles are always present for keyboard users.
- Disabled controls explain unavailable actions when context is required.
- Loading, empty and error states reflect real application state.
- Destructive actions require clear confirmation.
- Toasts report results; they do not replace recoverable inline errors.
- Reduced-motion preferences are respected.

No core action may be a dead button, fake progress indicator or permanent
"coming soon" placeholder.

## Projects and Overview

The Projects page prioritizes project identity, research topic, status and the
next meaningful action. Destructive project actions live in a deliberate
overflow or confirmation flow.

Overview presents the Project research scope and routes into Discover, Papers
and Writing. It does not invent analytics or expose internal runtime metrics.

## Discover

Discover displays requirement clarification, editable filters, execution state
and normalized paper results as separate visual regions.

Result cards prioritize title, authors/year/venue, abstract, relevance reason
and metadata. Import is the primary acquisition action when available;
Favorite, Details and Download remain distinct. Full abstracts may be visually
collapsed but are never truncated in backend state.

Provider engineering terms, raw payloads and raw execution logs are not shown
to users.

## Papers

Project Papers uses a compact table organized around paper identity, year,
processing/reading state and actions. Author and venue metadata support the
title rather than competing with it.

Opening a row or its explicit action enters the existing Paper Reader. The page
does not duplicate Reader controls or paper content.

## Writing

Desktop Writing uses Outline, Editor and Agent/Evidence regions. The editor is
the primary reading surface. The right rail switches between Agent and Evidence
without obscuring document content.

The toolbar uses grouped controls and Arco icons rather than a long row of text
buttons. Citation nodes are visually distinct and inspectable but remain part
of the editor document.

Proposal cards show instruction context, proposed text, citation status and
explicit Replace/Copy actions. Replace is never implicit. Evidence items expose
paper identity, source location, snippet and verification state.

## Responsive behavior

- Wide desktop retains the full sidebar and three-column Writing layout.
- Medium desktop may reduce panel widths while protecting editor readability.
- Tablet collapses secondary panels into drawers or switchable regions.
- Mobile uses a single primary column with reachable navigation and actions.

Responsive changes preserve task order, labels, ownership checks and safety
actions. Hidden panels must remain reachable.

## Accessibility

Interactive elements use semantic controls, keyboard operation, visible focus,
accessible names and appropriate ARIA state. Color is never the sole carrier of
status. Text and interactive contrast meet the project's accessibility target.

Selection, hover, disabled, loading, error and validation states remain
distinguishable in light mode.

## Frontend boundaries

- Vue Router owns navigation.
- Pinia owns shared Project, Discover, Papers, Writing and workspace state.
- API modules own transport and typed response normalization.
- Components do not invent backend capabilities or parse prose into business
  objects.
- Domain/application code does not depend on Vue state.
- `PaperReader.vue` and the Tiptap editor remain protected reusable assets.

The frontend never exposes Tool, Skill, ReAct, chain-of-thought, raw provider
payloads or raw execution event logs.

## Maintenance checks

Frontend changes preserve the four-page Project boundary, design tokens,
responsive access to core actions, keyboard/focus behavior, real state
feedback, Reader navigation and Writing proposal safety.
