// Same estimates as server/engine/text.py, so the editor footer matches the server.

// Characters of speech per second at speed 1.0, measured with Kokoro-82M.
const CHARS_PER_SECOND: Record<string, number> = {
  a: 14,
  b: 14,
  h: 12,
  f: 22,
  e: 18,
  i: 18,
  p: 18,
}

export function estimateSeconds(text: string, lang = 'a', speed = 1): number {
  if (!text.trim()) return 0
  return text.length / ((CHARS_PER_SECOND[lang] ?? 15) * Math.max(0.1, speed))
}

export function countWords(text: string): number {
  const trimmed = text.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

/** 0:07, 1:26, 1:02:03 */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const ss = String(s).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** "~1m 26s" style for estimates */
export function formatEstimate(seconds: number): string {
  const total = Math.round(seconds)
  if (total < 60) return `~${total}s`
  const m = Math.floor(total / 60)
  const s = total % 60
  return s ? `~${m}m ${s}s` : `~${m}m`
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

/** 1200 → "1.2k" */
export function formatShort(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k` : String(n)
}
