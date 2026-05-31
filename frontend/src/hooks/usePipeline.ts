import { useState, useCallback } from 'react'
import type {
  AgentStatus,
  PipelineStatus,
  Opportunity,
  Strategy,
  SupervisorScores,
  WandbRun,
  LogEntry,
  LogLevel,
} from '../types'
import { API_BASE } from '../types'
import { INITIAL_WANDB_RUNS } from '../mockData'

interface AgentStatuses {
  scout: AgentStatus
  analyst: AgentStatus
  strategist: AgentStatus
  writer: AgentStatus
}

const INITIAL_AGENTS: AgentStatuses = {
  scout: 'waiting',
  analyst: 'waiting',
  strategist: 'waiting',
  writer: 'waiting',
}

async function apiFetch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: body !== undefined ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(120_000), // 2 min max per stage
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `API error ${res.status}`)
  }
  return res.json()
}

function nowTs(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function usePipeline() {
  const [status, setStatus] = useState<PipelineStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [topic, setTopic] = useState('')
  const [agentStatuses, setAgentStatuses] = useState<AgentStatuses>(INITIAL_AGENTS)
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [selectedOpportunity, setSelectedOpp] = useState<Opportunity | null>(null)
  const [strategy, setStrategy] = useState<Strategy | null>(null)
  const [draft, setDraft] = useState('')
  const [supervisorScores, setSupervisorScores] = useState<SupervisorScores>({})
  const [wandbRuns, setWandbRuns] = useState<WandbRun[]>(INITIAL_WANDB_RUNS)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])

  const addLog = useCallback((agent: string, level: LogLevel, message: string, elapsed?: string) => {
    setLogEntries(prev => [
      ...prev.slice(-99),
      { ts: nowTs(), agent, level, message, elapsed },
    ])
  }, [])

  // ── Stage 1 + 2: Scout then Analyst ──────────────────────────────────────
  const startPipeline = useCallback(async (inputTopic: string, mode = 'jobs') => {
    setTopic(inputTopic)
    setOpportunities([])
    setSelectedOpp(null)
    setStrategy(null)
    setDraft('')
    setSupervisorScores({})
    setError(null)
    setAgentStatuses(INITIAL_AGENTS)
    setLogEntries([])

    // Stage 1: Scout
    setStatus('scouting')
    setAgentStatuses(prev => ({ ...prev, scout: 'running' }))
    addLog('Scout', 'STARTED', `Preparing queries for "${inputTopic}"`)
    addLog('Scout', 'SOURCE', 'Searching Hacker News')
    addLog('Scout', 'SOURCE', 'Searching Reddit')
    const t0Scout = Date.now()
    try {
      const scoutData = await apiFetch<{ posts: unknown[]; supervisor: unknown }>(
        '/scout', { topic: inputTopic, mode }
      )
      const posts = scoutData.posts as Opportunity['post'][]
      addLog('Scout', 'COMPLETE', `Found ${posts.length} public posts`, `${((Date.now() - t0Scout) / 1000).toFixed(1)}s`)
      setSupervisorScores(prev => ({ ...prev, scout: scoutData.supervisor as SupervisorScores['scout'] }))
      setAgentStatuses(prev => ({ ...prev, scout: 'complete', analyst: 'running' }))
      setStatus('analyzing')

      // Stage 2: Analyst
      addLog('Analyst', 'STARTED', `Scoring ${posts.length} posts against profile`)
      const t0Analyst = Date.now()
      const analyzeData = await apiFetch<{ opportunities: Opportunity[]; supervisor: unknown }>(
        '/analyze', { posts }
      )
      addLog('Analyst', 'COMPLETE',
        `Kept ${analyzeData.opportunities.length} leads with fit ≥ 5`,
        `${((Date.now() - t0Analyst) / 1000).toFixed(1)}s`)
      setOpportunities(analyzeData.opportunities)
      setSupervisorScores(prev => ({ ...prev, analyst: analyzeData.supervisor as SupervisorScores['analyst'] }))
      setAgentStatuses(prev => ({ ...prev, analyst: 'complete' }))
      setStatus('selecting')

    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Pipeline failed'
      addLog('Scout', 'ERROR', msg)
      setError(msg)
      setStatus('error')
      setAgentStatuses(prev => ({ ...prev, scout: 'error', analyst: 'error' }))
    }
  }, [addLog])

  // ── Stage 3 + 4: Strategist then Writer ───────────────────────────────────
  const selectOpportunity = useCallback(async (opp: Opportunity) => {
    setSelectedOpp(opp)
    setError(null)

    // Stage 3: Strategist
    setStatus('strategizing')
    setAgentStatuses(prev => ({ ...prev, strategist: 'running' }))
    const shortTitle = opp.post.title.length > 48 ? opp.post.title.slice(0, 48) + '…' : opp.post.title
    addLog('Strategist', 'STARTED', `Planning outreach angle for "${shortTitle}"`)
    const t0Strat = Date.now()
    try {
      const stratData = await apiFetch<{ strategy: Strategy; supervisor: unknown }>(
        '/strategize', { post: opp.post, analysis: opp.analysis }
      )
      addLog('Strategist', 'COMPLETE',
        `Channel: ${stratData.strategy.channel} · target: ${stratData.strategy.target_role}`,
        `${((Date.now() - t0Strat) / 1000).toFixed(1)}s`)
      setStrategy(stratData.strategy)
      setSupervisorScores(prev => ({ ...prev, strategist: stratData.supervisor as SupervisorScores['strategist'] }))
      setAgentStatuses(prev => ({ ...prev, strategist: 'complete', writer: 'running' }))
      setStatus('writing')

      // Stage 4: Writer
      addLog('Writer', 'STARTED', 'Drafting outreach note in student voice')
      const t0Writer = Date.now()
      const writeData = await apiFetch<{ draft: string; word_count?: number; supervisor: unknown }>(
        '/write', { post: opp.post, analysis: opp.analysis, strategy: stratData.strategy }
      )
      const wc = writeData.word_count ?? writeData.draft.split(/\s+/).filter(Boolean).length
      addLog('Writer', 'COMPLETE', `${wc} words written`, `${((Date.now() - t0Writer) / 1000).toFixed(1)}s`)
      setDraft(writeData.draft)
      setSupervisorScores(prev => ({ ...prev, writer: writeData.supervisor as SupervisorScores['writer'] }))
      setAgentStatuses(prev => ({ ...prev, writer: 'complete' }))
      setStatus('done')

    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Agent failed'
      addLog('Pipeline', 'ERROR', msg)
      setError(msg)
      setStatus('error')
      setAgentStatuses(prev => ({ ...prev, strategist: 'error', writer: 'error' }))
    }
  }, [addLog])

  // ── Log to W&B ────────────────────────────────────────────────────────────
  const logToWandb = useCallback(async (sent = false) => {
    if (!selectedOpportunity || !strategy) return null
    try {
      const data = await apiFetch<{ run_id: string }>('/log', {
        post: selectedOpportunity.post,
        analysis: selectedOpportunity.analysis,
        strategy,
        draft,
        sent,
        supervisor_summary: {
          agent_scores: {
            scout: supervisorScores.scout?.score,
            analyst: supervisorScores.analyst?.score,
            strategist: supervisorScores.strategist?.score,
            writer: supervisorScores.writer?.score,
          },
          overall_score: (() => {
            const vals = Object.values(supervisorScores)
              .map(s => s?.score)
              .filter((s): s is number => typeof s === 'number')
            return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
          })(),
          total_flags: Object.values(supervisorScores)
            .flatMap(s => s?.flags ?? []).length,
          passed: Object.values(supervisorScores).every(s => s?.passed !== false),
        },
      })
      const newRun: WandbRun = {
        run_id: data.run_id,
        topic,
        source: selectedOpportunity.post.source,
        fit_score: selectedOpportunity.analysis.fit_score,
        draft_created: true,
        sent,
        reply: false,
        last_updated: new Date().toLocaleString('en-US', {
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit',
        }),
      }
      setWandbRuns(prev => [newRun, ...prev])
      return data.run_id
    } catch {
      return null
    }
  }, [selectedOpportunity, strategy, draft, supervisorScores, topic])

  const reset = useCallback(() => {
    setStatus('idle')
    setError(null)
    setTopic('')
    setOpportunities([])
    setSelectedOpp(null)
    setStrategy(null)
    setDraft('')
    setSupervisorScores({})
    setAgentStatuses(INITIAL_AGENTS)
  }, [])

  return {
    status,
    error,
    topic,
    agentStatuses,
    opportunities,
    selectedOpportunity,
    strategy,
    draft,
    supervisorScores,
    wandbRuns,
    logEntries,
    startPipeline,
    selectOpportunity,
    setDraft,
    logToWandb,
    reset,
  }
}
