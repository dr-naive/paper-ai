import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { describe, expect, it } from 'vitest'
import { deriveWritingContext } from './writingContext'

const createDocument = () => new Editor({
  extensions: [StarterKit],
  content: {
    type: 'doc',
    content: [
      { type: 'heading', attrs: { level: 1 }, content: [{ type: 'text', text: 'Introduction' }] },
      { type: 'paragraph', content: [{ type: 'text', text: 'Opening context.' }] },
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Methods' }] },
      { type: 'paragraph', content: [{ type: 'text', text: 'Participants completed the protocol.' }] },
      { type: 'heading', attrs: { level: 3 }, content: [{ type: 'text', text: 'Sample' }] },
      { type: 'paragraph', content: [{ type: 'text', text: 'The final sample included forty participants.' }] },
    ],
  },
})

describe('writing editor context', () => {
  it('derives the active heading hierarchy from the cursor', () => {
    const editor = createDocument()
    const initial = deriveWritingContext(editor.state.doc as unknown as Parameters<typeof deriveWritingContext>[0], 1, 1)
    const sample = initial.outline.find(item => item.text === 'Sample')!
    const snapshot = deriveWritingContext(editor.state.doc as unknown as Parameters<typeof deriveWritingContext>[0], sample.pos + 1, sample.pos + 1)

    expect(snapshot.outline.map(item => [item.text, item.level])).toEqual([
      ['Introduction', 1],
      ['Methods', 2],
      ['Sample', 3],
    ])
    expect(snapshot.currentHeading).toBe('Sample')
    expect(snapshot.sectionPath).toEqual(['Introduction', 'Methods', 'Sample'])
    editor.destroy()
  })

  it('captures selected text and bounded nearby blocks without storing the document', () => {
    const editor = createDocument()
    let textPosition = 0
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'paragraph' && node.textContent.startsWith('Participants completed')) textPosition = pos + 1
    })
    const snapshot = deriveWritingContext(
      editor.state.doc as unknown as Parameters<typeof deriveWritingContext>[0],
      textPosition,
      textPosition + 'Participants'.length,
      80,
    )

    expect(snapshot.selectedText).toBe('Participants')
    expect(snapshot.selectedCharacterCount).toBe(12)
    expect(snapshot.currentHeading).toBe('Methods')
    expect(snapshot.nearbyText).toContain('Opening context.')
    expect(snapshot.nearbyText.length).toBeLessThanOrEqual(80)
    editor.destroy()
  })
})
