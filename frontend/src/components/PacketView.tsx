import { useState } from 'react'
import type { OSPacket, OSProblem, OSPerson } from '../hooks/useOS'

interface Props {
  company: string
  packet: OSPacket
  problems: OSProblem[]
  people: OSPerson[]
}

function Score({ value, label = '' }: { value: number; label?: string }) {
  const style = value >= 8 ? 'score-good' : value >= 6 ? 'score-warn' : 'score-bad'
  return <span className={`packet-score ${style}`}>{label}{value}/10</span>
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
  const statusStyle = packet.crm_status === 'prepared' ? 'is-prepared' : packet.crm_status === 'needs_review' ? 'is-review' : ''

  return (
    <section className="packet-view">
      <header className="packet-view-header">
        <div>
          <p>Selected packet</p>
          <h2>{company}</h2>
          <span className={`packet-status ${statusStyle}`}>{packet.crm_status?.replace('_', ' ') || 'draft'}</span>
        </div>
        <Score value={packet.qa_score ?? 0} label="QA " />
      </header>

      <nav role="tablist" aria-label="Packet sections" className="packet-tabs">
        {(['overview', 'note', 'drafts'] as const).map(item => (
          <button key={item} role="tab" id={`tab-${item}`} aria-selected={tab === item}
            onClick={() => setTab(item)}
            className={`packet-tab ${tab === item ? 'is-active' : ''}`}>
            {item === 'note' ? 'Technical note' : item}
          </button>
        ))}
      </nav>

      <div role="tabpanel" aria-labelledby={`tab-${tab}`} className="packet-tabpanel">
        {tab === 'overview' && (
          <div className="space-y-7">
            {packet.company_fit && (
              <section>
                <p className="packet-section-label">Company fit</p>
                <p className="packet-body-copy mt-2">{packet.company_fit}</p>
              </section>
            )}

            {packet.adjacent_proof && (
              <section className="packet-proof">
                <p className="packet-section-label">Adjacent proof</p>
                <p>{packet.adjacent_proof}</p>
              </section>
            )}

            {problems.length > 0 && (
              <section>
                <p className="packet-section-label">Open problems / {problems.length}</p>
                <div className="space-y-3 mt-3">
                  {problems.map(problem => (
                    <article key={problem.id} className="packet-record">
                      <div className="flex items-start justify-between gap-3">
                        <h3>{problem.title}</h3>
                        <Score value={problem.relevance_score} />
                      </div>
                      <p>{problem.description}</p>
                      {sourceUrls(problem.source_urls).length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {sourceUrls(problem.source_urls).map((url, index) => (
                            <a key={`${url}-${index}`} href={url} target="_blank" rel="noopener noreferrer"
                              className="packet-link">
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
                <p className="packet-section-label">People map / {people.length}</p>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 mt-3">
                  {people.map(person => (
                    <article key={person.id} className="packet-person">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3>{person.name}</h3>
                          <p>{person.role}</p>
                        </div>
                        <Score value={person.relevance_score} />
                      </div>
                      <p className="packet-person-reason">{person.relevance_reason}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        <span className="packet-mini-badge">{person.proximity}</span>
                        {person.linkedin_url && <a href={person.linkedin_url} target="_blank" rel="noopener noreferrer" className="packet-link">LinkedIn</a>}
                        {person.github_url && <a href={person.github_url} target="_blank" rel="noopener noreferrer" className="packet-link">GitHub</a>}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {qaFlags.length > 0 && (
              <section>
                <p className="packet-section-label">QA flags / {qaFlags.length}</p>
                <div className="space-y-2 mt-3">
                  {qaFlags.map((flag, index) => <p key={index} className="packet-qa-flag">{flag}</p>)}
                </div>
              </section>
            )}
          </div>
        )}

        {tab === 'note' && (
          <pre className="packet-note">
            {packet.technical_note || 'No technical note generated yet.'}
          </pre>
        )}

        {tab === 'drafts' && (
          <div className="space-y-5">
            {Object.entries(drafts).filter(([, text]) => text.trim()).map(([variant, text]) => {
              const words = text.split(/\s+/).filter(Boolean).length
              const over = words > 200
              return (
                <section key={variant}>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <p className="packet-section-label">{variant.replace('_', ' ')}</p>
                    <span className={`packet-score ${over ? 'score-bad' : ''}`}>{words}w</span>
                  </div>
                  <pre className="packet-draft">{text}</pre>
                  {over && <p className="mt-2 text-xs text-[#a6382d]">Over 200 words. Edit before sending manually.</p>}
                </section>
              )
            })}
            {Object.keys(drafts).length === 0 && <p className="text-sm text-[#8a867d]">No drafts generated yet.</p>}
          </div>
        )}
      </div>
    </section>
  )
}
