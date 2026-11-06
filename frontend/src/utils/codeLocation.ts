export const CODE_LOCATION_EVENT = 'gui-anything:open-code-location'

export type CodeLocation = {
  appId: string
  path: string
  startLine?: number
  endLine?: number
  fileSha256?: string
  origin?: 'map' | 'run' | 'conversation'
}

export function openCodeLocation(location: CodeLocation) {
  window.dispatchEvent(new CustomEvent<CodeLocation>(CODE_LOCATION_EVENT, { detail: location }))
}

const SOURCE_REFERENCE = /(?:^|[\s`(（【\[])([A-Za-z0-9_@+.,()\-/\\]+\.(?:java|kt|kts|xml|gradle|groovy|properties|json|ya?ml|ts|tsx|js|jsx|vue|py|go|rs|c|cc|cpp|h|hpp)):(\d+)(?:\s*[-–—]\s*(\d+))?/gim

export function extractCodeLocations(content: string, appId: string): CodeLocation[] {
  const result: CodeLocation[] = []
  const seen = new Set<string>()
  for (const match of content.matchAll(SOURCE_REFERENCE)) {
    const path = match[1].replace(/\\/g, '/')
    const startLine = Number(match[2])
    const endLine = Number(match[3] || match[2])
    const key = `${path}:${startLine}:${endLine}`
    if (seen.has(key)) continue
    seen.add(key)
    result.push({ appId, path, startLine, endLine, origin: 'conversation' })
  }
  return result
}
