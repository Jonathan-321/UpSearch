import type { Strategy } from '../types'

interface Props { strategy: Strategy }

export default function StrategyPanel({ strategy }: Props) {
  const rows = [
    ['Target', strategy.target_role],
    ['Hook', strategy.hook],
    ['Icebreaker', strategy.icebreaker],
    ['Suggested ask', strategy.suggested_ask],
  ].filter(([, value]) => value)

  return (
    <section className="panel overflow-hidden">
      <header className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="workspace-label">Strategy</p>
          <h3 className="text-base font-semibold text-text-1 mt-1">Outreach angle</h3>
        </div>
        <span className="badge badge-accent">{strategy.channel}</span>
      </header>
      <div className="divide-y divide-border px-5">
        {rows.map(([label, value]) => (
          <div key={label} className="py-4">
            <p className="section-head">{label}</p>
            <p className="text-sm text-text-2 leading-relaxed mt-1.5">{value}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
