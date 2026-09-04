export interface WritingOutlineItem {
  text: string
  level: number
  pos: number
}

export interface WritingContextSnapshot {
  outline: WritingOutlineItem[]
  currentHeading: string
  sectionPath: string[]
  selectionFrom: number
  selectionTo: number
  selectedText: string
  selectedCharacterCount: number
  nearbyText: string
}

interface DocumentNode {
  textContent: string
  nodeSize: number
  type: { name: string }
  attrs: Record<string, unknown>
  descendants: (callback: (node: DocumentNode, pos: number) => void) => void
  forEach: (callback: (node: DocumentNode, offset: number) => void) => void
  textBetween: (from: number, to: number, blockSeparator?: string) => string
}

export const deriveWritingContext = (
  doc: DocumentNode,
  selectionFrom: number,
  selectionTo: number,
  nearbyLimit = 12_000,
): WritingContextSnapshot => {
  const outline: WritingOutlineItem[] = []
  const sectionPath: string[] = []

  doc.descendants((node, pos) => {
    if (node.type.name !== 'heading') return
    const level = Math.max(1, Number(node.attrs.level) || 1)
    const text = node.textContent.trim() || '未命名标题'
    outline.push({ text, level, pos })
    if (pos >= selectionFrom) return
    sectionPath.splice(level - 1)
    sectionPath[level - 1] = text
  })

  const selectedText = selectionFrom === selectionTo
    ? ''
    : doc.textBetween(selectionFrom, selectionTo, ' ').trim()
  const blocks: Array<{ text: string; from: number; to: number }> = []
  doc.forEach((node, offset) => {
    const text = node.textContent.trim()
    if (text) blocks.push({ text, from: offset, to: offset + node.nodeSize })
  })
  const cursorIndex = Math.max(0, blocks.findIndex(block => selectionFrom >= block.from && selectionFrom <= block.to))
  const nearbyText = blocks
    .slice(Math.max(0, cursorIndex - 3), Math.min(blocks.length, cursorIndex + 2))
    .map(block => block.text)
    .join('\n\n')
    .slice(0, nearbyLimit)

  const cleanPath = sectionPath.filter(Boolean)
  return {
    outline,
    currentHeading: cleanPath.at(-1) || '正文开头',
    sectionPath: cleanPath,
    selectionFrom,
    selectionTo,
    selectedText,
    selectedCharacterCount: Array.from(selectedText).length,
    nearbyText,
  }
}
