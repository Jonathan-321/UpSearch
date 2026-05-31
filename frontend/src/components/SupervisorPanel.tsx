import type { SupervisorScores } from '../types'

interface SupervisorPanelProps {
  scores: SupervisorScores
}

const AGENTS: { key: keyof SupervisorScores; label: string }[] = [
  { key: 'scout',      label: 'Scout' },
  { key: 'analyst',    label: 'Analyst' },
  { key: 'strategist', label: 'Strategist' },
  { key: 'writer',     label: 'Writer' },
]

function ScoreBar({ score }: { score: number }) {
  const color = score >= 8 ? 'bg-emerald-400' : score >= 6 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className={`h-1.5 w-2.5 rounded-sm ${i < score ? color : 'bg-zinc-800'}`} />
        ))}
      </div>
      <span className={`text-xs font-bold tabular-nums ${score >= 8 ? 'text-emerald-400' : score >= 6 ? 'text-amber-400' : 'text-red-400'}`}>
        {score}/10
      </span>
    </div>
  )
}

export default function SupervisorPanel({ scores }: SupervisorPanelProps) {
  const available = AGENTS.filter(a => scores[a.key])
  if (available.length === 0) return null

  const vals = available.map(a => scores[a.key]!.score)
  const overall = Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10
  const allPassed = available.every(a => scores[a.key]!.passed)
  const allFlags = available.flatMap(a => scores[a.key]!.flags.map(f => ({ agent: a.label, flag: f })))

  return (
    <section className="card animate-fade-in-up overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-violet-500/20 flex items-center justify-center">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-violet-400">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100">Supervisor Report</p>
            <p className="text-xs text-zinc-500">Live quality evaluation — logged to W&amp;B</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 text-xs font-bold px-3 py-1 rounded-full border ${
          allPassed
            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
            : 'bg-red-500/15 text-red-400 border-red-500/30'
        }`}>
          <span>{allPassed ? 'All passed' : 'Flags raised'}</span>
          <span className="text-zinc-500 font-normal">|</span>
          <span>Overall {overall}/10</span>
        </div>
      </div>

      {/* Per-agent rows */}
      <div className="divide-y divide-zinc-800/50">
        {available.map(({ key, label }) => {
          const s = scores[key]!
          return (
            <div key={key} className="px-5 py-3 flex flex-col gap-1.5 animate-fade-in-up">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 min-w-[90px]">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${s.passed ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <span className="text-xs font-semibold text-zinc-300">{label}</span>
                </div>
                <ScoreBar score={s.score} />
                <p className="text-xs text-zinc-500 flex-1 text-right hidden md:block truncate">
                  {s.reasoning}
                </p>
              </div>
              {s.flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pl-5">
                  {s.flags.map((f, i) => (
                    <span key={i} className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md">
                      ! {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {allFlags.length === 0 && (
        <div className="px-5 py-3 text-xs text-zinc-600 italic">No flags raised across all agents.</div>
      )}
    </section>
  )
}
