import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_BASE, evidenceLabel } from '../types'

const OS_BASE = API_BASE.replace('/api', '/os')

type AuditStatus = 'pass' | 'warn' | 'fail' | 'idle'

interface Company {
  id: number
  name: string
  lane: string
  fit_score: number
  hiring_status: string
  status: string
}

interface ProfileSource {
  kind: string
  value: string
  status: string
}

interface ProfileHarness {
  route_provider: string
  route_model: string
  route_reason: string
  sources: ProfileSource[]
  proof_bank: string[]
  target_lanes: string[]
  constraints: string[]
  claim_boundaries: string[]
  missing_inputs: string[]
  fetched_at?: string | null
  source_warnings?: string[]
}

interface ProfilePayload {
  content: string
  harness: ProfileHarness | null
}

interface Problem {
  id: number
  title: string
  description: string
  source_urls: string
  relevance_score: number
}

interface Person {
  id: number
  name: string
  role: string
  proximity: string
  source_url?: string | null
  linkedin_url?: string | null
  relevance_score: number
  relevance_reason: string
  /** "verified" | "unverified" from the people table; absent on legacy rows. */
  verification_status?: string | null
  /** Not yet emitted by the backend; rendered when present. */
  verification_reason?: string | null
}

interface Packet {
  technical_note?: string
  outreach_drafts?: string
  qa_score?: number
  qa_flags?: string
  crm_status?: string
}

interface CheckupMetric {
  name: string
  score: number
  detail: string
}

interface TraceEvent {
  event_type: 'agent_step' | 'handoff' | 'gate' | 'block' | 'error'
  status: string
  timestamp: string
  agent?: string
  agent_role?: string
  role?: string
  from_agent?: string
  to_agent?: string
  output_summary?: string
  reason?: string
  reads?: string[]
  writes?: string[]
  payload_keys?: string[]
  latency_ms?: number
  payload?: Record<string, unknown>
}

interface RunRecord {
  run_id: string
  company_name: string
  lane: string
  status: 'running' | 'complete' | 'failed' | 'cancelled'
  current_step?: string | null
  steps_completed: string[]
  qa_score?: number | null
  final_status?: string | null
  error_message?: string | null
}

interface Checkup {
  company: string
  status: string
  overall_score: number
  failure_category: string
  trace_status?: 'unavailable' | 'incomplete' | 'complete'
  suggested_fix: string
  metrics: CheckupMetric[]
  trace: {
    events: TraceEvent[]
    agent_steps: number
    handoffs: number
    missing_agents: string[]
  }
  facts?: {
    problem_source_urls?: string[]
    qa_flags?: string[]
    over_200_drafts?: string[]
    note_words?: number
  }
}

interface PacketPayload {
  company?: Company
  packet: Packet | null
  problems: Problem[]
  people: Person[]
  checkup: Checkup | null
  run: RunRecord | null
  trace_status: 'unavailable' | 'incomplete' | 'complete'
  trace: TraceEvent[]
  approval_state: 'unavailable' | 'required' | 'partially_approved' | 'approved'
  handoff_readiness: Array<{
    message_id: number
    actionable: boolean
    safety_reasons: string[]
  }>
}

interface PendingMessage {
  id: number
  company_name?: string
  variant: string
  content: string
  word_count: number
  status: string
  person_name?: string
  person_role?: string
  problem_title?: string
  problem_source_urls?: string[]
  qa_score?: number
  qa_flags?: string[]
  channel?: string
  platform?: string
  platform_label?: string
  platform_url?: string
  handoff_mode?: 'prefill_compose' | 'copy_then_open' | 'open_only'
  approval_contract?: string
  actionable?: boolean
  safety_reasons?: string[]
}

interface AuditRow {
  key: string
  title: string
  status: AuditStatus
  summary: string
  evidence: string[]
  nextAction?: string
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${OS_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(30_000),
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Request failed with ${res.status}`)
  }
  return res.json()
}

function safeParse<T>(value: string | undefined | null, fallback: T): T {
  if (!value) return fallback
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

function sourceList(problem: Problem): string[] {
  return safeParse<string[]>(problem.source_urls, [])
}

function metric(checkup: Checkup | null, name: string): CheckupMetric | undefined {
  return checkup?.metrics.find((item) => item.name.toLowerCase() === name.toLowerCase())
}

function scoreStatus(score: number | undefined, passAt = 8, warnAt = 5): AuditStatus {
  if (score === undefined) return 'idle'
  if (score >= passAt) return 'pass'
  if (score >= warnAt) return 'warn'
  return 'fail'
}

function wordCount(text = ''): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function statusText(status: AuditStatus): string {
  if (status === 'pass') return 'passed'
  if (status === 'warn') return 'needs review'
  if (status === 'fail') return 'blocked'
  return 'waiting'
}

function unique(values: Array<string | undefined | null>): string[] {
  return Array.from(new Set(values.filter(Boolean) as string[]))
}

function AuditCard({ row, index }: { row: AuditRow; index: number }) {
  return (
    <article className={`audit-card is-${row.status}`}>
      <div className="audit-card-top">
        <span>{String(index + 1).padStart(2, '0')}</span>
        <strong>{row.title}</strong>
        <em>{statusText(row.status)}</em>
      </div>
      <p>{row.summary}</p>
      <div className="audit-evidence">
        {row.evidence.slice(0, 4).map((item, evidenceIndex) => (
          <span key={`${row.key}-${evidenceIndex}-${item}`}>{item}</span>
        ))}
      </div>
      {row.nextAction && <div className="audit-next">{row.nextAction}</div>}
    </article>
  )
}

export default function HarnessCheckup() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [packetLoading, setPacketLoading] = useState(false)
  const [fetchingSources, setFetchingSources] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [profile, setProfile] = useState<ProfilePayload | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [messages, setMessages] = useState<PendingMessage[]>([])
  const [selectedCompany, setSelectedCompany] = useState('')
  const [packetPayload, setPacketPayload] = useState<PacketPayload | null>(null)
  const [copiedId, setCopiedId] = useState<number | null>(null)

  const loadBase = useCallback(async () => {
    setError(null)
    const [profileData, companiesData, messagesData] = await Promise.all([
      fetchJson<ProfilePayload>('/profile'),
      fetchJson<{ companies: Company[] }>('/companies'),
      fetchJson<{ messages: PendingMessage[] }>('/messages/pending?include_needs_review=true'),
    ])
    setProfile(profileData)
    setCompanies(companiesData.companies)
    setMessages(messagesData.messages)

    const preferred = companiesData.companies.find((company) => company.name === selectedCompany)
      ?? companiesData.companies.find((company) => company.name === 'Baseten')
      ?? companiesData.companies[0]
    if (preferred && preferred.name !== selectedCompany) {
      setSelectedCompany(preferred.name)
    }
    return preferred?.name ?? selectedCompany
  }, [selectedCompany])

  const loadPacket = useCallback(async (company: string) => {
    if (!company) return
    setPacketLoading(true)
    setPacketPayload(null)
    try {
      const data = await fetchJson<PacketPayload>(`/packet/${encodeURIComponent(company)}`)
      setPacketPayload(data)
    } finally {
      setPacketLoading(false)
    }
  }, [])

  const refreshAll = useCallback(async () => {
    setRefreshing(true)
    try {
      const company = await loadBase()
      if (company) await loadPacket(company)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Harness checkup failed.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [loadBase, loadPacket])

  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  useEffect(() => {
    if (!selectedCompany) return
    loadPacket(selectedCompany).catch((err) => {
      setError(err instanceof Error ? err.message : 'Could not load selected packet.')
    })
  }, [loadPacket, selectedCompany])

  const selectedMessages = useMemo(
    () => messages.filter((message) => message.company_name === selectedCompany),
    [messages, selectedCompany],
  )

  const auditRows = useMemo<AuditRow[]>(() => {
    const harness = profile?.harness
    const checkup = packetPayload?.checkup ?? null
    const problems = packetPayload?.problems ?? []
    const people = packetPayload?.people ?? []
    const packet = packetPayload?.packet

    const fetchedSources = harness?.sources.filter((source) => source.status === 'fetched') ?? []
    const missingSources = harness?.sources.filter((source) => ['missing', 'needs_fetch', 'failed'].includes(source.status)) ?? []
    const profileProofCount = harness?.proof_bank.length ?? 0
    const missingInputs = harness?.missing_inputs ?? []

    const sourceGrounding = metric(checkup, 'Source grounding')
    const problemSourceUrls = unique(problems.flatMap((problem) => sourceList(problem)))
    const sourceBackedProblems = problems.filter((problem) => sourceList(problem).length > 0).length

    const peopleMapping = metric(checkup, 'People mapping')
    const verifiedPeople = people.filter((person) => person.verification_status === 'verified')
    const peopleByVerification = [...people].sort((a, b) =>
      Number(b.verification_status === 'verified') - Number(a.verification_status === 'verified'))

    const technicalMetric = metric(checkup, 'Technical note')
    const noteWords = checkup?.facts?.note_words ?? wordCount(packet?.technical_note)
    const qaFlags = [
      ...(checkup?.facts?.qa_flags ?? []),
      ...safeParse<string[]>(packet?.qa_flags, []),
    ]

    const maxDraftWords = Math.max(0, ...selectedMessages.map((message) => message.word_count ?? wordCount(message.content)))
    const draftsMissingContract = selectedMessages.filter((message) => !message.approval_contract).length
    const draftsMissingPlatform = selectedMessages.filter((message) => !message.platform_url && !message.platform_label).length
    const quarantinedDrafts = selectedMessages.filter((message) => message.actionable === false).length
    const actionableDrafts = selectedMessages.length - quarantinedDrafts
    const allDraftsShort = selectedMessages.every((message) => (message.word_count ?? wordCount(message.content)) <= 200)
    const trace = checkup?.trace
    const traceStatus = packetPayload?.trace_status ?? 'unavailable'
    const traceEvents = packetPayload?.trace.length ?? 0

    return [
      {
        key: 'profile',
        title: 'Profile truth',
        status: profileProofCount > 0 ? (missingInputs.length ? 'warn' : 'pass') : 'fail',
        summary: profileProofCount > 0
          ? `${profileProofCount} proof signals are available for downstream agents.`
          : 'No proof bank is available, so generated claims cannot be trusted yet.',
        evidence: [
          `${fetchedSources.length} public sources fetched`,
          `${missingInputs.length} missing inputs`,
          `${harness?.route_provider ?? 'unknown'} / ${harness?.route_model ?? 'unknown'}`,
        ],
        nextAction: missingInputs.length ? `Add or authorize: ${missingInputs.join(', ')}.` : undefined,
      },
      {
        key: 'sources',
        title: 'Source fetch',
        status: missingSources.some((source) => source.status === 'failed')
          ? 'fail'
          : missingSources.some((source) => source.status === 'needs_fetch')
            ? 'warn'
            : fetchedSources.length
              ? 'pass'
              : 'warn',
        summary: fetchedSources.length
          ? 'The profile harness has real public source evidence to cite.'
          : 'The system has not fetched enough source evidence yet.',
        evidence: (harness?.sources ?? []).map((source) => `${source.kind}: ${source.status}`),
        nextAction: missingSources.length ? 'Fetch public sources or connect authenticated sources before relying on profile claims.' : undefined,
      },
      {
        key: 'problems',
        title: 'Problem grounding',
        status: sourceGrounding ? scoreStatus(sourceGrounding.score) : sourceBackedProblems ? 'warn' : 'fail',
        summary: sourceGrounding?.detail ?? `${sourceBackedProblems}/${problems.length} problems have source URLs.`,
        evidence: [
          `${problems.length} problems`,
          `${problemSourceUrls.length} unique source URLs`,
          ...problemSourceUrls.slice(0, 2),
        ],
        nextAction: sourceBackedProblems < problems.length ? 'Open problem claims should cite company docs, blogs, repos, HN, Reddit, or papers.' : undefined,
      },
      {
        key: 'people',
        title: 'People verification',
        status: peopleMapping ? scoreStatus(peopleMapping.score) : verifiedPeople.length ? 'warn' : 'fail',
        summary: peopleMapping?.detail ?? `${verifiedPeople.length}/${people.length} people verified against a primary source.`,
        evidence: peopleByVerification.slice(0, 3).map((person) =>
          person.verification_status === 'verified'
            ? `${person.name}: verified · ${person.source_url ? evidenceLabel(person.source_url) : 'profile URL'}`
            : `${person.name}: unverified`),
        nextAction: verifiedPeople.length < people.length
          ? `${people.length - verifiedPeople.length} unverified people stay out of outreach until a primary source confirms them.`
          : undefined,
      },
      {
        key: 'note',
        title: 'Technical note',
        status: technicalMetric ? scoreStatus(technicalMetric.score) : noteWords >= 300 ? 'pass' : noteWords >= 120 ? 'warn' : 'fail',
        summary: noteWords ? `${noteWords} words in the current technical note.` : 'No technical note is available for the selected packet.',
        evidence: [
          `QA score ${packet?.qa_score ?? 'missing'}`,
          qaFlags.length ? `${qaFlags.length} QA flags` : 'no QA flags surfaced',
          technicalMetric?.detail ?? 'local word-count fallback',
        ],
        nextAction: qaFlags.length ? qaFlags[0] : undefined,
      },
      {
        key: 'outreach',
        title: 'Outreach safety',
        status: selectedMessages.length === 0
          ? 'warn'
          : quarantinedDrafts === 0 && allDraftsShort && draftsMissingPlatform === 0
            ? 'pass'
            : 'fail',
        summary: selectedMessages.length
          ? `${actionableDrafts}/${selectedMessages.length} drafts are send-ready. Longest is ${maxDraftWords} words.`
          : 'No pending outreach drafts exist for this company.',
        evidence: [
          `${quarantinedDrafts} quarantined drafts`,
          `${draftsMissingPlatform} missing platform handoffs`,
          `${allDraftsShort ? 'all' : 'some'} drafts under 200 words`,
          ...unique(selectedMessages.map((message) => message.platform)).slice(0, 3),
        ],
        nextAction: quarantinedDrafts
          ? 'Fix the packet checkup before any platform handoff.'
          : !allDraftsShort
            ? 'Shorten drafts before platform handoff.'
            : undefined,
      },
      {
        key: 'action',
        title: 'Action gate',
        status: selectedMessages.length === 0
          ? 'warn'
          : quarantinedDrafts > 0 || actionableDrafts === 0
            ? 'fail'
            : draftsMissingContract === 0
            ? 'pass'
            : 'fail',
        summary: selectedMessages.length
          ? `${actionableDrafts} external actions are currently allowed. Every send still requires exact approval.`
          : 'There is no action queued for human review.',
        evidence: [
          `${draftsMissingContract} drafts missing approval contracts`,
          `${quarantinedDrafts} blocked by packet safety`,
          'Gmail/LinkedIn handoff only',
          'no automated send path',
        ],
        nextAction: quarantinedDrafts
          ? 'Keep platform actions disabled until the packet passes review.'
          : draftsMissingContract
            ? 'Add an approval contract before allowing any platform action.'
            : undefined,
      },
      {
        key: 'trace',
        title: 'Run trace',
        status: traceStatus === 'complete'
          ? 'pass'
          : traceStatus === 'incomplete'
            ? 'fail'
            : 'warn',
        summary: traceStatus === 'unavailable'
          ? 'This packet predates trace capture. Coordination cannot be evaluated from historical data.'
          : `${trace?.agent_steps ?? 0} agent steps, ${trace?.handoffs ?? 0} handoffs, ${traceEvents} persisted events.`,
        evidence: [
          `trace status: ${traceStatus}`,
          `run status: ${packetPayload?.run?.status ?? 'unavailable'}`,
          `current step: ${packetPayload?.run?.current_step ?? 'none'}`,
          `${trace?.missing_agents.length ?? 0} missing agents`,
        ],
        nextAction: traceStatus === 'incomplete' && trace?.missing_agents.length
          ? `Missing: ${trace.missing_agents.join(', ')}.`
          : undefined,
      },
    ]
  }, [packetPayload, profile, selectedMessages])

  const overall = packetPayload?.checkup?.overall_score
  const passedCount = auditRows.filter((row) => row.status === 'pass').length
  const blockedCount = auditRows.filter((row) => row.status === 'fail').length
  const traceEvents = packetPayload?.trace ?? []
  const selectedActionableCount = selectedMessages.filter((message) => message.actionable !== false).length
  const auditHydrating = loading || refreshing || packetLoading || !selectedCompany || (!packetPayload && companies.length > 0)
  const showingLoadingVerdict = auditHydrating && !packetPayload

  const fetchSources = async () => {
    setFetchingSources(true)
    setError(null)
    try {
      await fetchJson('/profile/fetch-sources', { method: 'POST' })
      await refreshAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not fetch public profile sources.')
    } finally {
      setFetchingSources(false)
    }
  }

  const handlePlatformOpen = async (message: PendingMessage) => {
    if (message.actionable === false) return
    if (message.handoff_mode === 'copy_then_open' || message.handoff_mode === 'prefill_compose') {
      try {
        await navigator.clipboard.writeText(message.content)
        setCopiedId(message.id)
      } catch {
        setCopiedId(null)
      }
    }
    if (message.platform_url) {
      window.open(message.platform_url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <div className="mode-page harness-checkup">
      <section className="mode-hero audit-hero">
        <div className="mode-hero-copy">
          <p className="studio-kicker">Packet review</p>
          <h1>Audit the packet before trusting the agents.</h1>
          <p>
            This is the live verification surface: profile evidence, source fetches, problem grounding,
            people mapping, technical notes, approval gates, platform handoffs, and the agent run trace.
          </p>
        </div>

        <div className="audit-score-card">
          <span>{overall === undefined ? '--' : overall.toFixed(1)}</span>
          <strong>{showingLoadingVerdict ? 'loading audit' : 'current score'}</strong>
          <p>{showingLoadingVerdict ? 'Reviewer blocked until packet state loads.' : `${passedCount}/8 checks passed · ${blockedCount} blocked`}</p>
        </div>
      </section>

      <section className="audit-control-strip">
        <div>
          <p className="section-label">Company under test</p>
          <div className="audit-company-row">
            {companies.map((company) => (
              <button
                key={company.id}
                type="button"
                className={company.name === selectedCompany ? 'is-active' : ''}
                onClick={() => setSelectedCompany(company.name)}
              >
                {company.name}
              </button>
            ))}
          </div>
        </div>
        <div className="audit-control-actions">
          <button type="button" onClick={fetchSources} disabled={fetchingSources}>
            {fetchingSources ? 'Fetching sources...' : 'Fetch profile sources'}
          </button>
          <button type="button" onClick={refreshAll} disabled={refreshing}>
            {refreshing ? 'Refreshing...' : 'Refresh audit'}
          </button>
        </div>
      </section>

      {error && <div className="audit-error">{error}</div>}

      {auditHydrating && !packetPayload ? (
        <section className="audit-panel audit-loading" aria-busy="true">
          <p className="section-label">Loading packet audit</p>
          <h2>Fetching evidence, traces, drafts, and checkup state for {selectedCompany || 'the selected company'}.</h2>
          <p className="audit-empty">The reviewer will stay blocked until the packet data is loaded.</p>
        </section>
      ) : (
        <section className="audit-grid" aria-busy={auditHydrating}>
          {auditRows.map((row, index) => (
            <AuditCard key={row.key} row={row} index={index} />
          ))}
        </section>
      )}

      <section className="audit-lower-grid">
        <div className="audit-panel">
          <div className="audit-panel-head">
            <div>
              <p className="section-label">Agent trace</p>
              <h2>
                {packetPayload?.run
                  ? `${packetPayload.run.status}: ${packetPayload.run.current_step ?? 'pipeline'}`
                  : 'No persisted run metadata'}
              </h2>
            </div>
            <span>{packetPayload?.trace_status ?? 'unavailable'} · {traceEvents.length} events</span>
          </div>
          <div className="audit-trace-list">
            {traceEvents.slice(0, 10).map((event, index) => (
              <article key={`${event.timestamp}-${index}`}>
                <span>{event.event_type === 'handoff' ? 'handoff' : event.agent ?? 'agent'}</span>
                <strong>
                  {event.event_type === 'handoff'
                    ? `${event.from_agent} -> ${event.to_agent}`
                    : event.role ?? event.agent_role ?? event.output_summary ?? event.event_type}
                </strong>
                <p>{event.output_summary || event.reason || event.payload_keys?.join(', ') || 'No summary captured.'}</p>
              </article>
            ))}
            {traceEvents.length === 0 && (
              <p className="audit-empty">
                No trace is attached to this packet yet. Historical packets may need to be rerun after trace capture.
              </p>
            )}
          </div>
        </div>

        <div className="audit-panel">
          <div className="audit-panel-head">
            <div>
              <p className="section-label">Human reviewer</p>
              <h2>Pending action queue</h2>
            </div>
            <span>{selectedActionableCount}/{selectedMessages.length} ready</span>
          </div>
          <div className="audit-action-list">
            {selectedMessages.slice(0, 4).map((message) => (
              <article key={message.id}>
                <div>
                  <span>{message.platform ?? message.channel ?? 'manual'}</span>
                  <strong>{message.person_name ?? 'Unknown person'}</strong>
                  <p>{message.problem_title ?? 'No problem title attached'}</p>
                </div>
                <blockquote>{message.content}</blockquote>
                {message.approval_contract && <em>{message.approval_contract}</em>}
                {message.actionable === false && (
                  <em>{(message.safety_reasons ?? ['This draft is quarantined until the packet passes review.']).slice(0, 2).join(' ')}</em>
                )}
                <button type="button" disabled={message.actionable === false} onClick={() => handlePlatformOpen(message)}>
                  {message.actionable === false
                    ? 'Blocked by review'
                    : copiedId === message.id
                      ? 'Copied draft. Open platform'
                      : message.platform_label ?? 'Open platform'}
                </button>
              </article>
            ))}
            {selectedMessages.length === 0 && (
              <p className="audit-empty">No pending drafts for {selectedCompany || 'this company'}.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
