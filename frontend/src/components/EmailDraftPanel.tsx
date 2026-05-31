import { useState } from 'react'

interface Props {
  draft: string
  onEdit: (draft: string) => void
  onLog: (sent: boolean) => void
}

export default function EmailDraftPanel({ draft, onEdit, onLog }: Props) {
  const [copied, setCopied] = useState(false)
  const [logged, setLogged] = useState(false)
  const words = draft.trim().split(/\s+/).filter(Boolean).length
  const over = words > 200

  return (
    <section className="panel overflow-hidden">
      <header className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="workspace-label">Draft</p>
          <h3 className="text-base font-semibold text-text-1 mt-1">Editable email</h3>
        </div>
        <span className={`badge font-mono ${over ? 'badge-error' : ''}`}>{words}/200w</span>
      </header>
      <div className="p-5">
        <textarea value={draft} onChange={e => onEdit(e.target.value)}
          className="input font-mono min-h-[310px] resize-y !text-sm !leading-relaxed"
          aria-label="Outreach email draft" spellCheck={false} />
        {over && <p className="text-xs text-red-400 mt-2">Over 200 words. Edit before sending.</p>}

        <div className="flex flex-wrap items-center gap-2 mt-4">
          <button className="btn btn-ghost" onClick={async () => {
            await navigator.clipboard.writeText(draft)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
          }}>{copied ? 'Copied' : 'Copy draft'}</button>

          {!logged ? (
            <>
              <button className="btn btn-ghost" onClick={() => { onLog(false); setLogged(true) }}>Log draft</button>
              <button className="btn btn-primary" onClick={() => { onLog(true); setLogged(true) }}>Mark sent + log</button>
            </>
          ) : <span className="badge badge-success">Logged to W&amp;B</span>}
        </div>
      </div>
    </section>
  )
}
