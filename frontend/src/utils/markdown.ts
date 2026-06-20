import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false
})

export const renderMarkdown = (value: unknown): string => {
  const source = String(value || '').trim()
  if (!source) return ''
  return DOMPurify.sanitize(markdown.render(source), {
    USE_PROFILES: { html: true }
  })
}
