import { describe, expect, it } from 'vitest'
import { citationNode, collectHeadings, emptyProseMirrorDocument } from './prosemirror'

describe('Writing V2 ProseMirror contracts', () => {
  it('creates a valid empty document', () => expect(emptyProseMirrorDocument()).toEqual({ type: 'doc', content: [{ type: 'paragraph', content: [] }] }))
  it('stores paper and evidence identity in citation nodes', () => expect(citationNode('p1', 'Smith, 2026', 'e1').attrs).toEqual({ paper_id: 'p1', citation_key: 'Smith, 2026', evidence_id: 'e1' }))
  it('extracts ordered headings', () => expect(collectHeadings({ type: 'doc', content: [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Method' }] }] })).toEqual([{ text: 'Method', level: 2 }]))
})
