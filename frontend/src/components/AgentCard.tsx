import type { AgentStatus } from '../types'

interface AgentCardProps {
  name: string
  description: string
  icon: React.ReactNode
  status: AgentStatus
  stat?: string
}

const STATUS_CONFIG: Record<AgentStatus, { label: string; dot: string; badge: string }> = {
  waiting: {
    label: 'Waiting',
    dot: 'bg-zinc-600',
    badge: 'bg-zinc-800 text-zinc-500 border-zinc-700',
  },
  running: {
    label: 'Running',
    dot: 'bg-blue-400 animate-pulse',
    badge: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  complete: {
    label: 'Complete',
    dot: 'bg-emerald-400',
    badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  },
}

export default function AgentCard({ name, description, icon, status, stat }: AgentCardProps) {
  const cfg = STATUS_CONFIG[status]

  return (
    <div
      className={`card flex-1 min-w-[140px] p-4 flex flex-col gap-3 transition-all duration-300
        ${status === 'running' ? 'border-blue-500/30 animate-glow-pulse' : ''}
        ${status === 'complete' ? 'border-emerald-500/20' : ''}`}
    >
      {/* Icon */}
      <div
        className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-300
          ${status === 'complete' ? 'bg-emerald-500/15 text-emerald-400' : ''}
          ${status === 'running' ? 'bg-blue-500/15 text-blue-400' : ''}
          ${status === 'waiting' ? 'bg-zinc-800 text-zinc-500' : ''}`}
      >
        {icon}
      </div>

      {/* Name + description */}
      <div>
        <p className="text-sm font-semibold text-zinc-100">{name}</p>
        <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{description}</p>
      </div>

      {/* Footer: status + stat */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-zinc-800">
        <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.badge}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          {cfg.label}
        </span>
        {stat && <span className="text-xs text-zinc-500">{stat}</span>}
      </div>
    </div>
  )
}
