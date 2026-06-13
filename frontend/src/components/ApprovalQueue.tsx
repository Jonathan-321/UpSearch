import { useMemo, useState } from 'react'
import { evidenceLabel } from '../types'
import type { OSMessage, OSPerson } from '../hooks/useOS'

interface Props {
  messages: OSMessage[]
  /** People from the currently loaded packet payload; used only for the WHY line. */
  packetPeople?: OSPerson[]
  /** Company the loaded packet belongs to, so people are never matched across companies. */
  packetCompany?: string
  onApprove: (id: number) => Promise<void>
  onReject: (id: number, notes?: string) => Promise<void>
  onRecordDelivery: (
    id: number,
    status: 'opened' | 'sent' | 'delivered' | 'failed' | 'unknown',
    errorMessage?: string,
  ) => Promise<void>
  onScheduleFollowUp: (id: number, dueDate: string, notes?: string) => Promise<void>
  onUpdateFollowUp: (id: number, status: 'completed' | 'skipped', notes?: string) => Promise<void>
}

/**
 * Recipient verification reaches the message payload only as a QA flag string
 * ("Unverified recipient: <name> (status=unverified)"); there is no
 * message-level verification field yet, so match the flag text loosely.
 */
function hasUnverifiedRecipient(message: OSMessage): boolean {
  return (message.qa_flags ?? []).some(flag => /unverified recipient/i.test(flag))
}

/** Worth a human decision now: passes server safety gates and is addressed to a verified recipient. */
function isReadyForDecision(message: OSMessage): boolean {
  return message.actionable !== false && !hasUnverifiedRecipient(message)
}

function sourceLinks(message: OSMessage): string[] {
  const urls = [
    message.source_url,
    message.linkedin_url,
    message.github_url,
    ...(message.problem_source_urls ?? []),
  ].filter(Boolean) as string[]
  return Array.from(new Set(urls)).slice(0, 3)
}

function handoffCopy(message: OSMessage): string {
  if (message.handoff_mode === 'prefill_compose') {
    return 'Open a prepared Gmail compose window. Review the recipient and hit send yourself.'
  }
  if (message.handoff_mode === 'copy_then_open') {
    return `Copy the exact draft and open ${message.platform || 'the platform'} in one click. Paste and send only if it still matches.`
  }
  return `Open ${message.platform || 'the destination'} and complete the action manually after approval.`
}

function handoffButtonLabel(message: OSMessage): string {
  if (message.handoff_mode === 'prefill_compose') return message.platform_label || 'Open compose'
  if (message.handoff_mode === 'copy_then_open') return `Copy draft + ${message.platform_label || 'open platform'}`
  return message.platform_label || `Open ${message.platform || 'platform'}`
}

function followUpDate(days = 7): string {
  const due = new Date()
  due.setDate(due.getDate() + days)
  return due.toISOString().slice(0, 10)
}

/** Preferred channel order; the first present channel is the recommended default. */
const CHANNEL_ORDER = ['email', 'linkedin_note', 'connection_followup']

function channelLabel(variant: string): string {
  if (variant === 'email') return 'Email'
  if (variant === 'linkedin_note') return 'LinkedIn note'
  if (variant === 'connection_followup') return 'Follow-up'
  return variant.replace(/_/g, ' ')
}

/**
 * Case-insensitive substring dedup: "X" and "X (already flagged)" collapse to
 * the shorter line. Order of first appearance is preserved.
 */
function dedupeFlags(flags: string[]): string[] {
  const kept: string[] = []
  for (const raw of flags) {
    const flag = raw.trim()
    if (!flag) continue
    const lower = flag.toLowerCase()
    const matchIndex = kept.findIndex(existing => {
      const existingLower = existing.toLowerCase()
      return existingLower.includes(lower) || lower.includes(existingLower)
    })
    if (matchIndex === -1) kept.push(flag)
    else if (flag.length < kept[matchIndex].length) kept[matchIndex] = flag
  }
  return kept
}

interface ChannelGroup {
  variant: string
  /** Newest draft first. */
  messages: OSMessage[]
}

interface DecisionGroup {
  key: string
  personName: string
  personRole: string
  companyName: string
  /** Newest first across all channels. */
  messages: OSMessage[]
  channels: ChannelGroup[]
  defaultMessage: OSMessage
  verified: boolean
  ready: boolean
  qaScore: number | null
  packetScore: number | null
  flags: string[]
  newestId: number
}

/**
 * One decision card per (company, person). Rows without a person name stay as
 * single-message cards: merging anonymous legacy rows would hide decisions.
 */
function buildGroups(live: OSMessage[]): DecisionGroup[] {
  const byKey = new Map<string, OSMessage[]>()
  for (const message of live) {
    const person = (message.person_name ?? '').trim()
    const key = person
      ? `person:${(message.company_name ?? '').trim().toLowerCase()}|${person.toLowerCase()}`
      : `msg:${message.id}`
    const bucket = byKey.get(key)
    if (bucket) bucket.push(message)
    else byKey.set(key, [message])
  }

  const groups: DecisionGroup[] = []
  for (const [key, bucket] of byKey) {
    const messages = [...bucket].sort((a, b) => b.id - a.id)
    const variants = Array.from(new Set(messages.map(m => m.variant)))
    variants.sort((a, b) => {
      const ai = CHANNEL_ORDER.indexOf(a)
      const bi = CHANNEL_ORDER.indexOf(b)
      return (ai === -1 ? CHANNEL_ORDER.length : ai) - (bi === -1 ? CHANNEL_ORDER.length : bi)
    })
    const channels = variants.map(variant => ({
      variant,
      messages: messages.filter(m => m.variant === variant),
    }))
    const qaScores = messages.map(m => m.qa_score).filter((v): v is number => typeof v === 'number')
    const packetScores = messages
      .map(m => m.checkup_score ?? m.checkup?.overall_score)
      .filter((v): v is number => typeof v === 'number')
    groups.push({
      key,
      personName: (messages[0].person_name ?? '').trim(),
      personRole: (messages[0].person_role ?? '').trim(),
      companyName: (messages[0].company_name ?? '').trim(),
      messages,
      channels,
      defaultMessage: channels[0].messages[0],
      verified: !messages.some(hasUnverifiedRecipient),
      ready: messages.some(isReadyForDecision),
      qaScore: qaScores.length ? Math.max(...qaScores) : null,
      packetScore: packetScores.length ? Math.max(...packetScores) : null,
      flags: dedupeFlags(messages.flatMap(m => m.qa_flags ?? [])),
      newestId: messages[0].id,
    })
  }

  // Readiness order: actionable+verified first, then QA desc, then packet score desc.
  groups.sort((a, b) => {
    const readyDelta = Number(b.ready) - Number(a.ready)
    if (readyDelta) return readyDelta
    const qaDelta = (b.qaScore ?? -1) - (a.qaScore ?? -1)
    if (qaDelta) return qaDelta
    const packetDelta = (b.packetScore ?? -1) - (a.packetScore ?? -1)
    if (packetDelta) return packetDelta
    return b.newestId - a.newestId
  })
  return groups
}

const MAX_VISIBLE_FLAGS = 3

export default function ApprovalQueue({
  messages,
  packetPeople,
  packetCompany,
  onApprove,
  onReject,
  onRecordDelivery,
  onScheduleFollowUp,
  onUpdateFollowUp,
}: Props) {
  const [approving, setApproving] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<number | null>(null)
  const [rejectingAll, setRejectingAll] = useState<string | null>(null)
  const [updating, setUpdating] = useState<number | null>(null)
  const [dismissed, setDismissed] = useState<Set<number>>(new Set())
  const [copied, setCopied] = useState<number | null>(null)
  const [showNeedsReview, setShowNeedsReview] = useState(false)
  const [selection, setSelection] = useState<Record<string, number>>({})
  const [expandedFlags, setExpandedFlags] = useState<Set<string>>(new Set())

  const live = useMemo(
    () => messages.filter(message => !dismissed.has(message.id) && message.content?.trim()),
    [messages, dismissed],
  )
  const groups = useMemo(() => buildGroups(live), [live])
  const ready = groups.filter(group => group.ready)
  const needsReview = groups.filter(group => !group.ready)
  const visible = showNeedsReview ? [...ready, ...needsReview] : ready

  /** WHY line: problem title plus the person's packet-verified relevance, else the packet rationale. */
  function whyLine(group: DecisionGroup, message: OSMessage): string {
    const title = message.problem_title?.trim()
      ?? group.messages.find(m => m.problem_title?.trim())?.problem_title?.trim()
    const samePacket = Boolean(
      packetCompany
      && group.companyName
      && packetCompany.trim().toLowerCase() === group.companyName.toLowerCase(),
    )
    const person = samePacket && group.personName
      ? packetPeople?.find(p => p.name?.trim().toLowerCase() === group.personName.toLowerCase())
      : undefined
    const reason = person?.relevance_reason?.trim() || person?.proximity?.trim()
    if (title && reason) return `${title} — ${reason}`
    if (title) return `The packet identified "${title}" as the technical problem to discuss.`
    return 'The packet generated this draft from the selected company, problem, person, and technical note.'
  }

  return (
    <section className="studio-desk-card decision-inbox">
      <header className="decision-inbox-header">
        <div>
          <p className="studio-kicker">Human review</p>
          <h2>Decision inbox</h2>
          <span>One card per person. Pick the channel, then approve the exact draft — other variants stay pending.</span>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={`badge ${ready.length > 0 ? 'badge-warning' : 'badge-success'}`}>
            {ready.length > 0 ? `${ready.length} pending` : 'All clear'}
          </span>
          {needsReview.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={showNeedsReview}
              onClick={() => setShowNeedsReview(prev => !prev)}>
              {showNeedsReview
                ? `Hide needs-review (${needsReview.length})`
                : `Show needs-review (${needsReview.length})`}
            </button>
          )}
        </div>
      </header>

      {visible.length === 0 ? (
        <div className="decision-empty">
          <p>No send-ready people with verified recipients are waiting.</p>
          {needsReview.length > 0 ? (
            <span>{needsReview.length} decision cards are hidden because every draft failed safety gates or addresses an unverified recipient.</span>
          ) : (
            <span>Build or rerun a packet to generate a source-backed, profile-matched decision queue.</span>
          )}
        </div>
      ) : (
        <div className="decision-list">
          {visible.map(group => {
            const domKey = group.key.replace(/[^a-zA-Z0-9_-]/g, '-')
            const selectedId = selection[group.key]
            const message = group.messages.find(m => m.id === selectedId) ?? group.defaultMessage
            const activeChannel = group.channels.find(channel => channel.variant === message.variant)
              ?? group.channels[0]
            const words = message.word_count ?? message.content.split(/\s+/).filter(Boolean).length
            const over = words > 200
            const sources = sourceLinks(message)
            const safeToAct = message.actionable !== false
            const safeToApprove = message.review_actionable !== false
            const safetyReasons = message.safety_reasons ?? []
            const approved = message.status === 'approved' && message.approval_current
            const canOpenDestination = approved && safeToAct && Boolean(message.platform_url)
            const sent = message.delivery_status === 'sent' || message.delivery_status === 'delivered'
            const rejectable = group.messages.filter(m => m.status === 'draft' || m.state_stale)
            const flagsExpanded = expandedFlags.has(group.key)
            const visibleFlags = flagsExpanded ? group.flags : group.flags.slice(0, MAX_VISIBLE_FLAGS)
            const hiddenFlagCount = group.flags.length - MAX_VISIBLE_FLAGS
            const personLabel = group.personName || 'Selected recipient'
            return (
              <article key={group.key} className="decision-card">
                <div className="decision-card-top">
                  <div>
                    <p className="decision-eyebrow">{group.companyName || 'Company'}</p>
                    <h3>{personLabel}</h3>
                    <span>{group.personRole || 'Role pending'}</span>
                  </div>
                  <div className="decision-badges">
                    {group.verified
                      ? <span className="badge badge-success" title="No unverified-recipient QA flag on any draft for this person.">verified recipient</span>
                      : <span className="badge badge-warning" title="At least one draft carries an unverified-recipient QA flag.">unverified recipient</span>}
                    <span className={`badge font-mono ${over ? 'badge-error' : ''}`}>{words}w</span>
                    {typeof group.qaScore === 'number' && <span className="badge">QA {group.qaScore}/10</span>}
                    {typeof group.packetScore === 'number' && (
                      <span className={`badge ${message.failure_category === 'none' ? 'badge-success' : 'badge-warning'}`}>
                        C {group.packetScore}/10
                      </span>
                    )}
                    {message.crm_status && <span className="badge">{message.crm_status.replace(/_/g, ' ')}</span>}
                    {message.delivery_status && <span className="badge">{message.delivery_status}</span>}
                    {message.follow_up_status && <span className="badge">follow-up {message.follow_up_status}</span>}
                  </div>
                </div>

                <div className="decision-context-grid">
                  <div>
                    <span className="decision-label">Why this person</span>
                    <p>{whyLine(group, message)}</p>
                  </div>
                  <div>
                    <span className="decision-label">Destination</span>
                    <p>{handoffCopy(message)}</p>
                  </div>
                </div>

                {group.flags.length > 0 && (
                  <div className="decision-warning">
                    <strong>QA flags</strong>
                    <ul className="decision-flag-list">
                      {visibleFlags.map(flag => <li key={flag}>{flag}</li>)}
                    </ul>
                    {hiddenFlagCount > 0 && (
                      <button
                        type="button"
                        className="decision-flag-more"
                        aria-expanded={flagsExpanded}
                        onClick={() => setExpandedFlags(prev => {
                          const next = new Set(prev)
                          if (next.has(group.key)) next.delete(group.key)
                          else next.add(group.key)
                          return next
                        })}>
                        {flagsExpanded ? 'Show fewer' : `+${hiddenFlagCount} more`}
                      </button>
                    )}
                  </div>
                )}

                {group.channels.length > 1 && (
                  <nav className="decision-channel-tabs" role="tablist" aria-label={`Outreach channel for ${personLabel}`}>
                    {group.channels.map(channel => (
                      <button
                        key={channel.variant}
                        type="button"
                        role="tab"
                        id={`decision-tab-${domKey}-${channel.variant}`}
                        aria-selected={channel.variant === activeChannel.variant}
                        className={`decision-channel-tab ${channel.variant === activeChannel.variant ? 'is-active' : ''}`}
                        onClick={() => setSelection(prev => ({ ...prev, [group.key]: channel.messages[0].id }))}>
                        {channelLabel(channel.variant)}
                        {channel.messages.length > 1 ? ` · ${channel.messages.length}` : ''}
                      </button>
                    ))}
                  </nav>
                )}

                <div
                  role={group.channels.length > 1 ? 'tabpanel' : undefined}
                  aria-labelledby={group.channels.length > 1 ? `decision-tab-${domKey}-${activeChannel.variant}` : undefined}>
                  {activeChannel.messages.length > 1 && (
                    <div className="decision-draft-pick" aria-label="Multiple drafts on this channel">
                      <span className="decision-label">Drafts</span>
                      {activeChannel.messages.map((draft, index) => (
                        <button
                          key={draft.id}
                          type="button"
                          className={draft.id === message.id ? 'is-active' : ''}
                          onClick={() => setSelection(prev => ({ ...prev, [group.key]: draft.id }))}>
                          {index === 0 ? 'Newest' : `Draft ${activeChannel.messages.length - index}`}
                        </button>
                      ))}
                    </div>
                  )}

                  {!safeToAct && (
                    <div className="decision-warning">
                      <strong>Quarantined</strong>
                      <p>{safetyReasons.slice(0, 3).join(' ') || 'This draft needs a clean packet check before action.'}</p>
                    </div>
                  )}

                  {message.state_stale && (
                    <div className="decision-warning">
                      <strong>Approval expired</strong>
                      <p>The draft changed after approval. Review and approve the current text before any handoff.</p>
                    </div>
                  )}

                  {message.delivery_error && (
                    <div className="decision-warning">
                      <strong>Delivery not confirmed</strong>
                      <p>{message.delivery_error}</p>
                    </div>
                  )}

                  {message.follow_up_due_date && (
                    <div className="decision-contract">
                      <span>Follow-up</span>
                      <p>Due {message.follow_up_due_date} · {message.follow_up_status || 'pending'}</p>
                    </div>
                  )}

                  {sources.length > 0 && (
                    <div className="decision-source-row" aria-label="Evidence sources">
                      <span>Evidence</span>
                      {sources.map(url => (
                        <a key={url} href={url} target="_blank" rel="noopener noreferrer" title={url}>
                          {evidenceLabel(url)}
                        </a>
                      ))}
                    </div>
                  )}

                  <pre className="decision-draft">
                    {message.content}
                  </pre>

                  {message.approval_contract && (
                    <div className="decision-contract">
                      <span>Approval contract</span>
                      <p>{message.approval_contract}</p>
                    </div>
                  )}

                  {over && <p className="decision-error">Over 200 words. Edit before sending manually.</p>}

                  {message.failure_category && message.failure_category !== 'none' && (
                    <div className="decision-warning">
                      <strong>Checkup: {message.failure_category}</strong>
                    </div>
                  )}

                  <div className="decision-actions">
                    {canOpenDestination && (
                      <button
                        className="btn btn-ghost"
                        aria-label={`Open ${message.platform || 'platform'} for ${personLabel}`}
                        onClick={async () => {
                          setUpdating(message.id)
                          if (message.handoff_mode === 'copy_then_open') {
                            await navigator.clipboard.writeText(message.content)
                            setCopied(message.id)
                            setTimeout(() => setCopied(null), 2000)
                          }
                          try {
                            await onRecordDelivery(message.id, 'opened')
                            window.open(message.platform_url, '_blank', 'noopener,noreferrer')
                          } finally {
                            setUpdating(null)
                          }
                        }}
                        disabled={updating === message.id}
                      >
                        {updating === message.id
                          ? 'Opening'
                          : message.safe_retry
                            ? `Retry ${message.platform_label || 'handoff'}`
                            : handoffButtonLabel(message)}
                      </button>
                    )}
                    <button
                      className="btn btn-ghost"
                      aria-label="Copy draft to clipboard"
                      onClick={async () => {
                        await navigator.clipboard.writeText(message.content)
                        setCopied(message.id)
                        setTimeout(() => setCopied(null), 2000)
                      }}>
                      {copied === message.id ? 'Copied' : 'Copy draft'}
                    </button>
                    {(message.status === 'draft' || message.state_stale) && (
                      <>
                        <button
                          className="btn btn-primary"
                          disabled={!safeToApprove || approving === message.id}
                          aria-label={`Approve exact ${channelLabel(message.variant)} draft for ${personLabel}`}
                          onClick={async () => {
                            setApproving(message.id)
                            try { await onApprove(message.id) } finally { setApproving(null) }
                          }}>
                          {approving === message.id
                            ? 'Approving'
                            : message.state_stale
                              ? 'Approve edited draft'
                              : `Approve exact ${channelLabel(message.variant).toLowerCase()}`}
                        </button>
                        <button
                          className="btn btn-danger"
                          disabled={rejecting === message.id || rejectingAll === group.key}
                          aria-label={`Reject the ${channelLabel(message.variant)} draft for ${personLabel}`}
                          onClick={async () => {
                            setRejecting(message.id)
                            try { await onReject(message.id) } finally { setRejecting(null) }
                          }}>
                          {rejecting === message.id ? 'Rejecting' : 'Reject'}
                        </button>
                      </>
                    )}
                    {rejectable.length > 1 && (
                      <button
                        className="btn btn-ghost"
                        disabled={rejectingAll === group.key || rejecting !== null}
                        aria-label={`Reject all ${rejectable.length} pending drafts for ${personLabel}`}
                        onClick={async () => {
                          setRejectingAll(group.key)
                          try {
                            for (const draft of rejectable) {
                              await onReject(draft.id)
                            }
                          } finally {
                            setRejectingAll(null)
                          }
                        }}>
                        {rejectingAll === group.key ? 'Rejecting all' : `Reject all for this person (${rejectable.length})`}
                      </button>
                    )}
                    {approved && !sent && (
                      <button
                        className="btn btn-primary"
                        disabled={updating === message.id}
                        onClick={async () => {
                          setUpdating(message.id)
                          try { await onRecordDelivery(message.id, 'sent') } finally { setUpdating(null) }
                        }}>
                        Mark sent
                      </button>
                    )}
                    {approved && sent && !message.follow_up_id && (
                      <button
                        className="btn btn-primary"
                        disabled={updating === message.id}
                        onClick={async () => {
                          setUpdating(message.id)
                          try {
                            await onScheduleFollowUp(message.id, followUpDate(), 'Review for a response.')
                          } finally {
                            setUpdating(null)
                          }
                        }}>
                        Schedule 7-day follow-up
                      </button>
                    )}
                    {message.follow_up_id && message.follow_up_status === 'pending' && (
                      <>
                        <button
                          className="btn btn-primary"
                          disabled={updating === message.id}
                          onClick={async () => {
                            setUpdating(message.id)
                            try { await onUpdateFollowUp(message.follow_up_id!, 'completed') } finally { setUpdating(null) }
                          }}>
                          Complete follow-up
                        </button>
                        <button
                          className="btn btn-ghost"
                          disabled={updating === message.id}
                          onClick={async () => {
                            setUpdating(message.id)
                            try { await onUpdateFollowUp(message.follow_up_id!, 'skipped') } finally { setUpdating(null) }
                          }}>
                          Skip follow-up
                        </button>
                      </>
                    )}
                    <button
                      className="btn btn-ghost ml-auto"
                      aria-label={`Skip every draft for ${personLabel} in this session`}
                      onClick={() => setDismissed(prev => new Set([...prev, ...group.messages.map(m => m.id)]))}>
                      Skip person
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
