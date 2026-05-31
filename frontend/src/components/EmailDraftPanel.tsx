import { useState } from 'react'

interface EmailDraftPanelProps {
  draft: string
  onEdit: (draft: string) => void
  onLog: (sent: boolean) => void
}

export default function EmailDraftPanel({ draft, onEdit, onLog }: EmailDraftPanelProps) {
  const [copied, setCopied] = useState(false)
  const [logged, setLogged] = useState(false)

  const wordCount = draft.trim().split(/\s+/).filter(Boolean).length
  const isOver = wordCount > 200

  const handleCopy = async () => {
    await navigator.clipboard.writeText(draft)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleLog = (sent: boolean) => {
    onLog(sent)
    setLogged(true)
  }

  return (
    <div className="card p-5 flex flex-col gap-4 animate-fade-in-up h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-indigo-500/20 flex items-center justify-center">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-indigo-400">
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-zinc-100">Draft Email</span>
        </div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
          isOver
            ? 'text-red-400 bg-red-500/10 border-red-500/30'
            : 'text-zinc-500 bg-zinc-800 border-zinc-700'
        }`}>
          {wordCount} / 200 words
        </span>
      </div>

      {/* Editable draft */}
      <textarea
        value={draft}
        onChange={(e) => onEdit(e.target.value)}
        className="flex-1 min-h-[280px] bg-zinc-800/40 border border-zinc-700 rounded-lg p-4
                   text-sm text-zinc-200 leading-relaxed font-mono resize-none outline-none
                   focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20
                   transition-all duration-200 placeholder-zinc-600"
        placeholder="Draft will appear here..."
        spellCheck={false}
      />

      {isOver && (
        <p className="text-xs text-red-400 -mt-2">
          Over 200 words — edit before sending.
        </p>
      )}

      {/* Action row */}
      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-zinc-800">
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-zinc-700
                     bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors duration-150"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Copied
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <rect x="9" y="9" width="13" height="13" rx="2" />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
              </svg>
              Copy
            </>
          )}
        </button>

        {!logged ? (
          <>
            <button
              onClick={() => handleLog(false)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-zinc-700
                         bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors duration-150"
            >
              Log to W&amp;B (draft)
            </button>
            <button
              onClick={() => handleLog(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                         bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500
                         text-white font-semibold transition-all duration-200 shadow-sm"
            >
              Mark as sent + log
            </button>
          </>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-emerald-400">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Logged to W&amp;B
          </span>
        )}
      </div>
    </div>
  )
}
