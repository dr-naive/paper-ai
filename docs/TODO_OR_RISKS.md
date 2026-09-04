# Current Risks

Status: ACTIVE

This document records only risks that still exist in the current system.
Completed work and superseded findings belong in Git history or `docs/archive/`.
Implementation status belongs in
`docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`.

Each entry uses `OPEN` or `MITIGATED`; closed entries are removed.

## RISK-001 — Lead Agent responsibility concentration

Status: OPEN
Priority: P0

`backend/app/harness/agents/lead_agent.py` still coordinates the model loop,
context assembly, execution control, checkpoints and streaming.

Risk:

- new workflow-specific branches can turn the runtime into a God Object;
- prompt, retry and execution concerns can become coupled;
- isolated testing becomes harder.

Guardrail:

- keep the model tool-calling loop generic;
- keep Project Context, Discover, Writing and Citation decisions in typed
  application/workflow services;
- do not add large mode-specific branches to the runtime.

## RISK-002 — Literature tool/workflow coupling

Status: OPEN
Priority: P0

External-literature code can drift toward mixing provider HTTP behavior,
normalization, search strategy and user workflow in one large tool.

Guardrail:

```text
Academic Search Provider
→ normalization
→ bounded Discovery workflow
→ limited Agent decisions
```

Tools remain atomic and cannot combine requirement analysis, search, filtering,
import and writing in one call.

## RISK-003 — Citation verification quality

Status: MITIGATED
Priority: P0

The system performs referential integrity, lexical/retrieval checks and semantic
support verification. Residual model-quality risks remain for causal claims,
claim strength and evidence that is related but not actually supportive.

Guardrail:

- keep `verified`, `weak` and `unsupported` structured;
- fail closed on timeout, invalid output, authentication failure or rate limit;
- sample complex claims and never treat lexical overlap as semantic support.

## RISK-004 — Context expansion

Status: MITIGATED
Priority: P0

New use cases may bypass staged context narrowing and regress toward a single
large prompt containing all Project papers, memory, chats and writing content.

Guardrail:

- preserve Project Profile, Literature Memory, Paper Profile, Evidence and
  Writing Context as separate concepts;
- select bounded candidate papers before full-text retrieval;
- do not promote ordinary chat history to long-term memory by default.

## RISK-005 — Writing regressions

Status: MITIGATED
Priority: P0

Writing changes can break revision, undo, Citation Nodes, export or existing
document data.

Guardrail:

- reuse the existing Tiptap and WritingDocument foundations;
- keep proposals separate from document mutations;
- require explicit Replace or Copy;
- run revision, citation and export regression checks when affected.

## RISK-006 — Reader and retrieval regressions

Status: MITIGATED
Priority: P0

Project integration can accidentally duplicate or alter the established Reader,
PDF location or Hybrid Retrieval behavior.

Guardrail:

- keep `PaperReader.vue` protected;
- reuse the existing parsing, bbox, vector and retrieval foundations;
- do not create a second reader, RAG stack or vector store.

## RISK-007 — Search/import boundary expansion

Status: MITIGATED
Priority: P0

Search results may contain arbitrary links, but those links are not trusted PDF
sources. Adding providers can accidentally weaken SSRF, file or publisher-access
protections.

Guardrail:

- keep Search Provider and Remote Import Provider separate;
- preserve source allowlists, identifier validation, size limits, PDF magic
  bytes and temporary-file cleanup;
- disable Download and Import when no approved full-text source exists.

## RISK-008 — Optional proxy environment

Status: OPEN
Priority: P1

Container egress through a host proxy still depends on the proxy listener being
reachable outside host loopback. Direct egress is the accepted default path;
proxy validation is required only when that optional configuration is enabled.

## Lower-priority maintenance

- old artifact enum cleanup;
- dead non-V1 Research Map or Experiment code cleanup;
- legacy CSS cleanup;
- non-core UX optimization.
