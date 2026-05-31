import AgentCard from './AgentCard'
import type { AgentStatus } from '../types'

interface Props {
  agentStatuses: Record<'scout' | 'analyst' | 'strategist' | 'writer', AgentStatus>
  opportunityCount: number
}

const Icon = ({ children }: { children: React.ReactNode }) => <span className="font-mono text-xs">{children}</span>

export default function PipelineStepper({ agentStatuses, opportunityCount }: Props) {
  return (
    <section>
      <p className="workspace-label mb-3">Agent Pipeline</p>
      <div className="flex gap-3 overflow-x-auto pb-1">
        <AgentCard name="Scout" description="Searches Reddit and HN for useful public signals"
          icon={<Icon>01</Icon>} status={agentStatuses.scout}
          stat={agentStatuses.scout === 'complete' ? `${opportunityCount} posts` : undefined} />
        <AgentCard name="Analyst" description="Scores fit and extracts a grounded technical angle"
          icon={<Icon>02</Icon>} status={agentStatuses.analyst}
          stat={agentStatuses.analyst === 'complete' ? `${opportunityCount} scored` : undefined} />
        <AgentCard name="Strategist" description="Chooses the right recipient, hook, and channel"
          icon={<Icon>03</Icon>} status={agentStatuses.strategist} />
        <AgentCard name="Writer" description="Drafts a concise outreach note in a student voice"
          icon={<Icon>04</Icon>} status={agentStatuses.writer} />
      </div>
    </section>
  )
}
