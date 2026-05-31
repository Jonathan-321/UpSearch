import type { OSCompany } from '../hooks/useOS'

interface Props {
  companies: OSCompany[]
  currentCompany: string
  onSelect: (name: string) => void
}

function FitBar({ score }: { score: number }) {
  const color = score >= 8 ? 'bg-emerald-500' : score >= 6 ? 'bg-amber-500' : 'bg-red-500'
  const text  = score >= 8 ? 'text-emerald-400' : score >= 6 ? 'text-amber-400' : 'text-red-400'
  return (
    <div className="flex items-center gap-2">
      <span className={`text-sm font-bold tabular-nums w-5 text-right ${text}`}>{score}</span>
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className={`h-1.5 w-2 rounded-sm transition-colors ${i < score ? color : 'bg-zinc-800'}`}/>
        ))}
      </div>
    </div>
  )
}

const STATUS: Record<string, { label: string; color: string; dot: string }> = {
  packet_ready: { label: 'Packet ready',  color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', dot: 'bg-emerald-400' },
  needs_review: { label: 'Needs review',  color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',     dot: 'bg-amber-400' },
  researched:   { label: 'Researched',    color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',         dot: 'bg-blue-400' },
  sourced:      { label: 'Sourced',       color: 'text-zinc-500 bg-zinc-800/50 border-zinc-700',            dot: 'bg-zinc-600' },
}

const LANES: Record<string, string> = {
  ai_infra:  'AI Infra',
  inference: 'Inference',
  agentic:   'Agentic',
  dev_tools: 'Dev Tools',
  data:      'Data',
  robotics:  'Robotics',
}

export default function CRMTable({ companies, currentCompany, onSelect }: Props) {
  if (companies.length === 0) {
    return (
      <div className="card p-8 flex flex-col items-center gap-3 animate-fade-in-up">
        <div className="w-10 h-10 rounded-xl bg-zinc-800/60 flex items-center justify-center">
          <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} className="text-zinc-600">
            <path strokeLinecap="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16"/>
            <path strokeLinecap="round" d="M3 21h18M9 7h1m-1 4h1m4-4h1m-1 4h1"/>
          </svg>
        </div>
        <p className="text-sm text-zinc-500">No companies yet</p>
        <p className="text-xs text-zinc-700">Build a packet above to add the first one</p>
      </div>
    )
  }

  return (
    <section className="card overflow-hidden animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.05]">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-lg bg-violet-500/15 flex items-center justify-center">
            <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} className="text-violet-400">
              <path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </div>
          <span className="text-sm font-semibold text-zinc-200">Company CRM</span>
        </div>
        <span className="text-xs text-zinc-600 tabular-nums">{companies.length} companies</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-white/[0.04]">
        {companies.map((c, i) => {
          const isSelected = c.name === currentCompany
          const st = STATUS[c.status] ?? STATUS['sourced']

          return (
            <div
              key={c.id}
              onClick={() => onSelect(c.name)}
              className={`
                flex items-center justify-between px-5 py-3.5 gap-4 cursor-pointer
                transition-all duration-200 group animate-fade-in-up
                ${isSelected
                  ? 'bg-violet-500/[0.07] border-l-2 border-l-violet-500 pl-[18px]'
                  : 'hover:bg-white/[0.02] border-l-2 border-l-transparent'}
              `}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {/* Company name + lane */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors">
                    {c.name}
                  </span>
                  <span className="text-xs text-zinc-600 bg-zinc-800/60 px-1.5 py-0.5 rounded-md">
                    {LANES[c.lane] ?? c.lane}
                  </span>
                </div>
                <span className={`mt-1 inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${st.color}`}>
                  <span className={`w-1 h-1 rounded-full ${st.dot}`}/>
                  {st.label}
                </span>
              </div>

              {/* Fit bar */}
              <div className="shrink-0">
                {c.fit_score > 0 ? <FitBar score={c.fit_score}/> : <span className="text-xs text-zinc-700">—</span>}
              </div>

              {/* Arrow */}
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                className={`shrink-0 transition-colors ${isSelected ? 'text-violet-400' : 'text-zinc-800 group-hover:text-zinc-600'}`}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
              </svg>
            </div>
          )
        })}
      </div>
    </section>
  )
}
