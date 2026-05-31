import { useState } from 'react'

const LANES = [
  { value: 'ai_infra',    label: 'AI Infrastructure' },
  { value: 'inference',   label: 'Inference Systems' },
  { value: 'agentic',     label: 'Agentic AI' },
  { value: 'dev_tools',   label: 'Developer Tools' },
  { value: 'data',        label: 'Data Platforms' },
  { value: 'robotics',    label: 'Robotics AI' },
]

const SUGGESTIONS = ['Baseten', 'Modal', 'Together', 'Fireworks', 'CoreWeave', 'Anyscale', 'Replicate', 'Groq']

interface Props {
  onBuild: (company: string, lane: string) => void
  isRunning: boolean
}

export default function OSSearchPanel({ onBuild, isRunning }: Props) {
  const [company, setCompany] = useState('')
  const [lane, setLane] = useState('ai_infra')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!company.trim() || isRunning) return
    onBuild(company.trim(), lane)
  }

  return (
    <section className="card p-6 animate-fade-in-up">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-6 h-6 rounded-md bg-violet-500/20 flex items-center justify-center">
          <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} className="text-violet-400">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <span className="text-sm font-semibold text-zinc-300">Build Company Packet</span>
        <span className="text-xs text-zinc-600 ml-1">— Profile → Company → Problem → People → Note → Outreach → QA</span>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={company}
              onChange={e => setCompany(e.target.value)}
              placeholder="Company name (e.g. Baseten, Modal, Fireworks)"
              className="w-full bg-zinc-800/50 border border-zinc-700 rounded-xl px-4 py-3 text-sm
                         text-zinc-100 placeholder-zinc-500 outline-none
                         focus:border-violet-500/70 focus:ring-2 focus:ring-violet-500/10 transition-all"
              disabled={isRunning}
            />
          </div>
          <select
            value={lane}
            onChange={e => setLane(e.target.value)}
            className="bg-zinc-800/50 border border-zinc-700 rounded-xl px-3 py-3 text-sm text-zinc-300
                       outline-none focus:border-violet-500/50 transition-colors"
            disabled={isRunning}
          >
            {LANES.map(l => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
          <button type="submit" disabled={!company.trim() || isRunning} className="btn-primary flex items-center gap-2 px-5">
            {isRunning ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Building...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                Build Packet
              </>
            )}
          </button>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-zinc-600">Quick add:</span>
          {SUGGESTIONS.map(s => (
            <button key={s} type="button" onClick={() => setCompany(s)}
              className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-800
                         hover:border-zinc-700 px-2.5 py-1 rounded-md transition-colors">
              {s}
            </button>
          ))}
        </div>
      </form>
    </section>
  )
}
