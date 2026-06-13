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
  hiring_status: string | null
  identity_status?: string
  identity_confidence?: number
  identity_reason?: string
}

export interface OSPerson {
  id: number
  name: string
  role: string
  proximity: string
  linkedin_url?: string
  github_url?: string
  twitter_url?: string
  source_url?: string
  relevance_score: number
  relevance_reason: string
  /** "verified" | "unverified" from the people table; absent on legacy rows. */
  verification_status?: string | null
  /** Not yet emitted by the backend; rendered when present. */
  verification_reason?: string | null
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

export interface OSTraceEvent {
  event_type: 'agent_step' | 'handoff' | 'gate' | 'block' | 'error'
  status: string
  timestamp: string
  agent?: string
  agent_role?: string
  role?: string
  reads?: string[]
  writes?: string[]
  output_summary?: string
  latency_ms?: number
  from_agent?: string
  to_agent?: string
  payload_keys?: string[]
  reason?: string
  payload?: Record<string, unknown>
}

export interface OSCheckupMetric {
  name: string
  score: number
  detail: string
}

export interface OSSourceMethod {
  title: string
  steps: string[]
  current_tools: string[]
  planned_tools: string[]
}

export interface OSCheckup {
  company: string
  status: string
  overall_score: number
  failure_category: string
  trace_status?: 'unavailable' | 'incomplete' | 'complete'
  suggested_fix: string
  metrics: OSCheckupMetric[]
  trace: {
    events: OSTraceEvent[]
    agent_steps: number
    handoffs: number
    missing_agents: string[]
  }
  source_methods: Record<string, OSSourceMethod>
  facts?: {
    problem_source_urls?: string[]
    qa_flags?: string[]
    over_200_drafts?: string[]
    note_words?: number
  }
  artifact_paths?: {
    json?: string
    report?: string
  }
}

export interface OSRunRecord {
  run_id: string
  company_name: string
  lane: string
  status: 'running' | 'complete' | 'failed' | 'cancelled'
  started_at?: string | null
  completed_at?: string | null
  current_step?: string | null
  steps_completed: string[]
  qa_score?: number | null
  final_status?: string | null
  error_message?: string | null
}

export interface OSQAModelRoute {
  provider?: string | null
  model?: string | null
  configured?: boolean
  is_fallback?: boolean
  degraded_mode?: boolean
  reason?: string | null
}

export interface OSQAResult {
  score: number
  passed: boolean
  flags: string[]
  reasoning?: string | null
  model_route?: OSQAModelRoute | null
}

export interface OSModelStatus {
  ok: boolean
  agent_provider?: string | null
  agent_model?: string | null
  strong_model_provider?: string | null
  strong_model?: string | null
  problems: string[]
}

export interface OSHandoffReadiness {
  message_id: number
  actionable: boolean
  safety_reasons: string[]
  platform?: string | null
  platform_label?: string | null
  platform_url?: string | null
  handoff_mode?: string | null
  approval_contract?: string | null
}

export interface OSPacketPayload {
  company?: OSCompany
  packet: OSPacket | null
  problems: OSProblem[]
  people: OSPerson[]
  checkup?: OSCheckup | null
  run?: OSRunRecord | null
  trace_status: 'unavailable' | 'incomplete' | 'complete'
  trace: OSTraceEvent[]
  qa?: OSQAResult | null
  approval_state: 'unavailable' | 'required' | 'partially_approved' | 'approved'
  handoff_readiness: OSHandoffReadiness[]
}

export interface OSMessage {
  id: number
  packet_id?: number
  company_name?: string
  variant: string
  content: string
  word_count: number
  status: string
  person_name?: string
  person_role?: string
  linkedin_url?: string
  github_url?: string
  twitter_url?: string
  source_url?: string
  problem_title?: string
  problem_source_urls?: string[]
  qa_score?: number
  qa_flags?: string[]
  crm_status?: string
  channel?: string
  platform?: string
  platform_label?: string
  platform_url?: string
  handoff_mode?: 'prefill_compose' | 'copy_then_open' | 'open_only'
  approval_contract?: string
  actionable?: boolean
  review_actionable?: boolean
  safety_reasons?: string[]
  checkup?: OSCheckup
  failure_category?: string
  checkup_score?: number
  approval_id?: number
  approved_at?: string
  approval_current?: boolean
  state_stale?: boolean
  body_digest?: string
  delivery_status?: 'prepared' | 'opened' | 'sent' | 'delivered' | 'failed' | 'unknown'
  delivery_error?: string
  delivery_updated_at?: string
  safe_retry?: boolean
  follow_up_id?: number
  follow_up_status?: 'pending' | 'completed' | 'skipped'
  follow_up_due_date?: string
  follow_up_notes?: string
}

export interface OSUserProfile {
  id?: number
  name?: string
  email?: string
  school?: string
  background_summary?: string
  raw_profile?: string
  updated_at?: string
}

export interface OSProfileSource {
  kind: string
  value: string
  status: string
  discovered_from?: string
}

export interface OSProfileHarness {
  route_provider: string
  route_model: string
  route_reason: string
  sources: OSProfileSource[]
  profile_name?: string
  school?: string
  email?: string
  background_summary?: string
  proof_bank: string[]
  target_lanes: string[]
  constraints: string[]
  claim_boundaries: string[]
  missing_inputs: string[]
  fetched_at?: string | null
  source_warnings?: string[]
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

export async function fetchModelStatus(): Promise<OSModelStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/config/model-status`, {
      signal: AbortSignal.timeout(30_000),
    })
    if (!res.ok) return null
    return await res.json() as OSModelStatus
  } catch {
    return null
  }
}

function nowTs(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function useOS() {
  const [running, setRunning] = useState(false)
  const [stages, setStages] = useState<OSStage[]>(initialStages())
  const [companies, setCompanies] = useState<OSCompany[]>([])
  const [currentCompany, setCurrentCompany] = useState('')
  const [currentPacket, setCurrentPacket] = useState<OSPacketPayload | null>(null)
  const [currentRun, setCurrentRun] = useState<OSRunRecord | null>(null)
  const [traceEvents, setTraceEvents] = useState<OSTraceEvent[]>([])
  const [traceStatus, setTraceStatus] = useState<'unavailable' | 'incomplete' | 'complete'>('unavailable')
  const [pendingMessages, setPendingMessages] = useState<OSMessage[]>([])
  const [profileText, setProfileText] = useState('')
  const [profile, setProfile] = useState<OSUserProfile | null>(null)
  const [profileHarness, setProfileHarness] = useState<OSProfileHarness | null>(null)
  const [profileFetching, setProfileFetching] = useState(false)
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
    setCurrentRun(null)
    setTraceEvents([])
    setTraceStatus('incomplete')
    setLogEntries([])

    const es = new EventSource(`${OS_BASE}/packet/stream/${encodeURIComponent(company)}?lane=${lane}`)
    esRef.current = es

    es.addEventListener('stage', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as {
        run_id?: string
        stage: OSStageKey
        status: StageStatus
        message: string
        data?: unknown
      }
      updateStage(d.stage, { status: d.status, message: d.message, data: d.data })
      if (d.run_id) {
        setCurrentRun(prev => ({
          ...(prev ?? {}),
          run_id: d.run_id as string,
          company_name: company,
          lane,
          status: 'running',
          steps_completed: prev?.steps_completed ?? [],
          current_step: d.stage,
        }))
      }
    })

    es.addEventListener('progress', (e: MessageEvent) => {
      const event = JSON.parse(e.data) as OSTraceEvent
      setTraceEvents(prev => [...prev, event])
      setTraceStatus('incomplete')
    })

    es.addEventListener('keepalive', () => {
      setLogEntries(prev => [
        ...prev.slice(-99),
        { ts: nowTs(), agent: 'Runtime', level: 'INFO', message: 'Connection healthy. Agent work is still running.' },
      ])
    })

    es.addEventListener('log', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { agent: string; level: string; message: string; elapsed?: string }
      setLogEntries(prev => [
        ...prev.slice(-99),
        { ts: nowTs(), agent: d.agent, level: d.level as LogLevel, message: d.message, elapsed: d.elapsed },
      ])
    })

    es.addEventListener('gate', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { action: string; stage?: OSStageKey; reason: string; retry_count?: number }
      setLogEntries(prev => [
        ...prev.slice(-99),
        {
          ts: nowTs(),
          agent: 'Checkup',
          level: d.action === 'pass' ? 'COMPLETE' : d.action === 'retry' ? 'WARN' : 'ERROR',
          message: d.retry_count ? `${d.reason} Retry ${d.retry_count}.` : d.reason,
        },
      ])
      if (d.stage) {
        updateStage(d.stage, { message: d.reason })
      }
    })

    es.addEventListener('block', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { stage?: OSStageKey; reason: string }
      setError(`Review required: ${d.reason}`)
      setRunning(false)
      setTraceStatus('incomplete')
      setLogEntries(prev => [
        ...prev.slice(-99),
        { ts: nowTs(), agent: 'Checkup', level: 'ERROR', message: d.reason },
      ])
      if (d.stage) {
        updateStage(d.stage, { status: 'error', message: d.reason })
      }
      es.close()
      fetchCompanies()
      fetchPacket(company)
    })

    es.addEventListener('complete', (e: MessageEvent) => {
      const d = JSON.parse(e.data) as { company: string; blocked?: boolean; reason?: string }
      const completedCompany = d.company || company
      if (d.blocked) {
        const reason = d.reason || 'Packet needs review before action.'
        setError(`Review required: ${reason}`)
        updateStage('qa', { status: 'error', message: reason })
      } else {
        updateStage('qa', { status: 'complete' })
        setStages(prev => prev.map(s => ({ ...s, status: s.status === 'waiting' ? 'complete' : s.status })))
      }
      setRunning(false)
      setTraceStatus(d.blocked ? 'incomplete' : 'complete')
      es.close()
      // Refresh CRM and packet after completion
      fetchCompanies()
      fetchPacket(completedCompany)
      fetchPending()
    })

    es.addEventListener('checkup', (e: MessageEvent) => {
      const checkup = JSON.parse(e.data) as OSCheckup
      setLogEntries(prev => [
        ...prev.slice(-99),
        {
          ts: nowTs(),
          agent: 'Checkup',
          level: checkup.status === 'passed' ? 'COMPLETE' : 'WARN',
          message: `${checkup.overall_score}/10 · ${checkup.failure_category}`,
        },
      ])
    })

    es.addEventListener('error', (e: MessageEvent) => {
      if (!e.data) return
      try {
        const d = JSON.parse(e.data)
        setError(d.error)
      } catch {
        setError('Pipeline error — check the server.')
      }
      setRunning(false)
      es.close()
    })

    es.onerror = () => {
      if (es.readyState !== EventSource.CLOSED) return
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
      const data = await apiFetch<OSPacketPayload>(
        `/packet/${encodeURIComponent(company)}`
      )
      setCurrentPacket(data)
      setCurrentRun(data.run ?? null)
      setTraceEvents(data.trace ?? [])
      setTraceStatus(data.trace_status ?? 'unavailable')
    } catch { /* silent */ }
  }, [])

  const fetchPending = useCallback(async () => {
    try {
      const data = await apiFetch<OSMessage[]>('/messages/review')
      setPendingMessages(data)
    } catch { /* silent */ }
  }, [])

  const fetchProfile = useCallback(async () => {
    try {
      const data = await apiFetch<{ content: string; profile: OSUserProfile | null; harness: OSProfileHarness | null }>('/profile')
      setProfileText(data.content ?? '')
      setProfile(data.profile ?? null)
      setProfileHarness(data.harness ?? null)
    } catch { /* silent */ }
  }, [])

  const saveProfile = useCallback(async (content: string) => {
    const data = await apiFetch<{ content: string; profile: OSUserProfile | null; harness: OSProfileHarness | null }>('/profile', 'POST', { content })
    setProfileText(data.content ?? content)
    setProfile(data.profile ?? null)
    setProfileHarness(data.harness ?? null)
  }, [])

  const fetchProfileSources = useCallback(async () => {
    setProfileFetching(true)
    try {
      const data = await apiFetch<{ content: string; profile: OSUserProfile | null; harness: OSProfileHarness | null }>(
        '/profile/fetch-sources',
        'POST',
      )
      setProfileText(data.content ?? '')
      setProfile(data.profile ?? null)
      setProfileHarness(data.harness ?? null)
    } finally {
      setProfileFetching(false)
    }
  }, [])

  const approveMessage = useCallback(async (id: number) => {
    await apiFetch(`/messages/${id}/approve`, 'POST')
    await fetchPending()
  }, [fetchPending])

  const rejectMessage = useCallback(async (id: number, notes?: string) => {
    await apiFetch(`/messages/${id}/reject?notes=${encodeURIComponent(notes || 'Rejected in review')}`, 'POST')
    setPendingMessages(prev => prev.filter(m => m.id !== id))
  }, [])

  const recordDelivery = useCallback(async (
    id: number,
    status: 'opened' | 'sent' | 'delivered' | 'failed' | 'unknown',
    errorMessage?: string,
  ) => {
    await apiFetch(`/messages/${id}/delivery`, 'POST', {
      status,
      error_message: errorMessage || null,
    })
    await fetchPending()
  }, [fetchPending])

  const scheduleFollowUp = useCallback(async (id: number, dueDate: string, notes = '') => {
    await apiFetch(`/messages/${id}/follow-ups`, 'POST', {
      due_date: dueDate,
      notes,
    })
    await fetchPending()
  }, [fetchPending])

  const updateFollowUp = useCallback(async (
    followUpId: number,
    status: 'completed' | 'skipped',
    notes = '',
  ) => {
    await apiFetch(`/follow-ups/${followUpId}`, 'PATCH', { status, notes })
    await fetchPending()
  }, [fetchPending])

  const selectCompany = useCallback((company: string) => {
    setCurrentCompany(company)
    fetchPacket(company)
  }, [fetchPacket])

  return {
    running, stages, companies, currentCompany, currentPacket, currentRun, traceEvents, traceStatus,
    pendingMessages, profileText, profile, profileHarness, profileFetching, error, logEntries,
    buildPacket, fetchCompanies, fetchPacket, fetchPending,
    fetchProfile, saveProfile, fetchProfileSources, approveMessage, rejectMessage,
    recordDelivery, scheduleFollowUp, updateFollowUp, selectCompany,
  }
}
