import type { Strategy } from '../types'

interface StrategyPanelProps {
  strategy: Strategy
}

const CHANNEL_CONFIG: Record<string, { label: string; color: string }> = {
  email: { label: 'Email', color: 'bg-sky-500/15 text-sky-400 border-sky-500/30' },
  linkedin: { label: 'LinkedIn', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  x: { label: 'X / Twitter', color: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30' },
}

interface RowProps {
  label: string
  value: string
  accent?: boolean
}

function Row({ label, value, accent }: RowProps) {
  return (
    <div className="py-3 border-b border-zinc-800 last:border-0">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-sm leading-relaxed ${accent ? 'text-zinc-100 font-medium' : 'text-zinc-300'}`}>
        {value}
      </p>
    </div>
  )
}

export default function StrategyPanel({ strategy }: StrategyPanelProps) {
  const ch = CHANNEL_CONFIG[strategy.channel] ?? CHANNEL_CONFIG['email']

  return (
    <div className="card p-5 flex flex-col gap-4 animate-fade-in-up h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-violet-500/20 flex items-center justify-center">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-violet-400">
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-zinc-100">Outreach Strategy</span>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${ch.color}`}>
          {ch.label}
        </span>
      </div>

      {/* Strategy rows */}
      <div className="divide-y divide-zinc-800">
        <Row label="Target" value={strategy.target_role} accent />
        <Row label="Hook" value={strategy.hook} />
        <Row label="Icebreaker" value={strategy.icebreaker} />
        <Row label="Suggested ask" value={strategy.suggested_ask} />
      </div>
    </div>
  )
}
