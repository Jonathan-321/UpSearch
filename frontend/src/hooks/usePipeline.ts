import { useState, useCallback } from 'react'
import type {
  AgentStatus,
  PipelineStatus,
  Opportunity,
  Strategy,
  WandbRun,
} from '../types'
import {
  MOCK_OPPORTUNITIES,
  MOCK_STRATEGY,
  MOCK_DRAFT,
  INITIAL_WANDB_RUNS,
} from '../mockData'

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

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export function usePipeline() {
  const [status, setStatus] = useState<PipelineStatus>('idle')
  const [topic, setTopic] = useState('')
  const [agentStatuses, setAgentStatuses] = useState<AgentStatuses>(INITIAL_AGENTS)
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [selectedOpportunity, setSelectedOpp] = useState<Opportunity | null>(null)
  const [strategy, setStrategy] = useState<Strategy | null>(null)
  const [draft, setDraft] = useState('')
  const [wandbRuns, setWandbRuns] = useState<WandbRun[]>(INITIAL_WANDB_RUNS)

  // ── Start pipeline ────────────────────────────────────────────────────────
  // TODO: replace mock delays with real API call → POST /api/pipeline/start
  const startPipeline = useCallback(async (inputTopic: string) => {
    setTopic(inputTopic)
    setOpportunities([])
    setSelectedOpp(null)
    setStrategy(null)
    setDraft('')
    setAgentStatuses(INITIAL_AGENTS)

    // Stage 1: Scout
    setStatus('scouting')
    setAgentStatuses((prev) => ({ ...prev, scout: 'running' }))
    await delay(1800)

    // TODO: await fetch('/api/agents/scout', { method: 'POST', body: JSON.stringify({ topic }) })
    setOpportunities(MOCK_OPPORTUNITIES)
    setAgentStatuses((prev) => ({ ...prev, scout: 'complete', analyst: 'running' }))
    setStatus('analyzing')
    await delay(1800)

    // TODO: await fetch('/api/agents/analyst', { method: 'POST', body: JSON.stringify({ posts }) })
    setAgentStatuses((prev) => ({ ...prev, analyst: 'complete' }))
    setStatus('selecting')
  }, [])

  // ── Select an opportunity ─────────────────────────────────────────────────
  // TODO: replace mock delays with real API call → POST /api/pipeline/select
  const selectOpportunity = useCallback(async (opp: Opportunity) => {
    setSelectedOpp(opp)

    // Stage 3: Strategist
    setStatus('strategizing')
    setAgentStatuses((prev) => ({ ...prev, strategist: 'running' }))
    await delay(1400)

    // TODO: await fetch('/api/agents/strategist', { method: 'POST', body: JSON.stringify({ opportunity: opp }) })
    setStrategy(MOCK_STRATEGY)
    setAgentStatuses((prev) => ({ ...prev, strategist: 'complete', writer: 'running' }))
    setStatus('writing')
    await delay(1400)

    // TODO: await fetch('/api/agents/writer', { method: 'POST', body: JSON.stringify({ opportunity: opp, strategy }) })
    setDraft(MOCK_DRAFT)
    setAgentStatuses((prev) => ({ ...prev, writer: 'complete' }))
    setStatus('done')
  }, [])

  // ── Log to W&B ────────────────────────────────────────────────────────────
  // TODO: replace with real API call → POST /api/tracker/log
  const logToWandb = useCallback(
    (sent: boolean = false) => {
      if (!selectedOpportunity) return
      const newRun: WandbRun = {
        run_id: `us-${Math.random().toString(36).slice(2, 8)}`,
        topic,
        source: selectedOpportunity.post.source,
        fit_score: selectedOpportunity.analysis.fit_score,
        draft_created: true,
        sent,
        reply: false,
        last_updated: new Date().toLocaleString('en-US', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        }),
      }
      setWandbRuns((prev) => [newRun, ...prev])
    },
    [selectedOpportunity, topic],
  )

  const reset = useCallback(() => {
    setStatus('idle')
    setTopic('')
    setOpportunities([])
    setSelectedOpp(null)
    setStrategy(null)
    setDraft('')
    setAgentStatuses(INITIAL_AGENTS)
  }, [])

  return {
    status,
    topic,
    agentStatuses,
    opportunities,
    selectedOpportunity,
    strategy,
    draft,
    wandbRuns,
    startPipeline,
    selectOpportunity,
    setDraft,
    logToWandb,
    reset,
  }
}
