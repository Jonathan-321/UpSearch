import { useState } from 'react'
import type { OSPacket, OSProblem, OSPerson } from '../hooks/useOS'

interface Props {
  company: string
  packet: OSPacket
  problems: OSProblem[]
  people: OSPerson[]
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 7 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : score >= 5 ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
              : 'bg-red-500/15 text-red-400 border-red-500/30'
  return <span className={`text-xs font-bold px-2 py-0.5 rounded-md border ${color}`}>{score}/10</span>
}

function ProximityBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    founder:        'bg-violet-500/15 text-violet-400 border-violet-500/30',
    researcher:     'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
    engineer:       'bg-sky-500/15 text-sky-400 border-sky-500/30',
    FDE:            'bg-teal-500/15 text-teal-400 border-teal-500/30',
    hiring_manager: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    recruiter:      'bg-zinc-500/15 text-zinc-400 border-zinc-700',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${colors[type] ?? colors['engineer']}`}>
      {type}
    </span>
  )
}

export default function PacketView({ company, packet, problems, people }: Props) {
  const [activeTab, setActiveTab] = useState<'overview' | 'note' | 'drafts'>('overview')

  let drafts: Record<string, string> = {}
  try { drafts = JSON.parse(packet.outreach_drafts ?? '{}') } catch { /* empty */ }

  let qaFlags: string[] = []
  try { qaFlags = JSON.parse(packet.qa_flags ?? '[]') } catch { /* empty */ }

  const tabs = ['overview', 'note', 'drafts'] as const

  return (
    <section className="card overflow-hidden animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
        <div>
          <p className="text-sm font-bold text-zinc-100">{company}</p>
          <p className="text-xs text-zinc-500 mt-0.5">{packet.crm_status?.replace('_', ' ')}</p>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={packet.qa_score ?? 0} />
          {qaFlags.length > 0 && (
            <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md">
              {qaFlags.length} flag{qaFlags.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800">
        {tabs.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-5 py-2.5 text-xs font-semibold capitalize transition-colors
              ${activeTab === tab ? 'text-violet-400 border-b-2 border-violet-500' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            {tab === 'note' ? 'Technical Note' : tab}
          </button>
        ))}
      </div>

      <div className="p-5 space-y-4 max-h-[520px] overflow-y-auto">
        {/* Overview tab */}
        {activeTab === 'overview' && (
          <>
            {packet.company_fit && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-1">Company Fit</p>
                <p className="text-xs text-zinc-300 leading-relaxed">{packet.company_fit}</p>
              </div>
            )}

            {packet.adjacent_proof && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-1">Adjacent Proof</p>
                <p className="text-xs text-zinc-300 leading-relaxed">{packet.adjacent_proof}</p>
              </div>
            )}

            {problems.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Open Problems</p>
                <div className="space-y-2">
                  {problems.map(p => (
                    <div key={p.id} className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-800">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-zinc-200">{p.title}</span>
                        <ScoreBadge score={p.relevance_score} />
                      </div>
                      <p className="text-xs text-zinc-400 leading-relaxed">{p.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {people.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">People Map</p>
                <div className="space-y-2">
                  {people.map(p => (
                    <div key={p.id} className="flex items-start justify-between gap-3 py-2 border-b border-zinc-800 last:border-0">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-zinc-200">{p.name}</span>
                          <ProximityBadge type={p.proximity} />
                        </div>
                        <p className="text-xs text-zinc-500 mt-0.5">{p.role}</p>
                        {p.relevance_reason && (
                          <p className="text-xs text-zinc-600 mt-0.5 italic">{p.relevance_reason}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {p.linkedin_url && (
                          <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                            LI →
                          </a>
                        )}
                        {p.github_url && (
                          <a href={p.github_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-zinc-400 hover:text-zinc-300 transition-colors">
                            GH →
                          </a>
                        )}
                        <ScoreBadge score={p.relevance_score} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {qaFlags.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">QA Flags</p>
                <div className="space-y-1">
                  {qaFlags.map((f, i) => (
                    <p key={i} className="text-xs text-amber-400 bg-amber-500/8 border border-amber-500/20 px-3 py-1.5 rounded-md">
                      ! {f}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Technical note tab */}
        {activeTab === 'note' && (
          <pre className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-sans">
            {packet.technical_note || 'No technical note generated yet.'}
          </pre>
        )}

        {/* Drafts tab */}
        {activeTab === 'drafts' && (
          <div className="space-y-4">
            {Object.entries(drafts).filter(([, v]) => v.trim()).map(([variant, text]) => (
              <div key={variant}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">{variant}</span>
                  <span className="text-xs text-zinc-600">{text.split(/\s+/).length} words</span>
                </div>
                <pre className="bg-zinc-800/40 border border-zinc-800 rounded-lg p-4 text-xs text-zinc-300
                                leading-relaxed whitespace-pre-wrap font-sans">
                  {text}
                </pre>
              </div>
            ))}
            {Object.keys(drafts).length === 0 && (
              <p className="text-xs text-zinc-600 italic">No drafts generated yet.</p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
