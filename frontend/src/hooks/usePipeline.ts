import { useState, useCallback } from 'react'
import type {
  AgentStatus,
  PipelineStatus,
  Opportunity,
  Strategy,
  SupervisorScores,
  WandbRun,
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

    // Stage 1: Scout
    setStatus('scouting')
    setAgentStatuses(prev => ({ ...prev, scout: 'running' }))
    try {
      const scoutData = await apiFetch<{ posts: unknown[]; supervisor: unknown }>(
        '/scout', { topic: inputTopic, mode }
      )
      const posts = scoutData.posts as Opportunity['post'][]
      setSupervisorScores(prev => ({ ...prev, scout: scoutData.supervisor as SupervisorScores['scout'] }))
      setAgentStatuses(prev => ({ ...prev, scout: 'complete', analyst: 'running' }))
      setStatus('analyzing')

      // Stage 2: Analyst
      const analyzeData = await apiFetch<{ opportunities: Opportunity[]; supervisor: unknown }>(
        '/analyze', { posts }
      )
      setOpportunities(analyzeData.opportunities)
      setSupervisorScores(prev => ({ ...prev, analyst: analyzeData.supervisor as SupervisorScores['analyst'] }))
      setAgentStatuses(prev => ({ ...prev, analyst: 'complete' }))
      setStatus('selecting')

    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Pipeline failed'
      setError(msg)
      setStatus('error')
      setAgentStatuses(prev => ({ ...prev, scout: 'error', analyst: 'error' }))
    }
  }, [])

  // ── Stage 3 + 4: Strategist then Writer ───────────────────────────────────
  const selectOpportunity = useCallback(async (opp: Opportunity) => {
    setSelectedOpp(opp)
    setError(null)

    // Stage 3: Strategist
    setStatus('strategizing')
    setAgentStatuses(prev => ({ ...prev, strategist: 'running' }))
    try {
      const stratData = await apiFetch<{ strategy: Strategy; supervisor: unknown }>(
        '/strategize', { post: opp.post, analysis: opp.analysis }
      )
      setStrategy(stratData.strategy)
      setSupervisorScores(prev => ({ ...prev, strategist: stratData.supervisor as SupervisorScores['strategist'] }))
      setAgentStatuses(prev => ({ ...prev, strategist: 'complete', writer: 'running' }))
      setStatus('writing')

      // Stage 4: Writer
      const writeData = await apiFetch<{ draft: string; supervisor: unknown }>(
        '/write', { post: opp.post, analysis: opp.analysis, strategy: stratData.strategy }
      )
      setDraft(writeData.draft)
      setSupervisorScores(prev => ({ ...prev, writer: writeData.supervisor as SupervisorScores['writer'] }))
      setAgentStatuses(prev => ({ ...prev, writer: 'complete' }))
      setStatus('done')

    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Agent failed'
      setError(msg)
      setStatus('error')
      setAgentStatuses(prev => ({ ...prev, strategist: 'error', writer: 'error' }))
    }
  }, [])

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
    startPipeline,
    selectOpportunity,
    setDraft,
    logToWandb,
    reset,
  }
}
