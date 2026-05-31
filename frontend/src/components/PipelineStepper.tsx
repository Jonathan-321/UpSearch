import AgentCard from './AgentCard'
import type { AgentStatus } from '../types'

interface AgentStatuses {
  scout: AgentStatus
  analyst: AgentStatus
  strategist: AgentStatus
  writer: AgentStatus
}

interface PipelineStepperProps {
  agentStatuses: AgentStatuses
  opportunityCount: number
}

const ScoutIcon = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <circle cx="11" cy="11" r="7" />
    <path strokeLinecap="round" d="M16.5 16.5L21 21" />
  </svg>
)

const AnalystIcon = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
)

const StrategistIcon = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="3" />
    <line x1="12" y1="3" x2="12" y2="9" strokeLinecap="round" />
    <line x1="12" y1="15" x2="12" y2="21" strokeLinecap="round" />
    <line x1="3" y1="12" x2="9" y2="12" strokeLinecap="round" />
    <line x1="15" y1="12" x2="21" y2="12" strokeLinecap="round" />
  </svg>
)

const WriterIcon = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
  </svg>
)

const Connector = ({ active }: { active: boolean }) => (
  <div className="hidden sm:flex items-center px-1">
    <div className={`flex items-center gap-0.5 transition-colors duration-500 ${active ? 'text-violet-500' : 'text-zinc-700'}`}>
      <div className={`h-px w-6 transition-colors duration-500 ${active ? 'bg-violet-500' : 'bg-zinc-800'}`} />
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
        <path d="M3 2l6 4-6 4V2z" />
      </svg>
    </div>
  </div>
)

export default function PipelineStepper({ agentStatuses, opportunityCount }: PipelineStepperProps) {
  const { scout, analyst, strategist, writer } = agentStatuses

  return (
    <section className="animate-fade-in-up">
      <div className="flex items-center gap-1 mb-3">
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Pipeline</span>
      </div>
      <div className="flex items-stretch gap-0">
        <AgentCard
          name="Scout"
          description="Searches Reddit & HN for real open problems"
          icon={<ScoutIcon />}
          status={scout}
          stat={scout === 'complete' ? `${opportunityCount} posts` : undefined}
        />
        <Connector active={scout === 'complete'} />
        <AgentCard
          name="Analyst"
          description="Scores fit 1–10 and extracts technical angle"
          icon={<AnalystIcon />}
          status={analyst}
          stat={analyst === 'complete' ? `${opportunityCount} scored` : undefined}
        />
        <Connector active={analyst === 'complete'} />
        <AgentCard
          name="Strategist"
          description="Decides who to contact, hook, and channel"
          icon={<StrategistIcon />}
          status={strategist}
        />
        <Connector active={strategist === 'complete'} />
        <AgentCard
          name="Writer"
          description="Drafts ≤200-word cold email in student voice"
          icon={<WriterIcon />}
          status={writer}
        />
      </div>
    </section>
  )
}
