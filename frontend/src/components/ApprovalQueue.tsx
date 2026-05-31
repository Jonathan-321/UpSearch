import { useState } from 'react'
import type { OSMessage } from '../hooks/useOS'

interface Props {
  messages: OSMessage[]
  onApprove: (id: number) => Promise<void>
}

export default function ApprovalQueue({ messages, onApprove }: Props) {
  const [approving, setApproving] = useState<number | null>(null)
  const [dismissed, setDismissed] = useState<Set<number>>(new Set())
  const [copied, setCopied] = useState<number | null>(null)
  const visible = messages.filter(message => !dismissed.has(message.id) && message.content?.trim())

  return (
    <section className="panel overflow-hidden">
      <header className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="workspace-label">Human Review</p>
          <h2 className="text-section mt-1">Approval queue</h2>
        </div>
        <span className={`badge ${visible.length > 0 ? 'badge-warning' : 'badge-success'}`}>
          {visible.length > 0 ? `${visible.length} pending` : 'All clear'}
        </span>
      </header>

      {visible.length === 0 ? (
        <div className="px-5 py-8 text-center">
          <p className="text-sm text-text-2">No outreach drafts are waiting for review.</p>
          <p className="text-xs text-text-3 mt-1">Build a packet to generate a review queue.</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {visible.map(message => {
            const words = message.word_count ?? message.content.split(/\s+/).filter(Boolean).length
            const over = words > 200
            return (
              <article key={message.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge badge-accent uppercase">{message.variant?.replace('_', ' ')}</span>
                    {message.person_name && <span className="text-xs text-text-2">For {message.person_name}</span>}
                  </div>
                  <span className={`badge font-mono ${over ? 'badge-error' : ''}`}>{words}w</span>
                </div>

                <pre className="font-mono text-sm text-text-2 leading-relaxed whitespace-pre-wrap panel panel-raised p-4 mt-4 max-h-64 overflow-y-auto">
                  {message.content}
                </pre>

                {over && <p className="text-xs text-red-400 mt-2">Over 200 words. Edit before sending manually.</p>}

                <div className="flex flex-wrap items-center gap-2 mt-4">
                  <button className="btn bg-emerald-700 text-white hover:bg-emerald-600"
                    disabled={approving === message.id}
                    onClick={async () => {
                      setApproving(message.id)
                      try { await onApprove(message.id) } finally { setApproving(null) }
                    }}>
                    {approving === message.id ? 'Approving...' : 'Approve'}
                  </button>
                  <button className="btn btn-ghost" onClick={() => setDismissed(prev => new Set([...prev, message.id]))}>Skip</button>
                  <button className="btn btn-ghost ml-auto" onClick={async () => {
                    await navigator.clipboard.writeText(message.content)
                    setCopied(message.id)
                    setTimeout(() => setCopied(null), 2000)
                  }}>
                    {copied === message.id ? 'Copied' : 'Copy draft'}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
