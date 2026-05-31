import { useState } from 'react'
import type { OSPacket, OSProblem, OSPerson } from '../hooks/useOS'

interface Props {
  company: string
  packet: OSPacket
  problems: OSProblem[]
  people: OSPerson[]
}

function Score({ value, label = '' }: { value: number; label?: string }) {
  const style = value >= 8 ? 'badge-success' : value >= 6 ? 'badge-warning' : 'badge-error'
  return <span className={`badge ${style} font-mono`}>{label}{value}/10</span>
}

function parseJson<T>(value: string | undefined, fallback: T): T {
  try { return JSON.parse(value ?? '') as T } catch { return fallback }
}

function sourceUrls(value: string): string[] {
  const parsed = parseJson<unknown>(value, [])
  if (Array.isArray(parsed)) return parsed.filter((item): item is string => typeof item === 'string')
  return value ? [value] : []
}

export default function PacketView({ company, packet, problems, people }: Props) {
  const [tab, setTab] = useState<'overview' | 'note' | 'drafts'>('overview')
  const drafts = parseJson<Record<string, string>>(packet.outreach_drafts, {})
  const qaFlags = parseJson<string[]>(packet.qa_flags, [])
  const statusStyle = packet.crm_status === 'prepared' ? 'badge-success' : packet.crm_status === 'needs_review' ? 'badge-warning' : ''

  return (
    <section className="panel overflow-hidden min-h-[520px]">
      <header className="px-5 sm:px-6 py-5 border-b border-border flex items-start justify-between gap-4">
        <div>
          <p className="workspace-label">Selected Packet</p>
          <h2 className="font-serif text-3xl text-text-1 mt-1">{company}</h2>
          <span className={`badge ${statusStyle} mt-2`}>{packet.crm_status?.replace('_', ' ') || 'draft'}</span>
        </div>
        <Score value={packet.qa_score ?? 0} label="QA " />
      </header>

      <nav className="flex gap-5 px-5 sm:px-6 border-b border-border" aria-label="Packet sections">
        {(['overview', 'note', 'drafts'] as const).map(item => (
          <button key={item} onClick={() => setTab(item)}
            className={`tab-btn capitalize ${tab === item ? 'tab-btn-active' : ''}`}>
            {item === 'note' ? 'Technical note' : item}
          </button>
        ))}
      </nav>

      <div className="p-5 sm:p-6">
        {tab === 'overview' && (
          <div className="space-y-7">
            {packet.company_fit && (
              <section>
                <p className="section-head">Company fit</p>
                <p className="text-body text-text-1 mt-2">{packet.company_fit}</p>
              </section>
            )}

            {packet.adjacent_proof && (
              <section className="border-l-2 border-amber-500/60 pl-4">
                <p className="section-head">Adjacent proof</p>
                <p className="text-sm text-text-2 mt-2 leading-relaxed">{packet.adjacent_proof}</p>
              </section>
            )}

            {problems.length > 0 && (
              <section>
                <p className="section-head">Open problems / {problems.length}</p>
                <div className="space-y-3 mt-3">
                  {problems.map(problem => (
                    <article key={problem.id} className="panel panel-raised p-4">
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-sm font-semibold text-text-1">{problem.title}</h3>
                        <Score value={problem.relevance_score} />
                      </div>
                      <p className="text-sm text-text-2 leading-relaxed mt-2">{problem.description}</p>
                      {sourceUrls(problem.source_urls).length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {sourceUrls(problem.source_urls).map((url, index) => (
                            <a key={`${url}-${index}`} href={url} target="_blank" rel="noopener noreferrer"
                              className="text-xs text-amber-400 hover:text-amber-300 underline underline-offset-4">
                              Evidence {index + 1}
                            </a>
                          ))}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )}

            {people.length > 0 && (
              <section>
                <p className="section-head">People map / {people.length}</p>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 mt-3">
                  {people.map(person => (
                    <article key={person.id} className="panel panel-raised p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold text-text-1">{person.name}</h3>
                          <p className="text-xs text-text-2 mt-1">{person.role}</p>
                        </div>
                        <Score value={person.relevance_score} />
                      </div>
                      <p className="text-xs text-text-3 leading-relaxed mt-3">{person.relevance_reason}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        <span className="badge badge-accent">{person.proximity}</span>
                        {person.linkedin_url && <a href={person.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-amber-400 hover:text-amber-300">LinkedIn</a>}
                        {person.github_url && <a href={person.github_url} target="_blank" rel="noopener noreferrer" className="text-xs text-amber-400 hover:text-amber-300">GitHub</a>}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {qaFlags.length > 0 && (
              <section>
                <p className="section-head">QA flags / {qaFlags.length}</p>
                <div className="space-y-2 mt-3">
                  {qaFlags.map((flag, index) => <p key={index} className="text-sm text-amber-300 bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">! {flag}</p>)}
                </div>
              </section>
            )}
          </div>
        )}

        {tab === 'note' && (
          <pre className="font-mono text-sm text-text-2 leading-relaxed whitespace-pre-wrap panel panel-raised p-5">
            {packet.technical_note || 'No technical note generated yet.'}
          </pre>
        )}

        {tab === 'drafts' && (
          <div className="space-y-5">
            {Object.entries(drafts).filter(([, text]) => text.trim()).map(([variant, text]) => (
              <section key={variant}>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <p className="section-head">{variant.replace('_', ' ')}</p>
                  <span className="badge font-mono">{text.split(/\s+/).filter(Boolean).length}w</span>
                </div>
                <pre className="font-mono text-sm text-text-2 leading-relaxed whitespace-pre-wrap panel panel-raised p-4">{text}</pre>
              </section>
            ))}
            {Object.keys(drafts).length === 0 && <p className="text-sm text-text-3">No drafts generated yet.</p>}
          </div>
        )}
      </div>
    </section>
  )
}
