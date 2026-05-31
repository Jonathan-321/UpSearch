import type { OSCompany } from '../hooks/useOS'

interface Props {
  companies: OSCompany[]
  currentCompany: string
  onSelect: (name: string) => void
}

const STATUS: Record<string, { label: string; style: string }> = {
  packet_ready: { label: 'Packet ready', style: 'badge-success' },
  needs_review: { label: 'Needs review', style: 'badge-warning' },
  researched: { label: 'Researched', style: '' },
  sourced: { label: 'Sourced', style: '' },
}

const LANES: Record<string, string> = {
  ai_infra: 'AI Infra',
  inference: 'Inference',
  agentic: 'Agentic',
  dev_tools: 'Dev Tools',
  data: 'Data',
  robotics: 'Robotics',
}

function FitScore({ score }: { score: number }) {
  const color = score >= 8 ? 'text-emerald-400' : score >= 6 ? 'text-amber-400' : 'text-red-400'
  return <span className={`font-mono text-sm font-semibold ${color}`}>{score > 0 ? `${score}/10` : '--'}</span>
}

export default function CRMTable({ companies, currentCompany, onSelect }: Props) {
  return (
    <section className="panel overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-border">
        <div>
          <p className="workspace-label">Research Desk</p>
          <h2 className="text-base font-semibold text-text-1 mt-1">Company CRM</h2>
        </div>
        <span className="font-mono text-xs text-text-3">{companies.length}</span>
      </div>

      {companies.length === 0 ? (
        <div className="p-8 text-center">
          <p className="text-sm text-text-2">No companies tracked yet.</p>
          <p className="text-xs text-text-3 mt-1">Build a packet to start the desk.</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {companies.map(company => {
            const selected = company.name === currentCompany
            const status = STATUS[company.status] ?? STATUS.sourced
            return (
              <button key={company.id} type="button" onClick={() => onSelect(company.name)}
                aria-pressed={selected}
                className={`w-full text-left p-4 transition-colors border-l-2 ${
                  selected ? 'border-l-accent bg-amber-500/[0.06]' : 'border-l-transparent hover:bg-surface-2'
                }`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-text-1 truncate">{company.name}</p>
                    <p className="text-xs text-text-3 mt-1">{LANES[company.lane] ?? company.lane}</p>
                  </div>
                  <FitScore score={company.fit_score} />
                </div>
                <div className="flex items-center justify-between gap-2 mt-3">
                  <span className={`badge ${status.style}`}>{status.label}</span>
                  <span className="text-[10px] uppercase tracking-wider text-text-3">{company.hiring_status}</span>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
