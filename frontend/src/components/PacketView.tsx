import { useState } from 'react'
import { evidenceLabel } from '../types'
import type { OSCheckup, OSCompany, OSPacket, OSProblem, OSPerson, OSQAResult, OSSourceMethod, OSTraceEvent } from '../hooks/useOS'

interface Props {
  company: string
  packet: OSPacket
  problems: OSProblem[]
  people: OSPerson[]
  checkup?: OSCheckup | null
  qa?: OSQAResult | null
  /** Company row carrying identity_status/identity_reason; only read in the blocked state. */
  companyRecord?: OSCompany | null
  /** Existing rebuild flow (Packet Studio buildPacket); shown only when identity is blocked. */
  onRebuild?: () => void
  rebuildRunning?: boolean
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

function EvidenceLink({ url }: { url: string }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="packet-link" title={url}>
      {evidenceLabel(url)}
    </a>
  )
}

function isVerified(person: OSPerson): boolean {
  return person.verification_status === 'verified'
}

function CheckupScore({ value }: { value: number }) {
  const style = value >= 8 ? 'score-good' : value >= 6 ? 'score-warn' : 'score-bad'
  return <span className={`packet-score ${style}`}>Checkup {value}/10</span>
}

function SourceMethod({ method }: { method: OSSourceMethod }) {
  return (
    <article className="checkup-method">
      <h3>{method.title}</h3>
      <ol>
        {method.steps.map((step, index) => <li key={`${method.title}-${index}`}>{step}</li>)}
      </ol>
      <div className="checkup-tool-grid">
        <div>
          <p className="packet-section-label">Current tools</p>
          <div className="checkup-chip-row">
            {method.current_tools.map(tool => <span key={tool}>{tool}</span>)}
          </div>
        </div>
        <div>
          <p className="packet-section-label">Next tools</p>
          <div className="checkup-chip-row">
            {method.planned_tools.map(tool => <span key={tool}>{tool}</span>)}
          </div>
        </div>
      </div>
    </article>
  )
}

function TraceRow({ event }: { event: OSTraceEvent }) {
  if (event.event_type === 'handoff') {
    return (
      <div className="checkup-trace-row">
        <span>handoff</span>
        <strong>{event.from_agent}{' -> '}{event.to_agent}</strong>
        <p>{event.reason}</p>
      </div>
    )
  }

  return (
    <div className="checkup-trace-row">
      <span>step</span>
      <strong>{event.agent}</strong>
      <p>{event.output_summary || event.role}</p>
    </div>
  )
}

export default function PacketView({ company, packet, problems, people, checkup, qa, companyRecord, onRebuild, rebuildRunning }: Props) {
  const [tab, setTab] = useState<'overview' | 'note' | 'drafts' | 'checkup'>('overview')
  const drafts = parseJson<Record<string, string>>(packet.outreach_drafts, {})
  const qaFlags = parseJson<string[]>(packet.qa_flags, [])
  // Verified people first; relevance order within each group.
  const sortedPeople = [...people].sort((a, b) =>
    Number(isVerified(b)) - Number(isVerified(a)) || (b.relevance_score ?? 0) - (a.relevance_score ?? 0))
  const verifiedCount = people.filter(isVerified).length
  const statusStyle = packet.crm_status === 'prepared' ? 'is-prepared' : packet.crm_status === 'needs_review' ? 'is-review' : ''
  // Identity gate failed: every later stage was skipped, so one status card owns
  // the page and the symptom-level warnings (empty problems/people, checkup box,
  // score chips, QA flag echoes of the same reason) are suppressed.
  const identityBlocked = packet.crm_status === 'identity_blocked' || checkup?.failure_category === 'identity_blocked'
  const identityReason = companyRecord?.identity_reason
    || checkup?.suggested_fix
    || 'Company identity could not be verified against a primary source.'
  // The backend may end the reason with "Closest fetched candidate: <domain>." —
  // the nearest real site it fetched, which usually exposes a typo in the name.
  const closestCandidate = identityBlocked
    ? identityReason.match(/Closest fetched candidate:\s*(\S+?)\.?\s*$/)?.[1] ?? null
    : null

  return (
    <section className="packet-view">
      <header className="packet-view-header">
        <div>
          <p>Selected packet</p>
          <h2>{company}</h2>
          <span className={`packet-status ${statusStyle}`}>{packet.crm_status?.replace('_', ' ') || 'draft'}</span>
        </div>
        <div className="packet-header-scores">
          {!identityBlocked && checkup && <CheckupScore value={checkup.overall_score ?? 0} />}
          {!identityBlocked && <Score value={packet.qa_score ?? 0} label="QA " />}
          {qa?.model_route?.degraded_mode && (
            <span className="badge badge-warning" title={qa.model_route.reason ?? undefined}>
              QA degraded — not strong-model verified
            </span>
          )}
        </div>
      </header>

      {identityBlocked && (
        <div className="packet-identity-card">
          <h3>Identity blocked</h3>
          <p className="packet-identity-reason">{identityReason}</p>
          {closestCandidate && (
            <p className="packet-identity-hint">Did you mean <strong>{closestCandidate}</strong>?</p>
          )}
          {onRebuild && (
            <button
              type="button"
              className="studio-primary-action mt-4"
              onClick={onRebuild}
              disabled={rebuildRunning}
            >
              {rebuildRunning ? 'Rebuilding packet...' : 'Rebuild packet'}
            </button>
          )}
        </div>
      )}

      {!identityBlocked && checkup && checkup.failure_category !== 'none' && (
        <div className="packet-reliability-warning">
          <strong>Review required: {checkup.failure_category.replace(/_/g, ' ')}</strong>
          <p>{checkup.suggested_fix}</p>
        </div>
      )}

      <nav role="tablist" aria-label="Packet sections" className="packet-tabs">
        {(['overview', 'note', 'drafts', 'checkup'] as const).map(item => (
          <button key={item} role="tab" id={`tab-${item}`} aria-selected={tab === item}
            onClick={() => setTab(item)}
            className={`packet-tab ${tab === item ? 'is-active' : ''}`}>
            {item === 'note' ? 'Technical note' : item === 'checkup' ? 'Run checkup' : item}
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
                            <EvidenceLink key={`${url}-${index}`} url={url} />
                          ))}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )}

            {problems.length === 0 && !identityBlocked && (
              <section className="packet-empty-state">
                <p className="packet-section-label">Open problems / 0</p>
                <h3>No source-backed problem is attached.</h3>
                <p>Rerun problem discovery or add company blog, docs, HN, Reddit, GitHub, or paper sources before using this packet.</p>
              </section>
            )}

            {people.length > 0 && (
              <section>
                <p className="packet-section-label">
                  People map / {people.length} · {verifiedCount} verified
                </p>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 mt-3">
                  {sortedPeople.map(person => (
                    <article key={person.id} className="packet-person">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3>{person.name}</h3>
                          <p>{person.role}</p>
                        </div>
                        {isVerified(person) ? (
                          <Score value={person.relevance_score} />
                        ) : (
                          <span
                            className="packet-mini-badge"
                            title={person.verification_reason
                              || 'Not verified against a primary source. Excluded from outreach until a source confirms this person.'}>
                            unverified
                          </span>
                        )}
                      </div>
                      <p className="packet-person-reason">{person.relevance_reason}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        <span className="packet-mini-badge">{person.proximity}</span>
                        {person.linkedin_url && <a href={person.linkedin_url} target="_blank" rel="noopener noreferrer" className="packet-link">LinkedIn</a>}
                        {person.github_url && <a href={person.github_url} target="_blank" rel="noopener noreferrer" className="packet-link">GitHub</a>}
                        {person.twitter_url && <a href={person.twitter_url} target="_blank" rel="noopener noreferrer" className="packet-link">X</a>}
                        {person.source_url && <EvidenceLink url={person.source_url} />}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {people.length === 0 && !identityBlocked && (
              <section className="packet-empty-state">
                <p className="packet-section-label">People map / 0</p>
                <h3>No verified person is attached.</h3>
                <p>Find a founder, engineer, author, recruiter, or researcher with a public profile before drafting outreach.</p>
              </section>
            )}

            {identityBlocked && (
              <p className="packet-skip-note">Later stages were skipped until identity verifies.</p>
            )}

            {qaFlags.length > 0 && !identityBlocked && (
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

        {tab === 'checkup' && (
          <div className="checkup-view">
            {checkup ? (
              <>
                <section className="checkup-summary">
                  <div>
                    <p className="packet-section-label">Packet reliability</p>
                    <h3>{checkup.status?.replace('_', ' ')}</h3>
                    <p>{checkup.suggested_fix}</p>
                  </div>
                  <CheckupScore value={checkup.overall_score ?? 0} />
                </section>

                <section className="checkup-metrics">
                  {checkup.metrics.map(metric => (
                    <article key={metric.name}>
                      <div className="flex items-center justify-between gap-3">
                        <h3>{metric.name}</h3>
                        <Score value={metric.score} />
                      </div>
                      <p>{metric.detail}</p>
                    </article>
                  ))}
                </section>

                <section>
                  <p className="packet-section-label">Trace health</p>
                  <div className="checkup-trace-health">
                    <span>{checkup.trace.agent_steps} agent steps</span>
                    <span>{checkup.trace.handoffs} handoffs</span>
                    <span>{checkup.failure_category}</span>
                  </div>
                  {checkup.trace.missing_agents.length > 0 && (
                    <p className="checkup-warning">Missing trace agents: {checkup.trace.missing_agents.join(', ')}</p>
                  )}
                  <div className="checkup-trace-list">
                    {checkup.trace.events.slice(0, 12).map((event, index) => (
                      <TraceRow key={`${event.event_type}-${event.agent || event.from_agent}-${index}`} event={event} />
                    ))}
                  </div>
                </section>

                <section className="checkup-method-grid">
                  {checkup.source_methods.problem_discovery && (
                    <SourceMethod method={checkup.source_methods.problem_discovery} />
                  )}
                  {checkup.source_methods.people_sourcing && (
                    <SourceMethod method={checkup.source_methods.people_sourcing} />
                  )}
                </section>
              </>
            ) : (
              <section className="checkup-summary">
                <div>
                  <p className="packet-section-label">Packet reliability</p>
                  <h3>No checkup yet</h3>
                  <p>Run a packet build to generate trace events, quality metrics, and a report.</p>
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
