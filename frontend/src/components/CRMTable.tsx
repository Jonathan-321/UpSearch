import type { OSCompany } from '../hooks/useOS'

interface Props {
  companies: OSCompany[]
  currentCompany: string
  onSelect: (name: string) => void
}

const STATUS_COLOR: Record<string, string> = {
  packet_ready: 'text-emerald-400',
  needs_review: 'text-amber-400',
  researched:   'text-blue-400',
  sourced:      'text-zinc-500',
}

export default function CRMTable({ companies, currentCompany, onSelect }: Props) {
  if (companies.length === 0) {
    return (
      <div className="card p-6 text-center text-zinc-600 text-sm animate-fade-in-up">
        No companies in CRM yet. Build a packet above to add the first one.
      </div>
    )
  }

  return (
    <section className="card overflow-hidden animate-fade-in-up">
      <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-violet-400">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
          </svg>
          <span className="text-sm font-semibold text-zinc-200">Company CRM</span>
        </div>
        <span className="text-xs text-zinc-600">{companies.length} companies</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800">
              {['Company', 'Lane', 'Fit', 'Status', 'Hiring'].map(h => (
                <th key={h} className="text-left text-zinc-500 font-semibold uppercase tracking-wide px-4 py-2.5 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {companies.map(c => {
              const fit = c.fit_score
              const fitColor = fit >= 8 ? 'text-emerald-400' : fit >= 6 ? 'text-amber-400' : 'text-zinc-400'
              const isSelected = c.name === currentCompany

              return (
                <tr key={c.id}
                  onClick={() => onSelect(c.name)}
                  className={`border-b border-zinc-800/50 cursor-pointer transition-colors hover:bg-zinc-800/30
                    ${isSelected ? 'bg-violet-500/8 border-l-2 border-l-violet-500' : ''}`}
                >
                  <td className="px-4 py-2.5 font-medium text-zinc-200">{c.name}</td>
                  <td className="px-4 py-2.5 text-zinc-500">{c.lane}</td>
                  <td className={`px-4 py-2.5 font-bold ${fitColor}`}>{fit > 0 ? `${fit}/10` : '—'}</td>
                  <td className={`px-4 py-2.5 font-medium ${STATUS_COLOR[c.status] ?? 'text-zinc-500'}`}>
                    {c.status.replace('_', ' ')}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500">{c.hiring_status ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
