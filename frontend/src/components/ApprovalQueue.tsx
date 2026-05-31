import { useState } from 'react'
import type { OSMessage } from '../hooks/useOS'

interface Props {
  messages: OSMessage[]
  onApprove: (id: number) => Promise<void>
}

export default function ApprovalQueue({ messages, onApprove }: Props) {
  const [approving, setApproving] = useState<number | null>(null)
  const [dismissed, setDismissed] = useState<Set<number>>(new Set())

  if (messages.length === 0) {
    return (
      <section className="card p-5 animate-fade-in-up">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-sm font-semibold text-zinc-300">Approval Queue</span>
          <span className="text-xs text-emerald-400 ml-1">All clear</span>
        </div>
        <p className="text-xs text-zinc-600">No drafts pending approval. Build a packet and drafts will appear here.</p>
      </section>
    )
  }

  const visible = messages.filter(m => !dismissed.has(m.id))

  return (
    <section className="card overflow-hidden animate-fade-in-up">
      <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-60"/>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400"/>
          </span>
          <span className="text-sm font-semibold text-zinc-200">Approval Queue</span>
        </div>
        <span className="text-xs text-amber-400">{visible.length} pending</span>
      </div>

      <div className="divide-y divide-zinc-800/50 max-h-[500px] overflow-y-auto">
        {visible.map(msg => {
          const wordCount = msg.word_count ?? msg.content?.split(/\s+/).length ?? 0
          const isOver = wordCount > 200

          return (
            <div key={msg.id} className="p-5 space-y-3">
              {/* Header */}
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-zinc-200 uppercase tracking-wide">
                    {msg.variant?.replace('_', ' ')}
                  </span>
                  {msg.person_name && (
                    <span className="text-xs text-zinc-500">→ {msg.person_name}</span>
                  )}
                </div>
                <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
                  isOver ? 'text-red-400 bg-red-500/10 border-red-500/30'
                         : 'text-zinc-500 bg-zinc-800 border-zinc-700'
                }`}>
                  {wordCount}w
                </span>
              </div>

              {/* Draft preview */}
              <pre className="bg-zinc-800/30 border border-zinc-800 rounded-lg p-4 text-xs text-zinc-300
                              leading-relaxed whitespace-pre-wrap font-sans max-h-48 overflow-y-auto">
                {msg.content}
              </pre>

              {isOver && (
                <p className="text-xs text-red-400">Over 200 words — edit before sending.</p>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={async () => {
                    setApproving(msg.id)
                    await onApprove(msg.id)
                    setApproving(null)
                  }}
                  disabled={approving === msg.id}
                  className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg
                             bg-gradient-to-r from-emerald-700 to-green-700 hover:from-emerald-600 hover:to-green-600
                             text-white transition-all disabled:opacity-50"
                >
                  {approving === msg.id ? (
                    <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                  ) : (
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  )}
                  Approve
                </button>
                <button
                  onClick={() => setDismissed(prev => new Set([...prev, msg.id]))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800
                             hover:bg-zinc-700 text-zinc-400 transition-colors"
                >
                  Skip
                </button>
                <button
                  onClick={async () => {
                    await navigator.clipboard.writeText(msg.content ?? '')
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800
                             hover:bg-zinc-700 text-zinc-400 transition-colors ml-auto"
                >
                  Copy
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
