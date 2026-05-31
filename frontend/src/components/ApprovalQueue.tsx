import { useState } from 'react'
import type { OSMessage } from '../hooks/useOS'

interface Props {
  messages: OSMessage[]
  onApprove: (id: number) => Promise<void>
}

const VARIANT_STYLE: Record<string, string> = {
  email:              'text-sky-400 bg-sky-500/10 border-sky-500/20',
  linkedin_note:      'text-blue-400 bg-blue-500/10 border-blue-500/20',
  connection_followup:'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  recruiter:          'text-zinc-400 bg-zinc-800/50 border-zinc-700',
}

export default function ApprovalQueue({ messages, onApprove }: Props) {
  const [approving, setApproving] = useState<number | null>(null)
  const [dismissed, setDismissed] = useState<Set<number>>(new Set())
  const [copied, setCopied]       = useState<number | null>(null)

  const visible = messages.filter(m => !dismissed.has(m.id) && m.content?.trim())

  if (visible.length === 0) {
    return (
      <section className="card p-6 flex items-center gap-4 animate-fade-in-up">
        <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} className="text-emerald-400">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-zinc-300">Approval Queue — All clear</p>
          <p className="text-xs text-zinc-600 mt-0.5">Build a packet to generate drafts for review</p>
        </div>
      </section>
    )
  }

  return (
    <section className="card overflow-hidden animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.05]">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className="w-2 h-2 rounded-full bg-amber-400"/>
            <div className="absolute inset-0 w-2 h-2 rounded-full bg-amber-400 animate-ping-slow opacity-60"/>
          </div>
          <span className="text-sm font-semibold text-zinc-200">Approval Queue</span>
        </div>
        <span className="text-xs font-semibold text-amber-400 tabular-nums">
          {visible.length} pending
        </span>
      </div>

      {/* Cards */}
      <div className="divide-y divide-white/[0.04]">
        {visible.map((msg, i) => {
          const wc      = msg.word_count ?? msg.content?.split(/\s+/).filter(Boolean).length ?? 0
          const isOver  = wc > 200
          const vs      = VARIANT_STYLE[msg.variant ?? ''] ?? VARIANT_STYLE['email']

          return (
            <div key={msg.id}
              className={`p-5 space-y-4 animate-fade-in-up`}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              {/* Meta row */}
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border uppercase tracking-wide ${vs}`}>
                    {msg.variant?.replace('_', ' ')}
                  </span>
                  {msg.person_name && (
                    <span className="text-xs text-zinc-500 flex items-center gap-1">
                      <svg width="10" height="10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7"/>
                      </svg>
                      {msg.person_name}
                    </span>
                  )}
                </div>
                <span className={`text-xs font-mono tabular-nums px-2 py-0.5 rounded border
                  ${isOver ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-zinc-600 bg-zinc-800/50 border-zinc-700'}`}>
                  {wc}w
                </span>
              </div>

              {/* Draft */}
              <pre className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono
                              bg-white/[0.015] border border-white/[0.04] rounded-xl p-4
                              max-h-52 overflow-y-auto">
                {msg.content}
              </pre>

              {isOver && (
                <p className="text-xs text-red-400 flex items-center gap-1.5">
                  <svg width="11" height="11" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                  </svg>
                  Over 200 words — edit before sending
                </p>
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
                  className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-lg
                             bg-gradient-to-r from-emerald-700 to-green-700 hover:from-emerald-600 hover:to-green-600
                             text-white transition-all shadow-md shadow-emerald-950/50 disabled:opacity-50"
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
                  className="text-xs px-3 py-2 rounded-lg border border-white/[0.07] bg-white/[0.03]
                             hover:bg-white/[0.06] text-zinc-500 hover:text-zinc-300 transition-all"
                >
                  Skip
                </button>

                <button
                  onClick={async () => {
                    await navigator.clipboard.writeText(msg.content ?? '')
                    setCopied(msg.id)
                    setTimeout(() => setCopied(null), 2000)
                  }}
                  className="ml-auto flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-white/[0.07]
                             bg-white/[0.03] hover:bg-white/[0.06] text-zinc-500 hover:text-zinc-300 transition-all"
                >
                  {copied === msg.id ? (
                    <><svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg> Copied</>
                  ) : (
                    <><svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy</>
                  )}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
