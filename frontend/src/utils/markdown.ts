import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false
})

const defaultLinkOpen = markdown.renderer.rules.link_open
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen
    ? defaultLinkOpen(tokens, index, options, env, self)
    : self.renderToken(tokens, index, options)
}

const linkArxivTitles = (source: string): string => source
  .replace(
    /\*\*([^*\n]+)\*\*\s*[（(](?:arXiv\s*:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)[）)]/gi,
    '[**$1**](https://arxiv.org/abs/$2) ([arXiv:$2](https://arxiv.org/abs/$2))',
  )
  .replace(
    /《([^》\n]+)》\s*[（(](?:arXiv\s*:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)[）)]/gi,
    '[《$1》](https://arxiv.org/abs/$2) ([arXiv:$2](https://arxiv.org/abs/$2))',
  )

markdown.core.ruler.after('inline', 'arxiv-links', (state) => {
  const pattern = /\b(?:arXiv\s*:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)\b/gi
  for (const block of state.tokens) {
    if (block.type !== 'inline' || !block.children) continue
    const children = []
    let linkDepth = 0
    for (const child of block.children) {
      if (child.type === 'link_open') linkDepth += 1
      if (child.type !== 'text' || linkDepth > 0) {
        children.push(child)
      } else {
        let cursor = 0
        for (const match of child.content.matchAll(pattern)) {
          const index = match.index || 0
          if (index > cursor) {
            const text = new state.Token('text', '', 0)
            text.content = child.content.slice(cursor, index)
            children.push(text)
          }
          const id = match[1]
          const open = new state.Token('link_open', 'a', 1)
          open.attrSet('href', `https://arxiv.org/abs/${id}`)
          const label = new state.Token('text', '', 0)
          label.content = `arXiv:${id}`
          children.push(open, label, new state.Token('link_close', 'a', -1))
          cursor = index + match[0].length
        }
        if (cursor < child.content.length) {
          const text = new state.Token('text', '', 0)
          text.content = child.content.slice(cursor)
          children.push(text)
        }
      }
      if (child.type === 'link_close') linkDepth = Math.max(0, linkDepth - 1)
    }
    block.children = children
  }
})

export const renderMarkdown = (value: unknown): string => {
  const source = String(value || '').trim()
  if (!source) return ''
  return DOMPurify.sanitize(markdown.render(linkArxivTitles(source)), {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target', 'rel'],
  })
}
