import { describe, expect, it } from 'vitest'
import type { CitationVerificationResult } from '@/api/documents'
import { proposalInlineContent, proposalPlainText, proposalSegments, selectionAnchorIsCurrent } from './writingProposal'

const citation: CitationVerificationResult = {
  citation_key: 'Paper A, 2025',
  paper_id: 'paper-a',
  evidence_id: 'evidence-a',
  status: 'verified',
  code: 'semantic_verified',
  reason: 'Direct support.',
  confidence: 0.94,
  claim_text: 'The method improves retrieval quality.',
  original_claim: 'The method improves retrieval quality.',
  adjusted_claim: null,
  adjustment_applied: false,
  evidence_snippet: 'The method improves retrieval quality.',
}

describe('writing proposal helpers', () => {
  it('turns structured placeholders into readable segments and copy text', () => {
    const content = `The method improves retrieval quality [[CITATION:${citation.citation_key}]].`
    const segments = proposalSegments(content, [citation])
    expect(segments.map(item => item.type)).toEqual(['text', 'citation', 'text'])
    expect(segments[1].citation?.evidence_id).toBe('evidence-a')
    expect(proposalPlainText(content)).toBe('The method improves retrieval quality [Paper A, 2025].')
  })

  it('creates Citation Nodes for replacement instead of flattening identity into text', () => {
    const content = `Claim [[CITATION:${citation.citation_key}]].`
    expect(proposalInlineContent(content, [citation])).toEqual([
      { type: 'text', text: 'Claim ' },
      { type: 'citation', attrs: { paper_id: 'paper-a', evidence_id: 'evidence-a', citation_key: 'Paper A, 2025' } },
      { type: 'text', text: '.' },
    ])
  })

  it('rejects replacement when any selection anchor changed', () => {
    const expected = { revisionId: 'r1', from: 4, to: 18, selectedText: 'original' }
    expect(selectionAnchorIsCurrent(expected, expected)).toBe(true)
    expect(selectionAnchorIsCurrent(expected, { ...expected, to: 19 })).toBe(false)
    expect(selectionAnchorIsCurrent(expected, { ...expected, revisionId: 'r2' })).toBe(false)
    expect(selectionAnchorIsCurrent(expected, { ...expected, selectedText: 'changed' })).toBe(false)
  })
})
