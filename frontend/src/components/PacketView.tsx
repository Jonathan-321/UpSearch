import { useState } from 'react'
import type { OSPacket, OSProblem, OSPerson } from '../hooks/useOS'

interface Props {
  company: string
  packet: OSPacket
  problems: OSProblem[]
  people: OSPerson[]
}

const PROXIMITY_STYLE: Record<string, string> = {
  founder:        'text-violet-400 bg-violet-500/10 border-violet-500/25',
  researcher:     'text-indigo-400 bg-indigo-500/10 border-indigo-500/25',
  engineer:       'text-sky-400 bg-sky-500/10 border-sky-500/25',
  FDE:            'text-teal-400 bg-teal-500/10 border-teal-500/25',
  hiring_manager: 'text-orange-400 bg-orange-500/10 border-orange-500/25',
  recruiter:      'text-zinc-400 bg-zinc-800/60 border-zinc-700',
}

function RelevanceBar({ score }: { score: number }) {
  const color = score >= 8 ? 'bg-emerald-500' : score >= 6 ? 'bg-amber-500' : 'bg-red-400'
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex gap-px">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className={`h-1 w-1.5 rounded-sm ${i < score ? color : 'bg-zinc-800'}`}/>
        ))}
      </div>
      <span className="text-xs tabular-nums text-zinc-500">{score}/10</span>
    </div>
  )
}

function QABadge({ score }: { score: number }) {
  const style = score >= 7
    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25'
    : score >= 5
    ? 'text-amber-400 bg-amber-500/10 border-amber-500/25'
    : 'text-red-400 bg-red-500/10 border-red-500/25'
  return (
    <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${style}`}>
      QA {score}/10
    </span>
  )
}

export default function PacketView({ company, packet, problems, people }: Props) {
  const [tab, setTab] = useState<'overview' | 'note' | 'drafts'>('overview')

  let drafts: Record<string, string> = {}
  try { drafts = JSON.parse(packet.outreach_drafts ?? '{}') } catch { /**/ }

  let qaFlags: string[] = []
  try { qaFlags = JSON.parse(packet.qa_flags ?? '[]') } catch { /**/ }

  const statusStyle: Record<string, string> = {
    prepared:     'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    needs_review: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  }

  const TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'note',     label: 'Technical Note' },
    { key: 'drafts',   label: 'Drafts' },
  ] as const

  return (
    <section className="card overflow-hidden animate-fade-in-up flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.05]">
        <div>
          <h2 className="text-base font-bold text-zinc-100">{company}</h2>
          <span className={`mt-0.5 inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full border ${statusStyle[packet.crm_status ?? ''] ?? 'text-zinc-500 bg-zinc-800/50 border-zinc-700'}`}>
            {packet.crm_status?.replace('_', ' ')}
          </span>
        </div>
        <QABadge score={packet.qa_score ?? 0}/>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/[0.05] shrink-0">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`relative px-5 py-3 text-xs font-semibold transition-colors
              ${tab === t.key ? 'text-violet-400' : 'text-zinc-600 hover:text-zinc-400'}`}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-gradient-to-r from-violet-600 to-indigo-500 rounded-full"/>
            )}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* ── Overview tab ────────────────────────────── */}
        {tab === 'overview' && (
          <>
            {packet.company_fit && (
              <div className="space-y-1.5">
                <p className="section-label">Company Fit</p>
                <p className="text-xs text-zinc-300 leading-relaxed">{packet.company_fit}</p>
              </div>
            )}

            {packet.adjacent_proof && (
              <div className="space-y-1.5">
                <p className="section-label">Adjacent Proof</p>
                <p className="text-xs text-zinc-400 leading-relaxed italic border-l-2 border-violet-600/40 pl-3">
                  {packet.adjacent_proof}
                </p>
              </div>
            )}

            {problems.length > 0 && (
              <div className="space-y-2">
                <p className="section-label">Open Problems ({problems.length})</p>
                {problems.map(p => (
                  <div key={p.id} className="rounded-xl bg-white/[0.02] border border-white/[0.05] p-4 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs font-semibold text-zinc-200 leading-snug flex-1">{p.title}</p>
                      <RelevanceBar score={p.relevance_score}/>
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed">{p.description}</p>
                  </div>
                ))}
              </div>
            )}

            {people.length > 0 && (
              <div className="space-y-2">
                <p className="section-label">People Map ({people.length})</p>
                {people.map(p => (
                  <div key={p.id} className="flex items-start gap-3 rounded-xl bg-white/[0.02] border border-white/[0.05] p-3.5">
                    {/* Avatar */}
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-600/30 to-indigo-600/30
                                    border border-violet-500/20 flex items-center justify-center shrink-0">
                      <span className="text-xs font-bold text-violet-300">
                        {p.name.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-zinc-200">{p.name}</span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${PROXIMITY_STYLE[p.proximity] ?? PROXIMITY_STYLE['engineer']}`}>
                          {p.proximity}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500">{p.role}</p>
                      {p.relevance_reason && (
                        <p className="text-xs text-zinc-700 italic">{p.relevance_reason}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1.5">
                        {p.linkedin_url && (
                          <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/15
                                       border border-blue-500/20 px-2 py-0.5 rounded-md transition-colors">
                            LinkedIn →
                          </a>
                        )}
                        {p.github_url && (
                          <a href={p.github_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-zinc-400 hover:text-zinc-300 bg-zinc-800/60 hover:bg-zinc-800
                                       border border-zinc-700 px-2 py-0.5 rounded-md transition-colors">
                            GitHub →
                          </a>
                        )}
                        <RelevanceBar score={p.relevance_score}/>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {qaFlags.length > 0 && (
              <div className="space-y-2">
                <p className="section-label">QA Flags ({qaFlags.length})</p>
                <div className="space-y-1.5">
                  {qaFlags.map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-amber-400
                                            bg-amber-500/5 border border-amber-500/15 rounded-lg px-3 py-2">
                      <span className="font-bold shrink-0 mt-px">!</span>
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Technical Note tab ──────────────────────── */}
        {tab === 'note' && (
          <div className="rounded-xl bg-white/[0.02] border border-white/[0.04] p-4">
            <pre className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono">
              {packet.technical_note || 'No technical note generated yet.'}
            </pre>
          </div>
        )}

        {/* ── Drafts tab ──────────────────────────────── */}
        {tab === 'drafts' && (
          <div className="space-y-5">
            {Object.entries(drafts).filter(([, v]) => v.trim()).map(([variant, text]) => {
              const wc = text.split(/\s+/).filter(Boolean).length
              return (
                <div key={variant} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="section-label">{variant.replace('_', ' ')}</span>
                    <span className={`text-xs tabular-nums font-mono px-2 py-0.5 rounded border
                      ${wc > 200 ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-zinc-500 bg-zinc-800/50 border-zinc-700'}`}>
                      {wc}w
                    </span>
                  </div>
                  <pre className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono
                                  bg-white/[0.02] border border-white/[0.04] rounded-xl p-4">
                    {text}
                  </pre>
                </div>
              )
            })}
            {Object.keys(drafts).length === 0 && (
              <p className="text-xs text-zinc-700 italic">No drafts generated yet.</p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
