import { useEffect, useState } from 'react'

import HarnessCheckup from './components/HarnessCheckup'
import PacketStudio from './components/PacketStudio'
import { fetchModelStatus, type OSModelStatus } from './hooks/useOS'

type AppMode = 'os' | 'review'

const modeLabels: Record<AppMode, string> = {
  os: 'Build Packet',
  review: 'Review',
}

const modeMeta: Record<AppMode, { number: string; label: string; title: string; detail: string }> = {
  os: {
    number: '01',
    label: 'Build',
    title: 'Assemble the technical packet.',
    detail: 'The main studio for company-specific problems, people, notes, drafts, QA, and approval.',
  },
  review: {
    number: '02',
    label: 'Verify',
    title: 'Trust the packet before action.',
    detail: 'Profile truth, source grounding, people verification, approval gates, and run traces.',
  },
}

function ModelConfigBanner() {
  const [status, setStatus] = useState<OSModelStatus | null>(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchModelStatus().then(data => {
      if (!cancelled) setStatus(data)
    })
    return () => { cancelled = true }
  }, [])

  if (dismissed || !status || status.ok) return null

  return (
    <div className="relative z-10 mx-auto w-full max-w-[1620px] px-4 pt-4 sm:px-6">
      <div className="studio-warning" role="alert">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <strong>Model configuration needs attention</strong>
            {status.problems.map((problem, index) => (
              <p key={index}>{problem}</p>
            ))}
          </div>
          <button
            className="btn btn-ghost"
            aria-label="Dismiss model configuration warning"
            onClick={() => setDismissed(true)}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [mode, setMode] = useState<AppMode>('os')
  const activeMode = modeMeta[mode]

  return (
    <div className="min-h-screen flex flex-col relative app-stage">

      <header className="app-header relative z-10">
        <div className="mx-auto flex max-w-[1620px] items-center justify-between gap-4 px-4 py-5 sm:px-6">
          <div className="app-brand">
            <div className="brand-mark" aria-hidden="true">
              <svg width="17" height="17" viewBox="0 0 16 16" fill="none">
                <circle cx="6" cy="6" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                <line x1="9" y1="9" x2="13.5" y2="13.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                <line x1="6" y1="3" x2="6" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="3" y1="6" x2="9" y2="6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
            </div>
            <div>
              <p>UpSearch</p>
              <span>{activeMode.number} · {activeMode.label}</span>
            </div>
          </div>

          <div role="group" aria-label="Application mode" className="mode-switcher">
            {(['os', 'review'] as AppMode[]).map(item => (
              <button key={item} onClick={() => setMode(item)}
                aria-pressed={mode === item}
                className={mode === item ? 'is-active' : ''}>
                {modeLabels[item]}
              </button>
            ))}
          </div>

          <div className="mode-context">
            <span>{activeMode.title}</span>
            <p>{activeMode.detail}</p>
          </div>

          <div className="status-pill hidden sm:flex">
            <span className="status-light" />
            DeepSeek · Claude · W&amp;B
          </div>
        </div>
      </header>

      <ModelConfigBanner />

      <main className="relative z-10 mx-auto w-full max-w-[1620px] flex-1 px-4 pb-10 sm:px-6">
        {mode === 'review' ? <HarnessCheckup /> : <PacketStudio />}
      </main>

      <footer className="relative z-10 px-6 py-4 text-center">
        <p className="text-xs text-zinc-400">
          UpSearch + Opportunity OS &nbsp;·&nbsp; Action over analysis.
        </p>
      </footer>
    </div>
  )
}
