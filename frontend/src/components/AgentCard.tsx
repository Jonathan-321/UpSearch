import type { AgentStatus } from '../types'

interface Props {
  name: string
  description: string
  icon: React.ReactNode
  status: AgentStatus
  stat?: string
}

export default function AgentCard({ name, description, icon, status, stat }: Props) {
  const active = status === 'running'
  const done = status === 'complete'
  const error = status === 'error'

  return (
    <div className={`panel min-w-[180px] flex-1 p-4 transition-colors ${
      active ? 'border-amber-500/60 bg-amber-500/[0.04]' :
      done ? 'border-emerald-500/20' :
      error ? 'border-red-500/30' : ''
    }`}>
      <div className="flex items-center justify-between gap-2">
        <span className={active ? 'text-amber-400' : done ? 'text-emerald-400' : error ? 'text-red-400' : 'text-text-3'}>{icon}</span>
        <span className={`status-dot ${active ? 'bg-amber-400 animate-pulse' : done ? 'bg-emerald-400' : error ? 'bg-red-400' : ''}`} />
      </div>
      <p className="text-sm font-semibold text-text-1 mt-4">{name}</p>
      <p className="text-xs text-text-3 mt-1 leading-relaxed">{description}</p>
      <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-border">
        <span className="text-[10px] uppercase tracking-wider text-text-2">{status}</span>
        {stat && <span className="font-mono text-[10px] text-text-3">{stat}</span>}
      </div>
    </div>
  )
}
