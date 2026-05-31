import type { SupervisorScores } from '../types'

interface Props { scores: SupervisorScores }

const AGENTS: { key: keyof SupervisorScores; label: string }[] = [
  { key: 'scout', label: 'Scout' },
  { key: 'analyst', label: 'Analyst' },
  { key: 'strategist', label: 'Strategist' },
  { key: 'writer', label: 'Writer' },
]

export default function SupervisorPanel({ scores }: Props) {
  const available = AGENTS.filter(agent => scores[agent.key])
  if (!available.length) return null
  const values = available.map(agent => scores[agent.key]!.score)
  const overall = Math.round((values.reduce((sum, score) => sum + score, 0) / values.length) * 10) / 10
  const passed = available.every(agent => scores[agent.key]!.passed)

  return (
    <section className="panel overflow-hidden">
      <header className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="workspace-label">Quality Control</p>
          <h2 className="text-base font-semibold text-text-1 mt-1">Supervisor report</h2>
        </div>
        <span className={`badge font-mono ${passed ? 'badge-success' : 'badge-error'}`}>Overall {overall}/10</span>
      </header>
      <div className="divide-y divide-border">
        {available.map(({ key, label }) => {
          const score = scores[key]!
          return (
            <div key={key} className="px-5 py-3.5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm font-semibold text-text-1">{label}</span>
                <span className={`badge font-mono ${score.passed ? 'badge-success' : 'badge-error'}`}>{score.score}/10</span>
              </div>
              <p className="text-xs text-text-2 mt-2">{score.reasoning}</p>
              {score.flags.length > 0 && <div className="flex flex-wrap gap-2 mt-2">
                {score.flags.map((flag, index) => <span key={index} className="badge badge-warning">! {flag}</span>)}
              </div>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
