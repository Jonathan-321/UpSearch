export const API_BASE = 'http://localhost:8000/api';

/**
 * Honest link text for an evidence URL: host plus a truncated path/query,
 * e.g. "baseten.co/author/bola-malek". Falls back to the raw value when the
 * URL cannot be parsed. The full URL belongs in href/title, never in the text.
 */
export function evidenceLabel(url: string, maxTail = 32): string {
  try {
    const parsed = new URL(url)
    const host = parsed.hostname.replace(/^www\./, '')
    let tail = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/$/, '')
    if (parsed.search) tail += parsed.search
    if (tail.length > maxTail) tail = `${tail.slice(0, maxTail - 1)}…`
    return `${host}${tail}`
  } catch {
    return url
  }
}

export type LogLevel = 'STARTED' | 'SOURCE' | 'INFO' | 'COMPLETE' | 'WARN' | 'ERROR'

export interface LogEntry {
  ts: string
  agent: string
  level: LogLevel
  message: string
  elapsed?: string
}
