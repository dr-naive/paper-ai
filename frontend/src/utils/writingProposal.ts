import type { CitationVerificationResult } from '@/api/documents'

export interface ProposalTextSegment {
  type: 'text' | 'citation'
  text: string
  citation?: CitationVerificationResult
}

export interface SelectionAnchor {
  revisionId: string
  from: number
  to: number
  selectedText: string
}

export const citationPlaceholder = (citationKey: string) => `[[CITATION:${citationKey}]]`

export const proposalSegments = (
  content: string,
  citations: CitationVerificationResult[] = [],
): ProposalTextSegment[] => {
  const byKey = new Map(citations.map(citation => [citation.citation_key, citation]))
  const segments: ProposalTextSegment[] = []
  const pattern = /\[\[CITATION:([^\]]+)\]\]/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(content))) {
    if (match.index > cursor) segments.push({ type: 'text', text: content.slice(cursor, match.index) })
    const key = match[1]
    segments.push({ type: 'citation', text: key, citation: byKey.get(key) })
    cursor = match.index + match[0].length
  }
  if (cursor < content.length) segments.push({ type: 'text', text: content.slice(cursor) })
  return segments.length ? segments : [{ type: 'text', text: content }]
}

export const proposalPlainText = (content: string, citationLabel = (key: string) => `[${key}]`) => content.replace(/\[\[CITATION:([^\]]+)\]\]/g, (_match, key: string) => citationLabel(key))

export const copyTextToClipboard = async (text: string) => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  if (typeof document === 'undefined' || !document.body) throw new Error('clipboard_unavailable')
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = typeof document.execCommand === 'function' && document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('clipboard_unavailable')
}

export const proposalInlineContent = (
  content: string,
  citations: CitationVerificationResult[] = [],
): Array<Record<string, unknown>> => proposalSegments(content, citations).map(segment => {
  if (segment.type === 'text') return { type: 'text', text: segment.text }
  const citation = segment.citation
  return {
    type: 'citation',
    attrs: {
      paper_id: citation?.paper_id || null,
      evidence_id: citation?.evidence_id || null,
      citation_key: citation?.citation_key || segment.text,
    },
  }
})

export const selectionAnchorIsCurrent = (expected: SelectionAnchor, current: SelectionAnchor) => (
  expected.revisionId === current.revisionId
  && expected.from === current.from
  && expected.to === current.to
  && expected.selectedText === current.selectedText
)
