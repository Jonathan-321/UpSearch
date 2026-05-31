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
    <section className="studio-desk-card">
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-[#dedbd2]">
        <div>
          <p className="studio-kicker">Research desk</p>
          <h2 className="mt-1 text-base font-semibold text-[#161616]">Company CRM</h2>
        </div>
        <span className="font-mono text-xs text-[#8a867d]">{companies.length}</span>
      </div>

      {companies.length === 0 ? (
        <div className="p-8 text-center">
          <p className="text-sm text-[#565248]">No companies tracked yet.</p>
          <p className="mt-1 text-xs text-[#8a867d]">Build a packet to start the desk.</p>
        </div>
      ) : (
        <div className="divide-y divide-[#dedbd2] lg:max-h-[58vh] lg:overflow-y-auto">
          {companies.map(company => {
            const selected = company.name === currentCompany
            const status = STATUS[company.status] ?? STATUS.sourced
            return (
              <button key={company.id} type="button" onClick={() => onSelect(company.name)}
                aria-pressed={selected}
                aria-label={`Select ${company.name}`}
                className={`w-full text-left p-4 transition-colors border-l-2 ${
                  selected ? 'border-l-[#f26a21] bg-[#f26a21]/[0.07]' : 'border-l-transparent hover:bg-[#f2f0ea]'
                }`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#161616]">{company.name}</p>
                    <p className="mt-1 text-xs text-[#8a867d]">{LANES[company.lane] ?? company.lane}</p>
                  </div>
                  <FitScore score={company.fit_score} />
                </div>
                <div className="flex items-center justify-between gap-2 mt-3">
                  <span className={`badge ${status.style}`}>{status.label}</span>
                  {company.hiring_status && (
                    <span className="text-[10px] uppercase tracking-wider text-text-3">{company.hiring_status}</span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
