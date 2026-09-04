export type ProseMirrorNode = { type: string; attrs?: Record<string, unknown>; content?: ProseMirrorNode[]; text?: string }

export const emptyProseMirrorDocument = (): ProseMirrorNode => ({
  type: 'doc', content: [{ type: 'paragraph', content: [] }],
})

export const citationNode = (paperId: string, citationKey: string, evidenceId?: string): ProseMirrorNode => ({
  type: 'citation', attrs: { paper_id: paperId, citation_key: citationKey, evidence_id: evidenceId || null },
})

export const collectHeadings = (document: ProseMirrorNode): Array<{ text: string; level: number }> => {
  const result: Array<{ text: string; level: number }> = []
  const visit = (node: ProseMirrorNode) => {
    if (node.type === 'heading') result.push({ text: (node.content || []).map(child => child.text || '').join(''), level: Number(node.attrs?.level || 1) })
    node.content?.forEach(visit)
  }
  visit(document)
  return result
}
