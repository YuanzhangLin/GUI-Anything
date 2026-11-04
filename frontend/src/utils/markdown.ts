import { marked } from 'marked'

const ALLOWED = new Set([
  'p', 'br', 'strong', 'em', 's', 'blockquote', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 'a', 'hr',
  'table', 'thead', 'tbody', 'tr', 'th', 'td'
])
const DROP_CONTENT = new Set(['script', 'style', 'iframe', 'object', 'embed', 'svg', 'math', 'form'])

export function renderMarkdown(content: string): string {
  const parsed = new DOMParser().parseFromString(String(marked.parse(content || '', { breaks: true, gfm: true })), 'text/html')
  const output = document.createElement('div')

  function appendSafe(source: Node, target: Node) {
    if (source.nodeType === Node.TEXT_NODE) {
      target.appendChild(document.createTextNode(source.textContent || ''))
      return
    }
    if (source.nodeType !== Node.ELEMENT_NODE) return
    const element = source as Element
    const tag = element.tagName.toLowerCase()
    if (DROP_CONTENT.has(tag)) return
    const destination = ALLOWED.has(tag) ? document.createElement(tag) : target
    if (tag === 'a' && destination !== target) {
      const href = element.getAttribute('href') || ''
      try {
        const url = new URL(href, window.location.href)
        if (['http:', 'https:', 'mailto:'].includes(url.protocol)) {
          const link = destination as HTMLAnchorElement
          link.href = url.href
          link.rel = 'noopener noreferrer'
        }
      } catch { /* Treat malformed links as plain text. */ }
    }
    for (const child of Array.from(element.childNodes)) appendSafe(child, destination)
    if (destination !== target) target.appendChild(destination)
  }

  for (const child of Array.from(parsed.body.childNodes)) appendSafe(child, output)
  return output.innerHTML
}
