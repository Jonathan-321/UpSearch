import { useState, useCallback, useRef } from 'react'
import { API_BASE } from '../types'
import type { LogEntry, LogLevel } from '../types'

const OS_BASE = API_BASE.replace('/api', '/os')

export type OSStageKey =
  | 'profile' | 'company' | 'problem' | 'people'
  | 'technical_note' | 'outreach' | 'qa' | 'done'

export type StageStatus = 'waiting' | 'running' | 'complete' | 'error'

export interface OSStage {
  key: OSStageKey
  label: string
  description: string
  status: StageStatus
  message: string
  data?: unknown
}

export interface OSCompany {
  id: number
  name: string
  lane: string
  fit_score: number
  status: string
  hiring_status: string
}

export interface OSPerson {
  id: number
  name: string
  role: string
  proximity: string
  linkedin_url?: string
  github_url?: string
  relevance_score: number
  relevance_reason: string
}

export interface OSProblem {
  id: number
  title: string
  description: string
  relevance_score: number
  source_urls: string
}

export interface OSPacket {
  company_fit: string
  adjacent_proof: string
  technical_note: string
  outreach_drafts: string
  qa_score: number
  qa_flags: string
  crm_status: string
}

export interface OSMessage {
  id: number
  variant: string
  content: string
  word_count: number
  status: string
  person_name?: string
}

const STAGES: Omit<OSStage, 'status' | 'message' | 'data'>[] = [
  { key: 'profile',       label: 'Profile',        description: 'Parses your background and proof points' },
  { key: 'company',       label: 'Company',         description: 'Researches fit, tech stack, hiring signal' },
  { key: 'problem',       label: 'Problem',         description: 'Extracts open technical problems' },
  { key: 'people',        label: 'People',          description: 'Maps relevant people by proximity' },
  { key: 'technical_note',label: 'Technical Note',  description: 'Writes one-page problem brief' },
  { key: 'outreach',      label: 'Outreach',        description: 'Drafts email, LinkedIn note, follow-up' },
  { key: 'qa',            label: 'QA',              description: 'Checks claims, sources, word count, tone' },
]

const initialStages = (): OSStage[] =>
  STAGES.map(s => ({ ...s, status: 'waiting', message: '' }))

async function apiFetch<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch(`${OS_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `API ${res.status}`)
  }
  return res.json()
}

function nowTs(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function useOS() {
  const [running, setRunning] = useState(false)
  const [stages, setStages] = useState<OSStage[]>(initialStages())
  const [companies, setCompanies] = useState<OSCompany[]>([])
  const [currentCompany, setCurrentCompany] = useState('')
  const [currentPacket, setCurrentPacket] = useState<{
    packet: OSPacket | null
    problems: OSProblem[]
    people: OSPerson[]
  } | null>(null)
  const [pendingMessages, setPendingMessages] = useState<OSMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const esRef = useRef<EventSource | null>(null)

  const updateStage = useCallback((key: OSStageKey, update: Partial<OSStage>) => {
    setStages(prev => prev.map(s => s.key === key ? { ...s, ...update } : s))
  }, [])

  const buildPacket = useCallback((company: string, lane: string) => {
    if (esRef.current) esRef.current.close()
    setRunning(true)
    setError(null)
    setCurrentCompany(company)
    setStages(initialStages())
    setCurrentPacket(null)
    setLogEntries([])

    const es = new EventSource(`${OS_BASE}/packet/stream/${encodeURIComponent(company)}?lane=${lane}`)
    esRef.current = es

    es.addEventListener('stage', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { stage: OSStageKey; status: StageStatus; message: string; data?: unknown }
      updateStage(d.stage, { status: d.status, message: d.message, data: d.data })
    })

    es.addEventListener('log', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { agent: string; level: string; message: string; elapsed?: string }
      setLogEntries(prev => [
        ...prev.slice(-99),
        { ts: nowTs(), agent: d.agent, level: d.level as LogLevel, message: d.message, elapsed: d.elapsed },
      ])
    })

    es.addEventListener('complete', (e: MessageEvent) => {
      const d = JSON.parse(e.data)
      updateStage('qa', { status: 'complete' })
      setStages(prev => prev.map(s => ({ ...s, status: s.status === 'waiting' ? 'complete' : s.status })))
      setRunning(false)
      es.close()
      // Refresh CRM and packet after completion
      fetchCompanies()
      fetchPacket(d.company)
      fetchPending()
    })

    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const d = JSON.parse((e as MessageEvent).data)
        setError(d.error)
      } catch {
        setError('Pipeline error — check the server.')
      }
      setRunning(false)
      es.close()
    })

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return
      setError('Connection to server lost. Is uvicorn running on port 8000?')
      setRunning(false)
      es.close()
    }
  }, [updateStage])

  const fetchCompanies = useCallback(async () => {
    try {
      const data = await apiFetch<{ companies: OSCompany[] }>('/companies')
      setCompanies(data.companies)
    } catch { /* silent */ }
  }, [])

  const fetchPacket = useCallback(async (company: string) => {
    try {
      const data = await apiFetch<{ packet: OSPacket; problems: OSProblem[]; people: OSPerson[] }>(
        `/packet/${encodeURIComponent(company)}`
      )
      setCurrentPacket(data)
    } catch { /* silent */ }
  }, [])

  const fetchPending = useCallback(async () => {
    try {
      const data = await apiFetch<{ messages: OSMessage[] }>('/messages/pending')
      setPendingMessages(data.messages)
    } catch { /* silent */ }
  }, [])

  const approveMessage = useCallback(async (id: number) => {
    await apiFetch(`/messages/${id}/approve`, 'POST')
    setPendingMessages(prev => prev.filter(m => m.id !== id))
  }, [])

  const selectCompany = useCallback((company: string) => {
    setCurrentCompany(company)
    fetchPacket(company)
  }, [fetchPacket])

  return {
    running, stages, companies, currentCompany, currentPacket,
    pendingMessages, error, logEntries,
    buildPacket, fetchCompanies, fetchPacket, fetchPending,
    approveMessage, selectCompany,
  }
}
