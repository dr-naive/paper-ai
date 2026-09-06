import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { EvidenceItem } from '@/api/projects'
import type { WritingRewriteProposal } from '@/api/documents'
import WritingProposalCard from './WritingProposalCard.vue'

const citation = {
  citation_key: 'Paper A, 2025',
  paper_id: 'paper-a',
  evidence_id: 'evidence-a',
  status: 'verified' as const,
  code: 'semantic_verified',
  reason: '直接支持该主张。',
  confidence: 0.94,
  claim_text: 'The method improves retrieval quality.',
  original_claim: 'The method improves retrieval quality.',
  adjusted_claim: null,
  adjustment_applied: false,
  evidence_snippet: 'The method improves retrieval quality in the evaluation.',
}
const proposal: WritingRewriteProposal = {
  proposal_id: 'proposal-1',
  project_id: 'project-1',
  document_id: 'document-1',
  base_revision_id: 'revision-1',
  kind: 'rewrite',
  status: 'ready',
  content: 'The method improves retrieval quality [[CITATION:Paper A, 2025]].',
  original_content: 'The method improves retrieval quality [[CITATION:Paper A, 2025]].',
  citations: [citation],
  warnings: [],
  selection: { from: 4, to: 20 },
  section_path: ['Methods'],
}
const evidence: EvidenceItem[] = [{
  id: 'evidence-a', project_id: 'project-1', paper_id: 'paper-a', evidence_type: 'result',
  snippet: 'The method improves retrieval quality in the evaluation.', normalized_claim: 'The method improves retrieval quality.',
  source_title: 'Paper A', source_authors: ['Ada Lin'], source_year: 2025, page_number: 4,
}]

describe('WritingProposalCard', () => {
  it('renders structured citation status and opens Evidence detail', async () => {
    const wrapper = mount(WritingProposalCard, { props: { proposal, evidence, replaceDisabled: false, replaceDisabledReason: '', projectId: 'project-1' } })
    expect(wrapper.text()).toContain('引用已验证')
    expect(wrapper.text()).toContain('Paper A')
    await wrapper.get('.citation-token').trigger('click')
    expect(wrapper.text()).toContain('The method improves retrieval quality in the evaluation.')
    expect(wrapper.text()).toContain('规范化主张：The method improves retrieval quality.')
    expect(wrapper.text()).toContain('第 4 页')
    expect(wrapper.get('.proposal-primary').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('a').attributes('href')).toBe('/projects/project-1/papers/paper-a/read')
    await wrapper.get('.proposal-primary').trigger('click')
    expect(wrapper.emitted('replace')).toHaveLength(1)
  })

  it('keeps replacement disabled with an explicit stale-selection reason', () => {
    const wrapper = mount(WritingProposalCard, { props: { proposal, evidence, replaceDisabled: true, replaceDisabledReason: '正文或选区已发生变化，请重新选择后再次生成建议。', projectId: 'project-1' } })
    const button = wrapper.get('.proposal-primary')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('title')).toContain('重新选择')
  })

  it('does not present weak or unsupported citations as verified', () => {
    const weak = { ...citation, status: 'weak' as const, reason: '只能支持相关性。' }
    const unsupported = { ...citation, status: 'unsupported' as const, reason: '证据不支持该主张。' }
    const partiallyVerified = mount(WritingProposalCard, { props: { proposal: { ...proposal, status: 'partially_verified', citations: [weak] }, evidence, replaceDisabled: false, replaceDisabledReason: '', projectId: 'project-1' } })
    expect(partiallyVerified.text()).toContain('部分引用证据较弱')
    expect(partiallyVerified.text()).toContain('证据较弱')
    expect(partiallyVerified.text()).not.toContain('引用已验证')
    const verificationFailed = mount(WritingProposalCard, { props: { proposal: { ...proposal, status: 'verification_failed', citations: [unsupported] }, evidence, replaceDisabled: false, replaceDisabledReason: '', projectId: 'project-1' } })
    expect(verificationFailed.text()).toContain('存在未支持引用')
    expect(verificationFailed.text()).toContain('不支持')
  })
})
