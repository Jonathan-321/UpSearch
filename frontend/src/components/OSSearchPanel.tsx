import { useState } from 'react'

const LANES = [
  { value: 'ai_infra',  label: 'AI Infrastructure' },
  { value: 'inference', label: 'Inference Systems' },
  { value: 'agentic',   label: 'Agentic AI' },
  { value: 'dev_tools', label: 'Developer Tools' },
  { value: 'data',      label: 'Data Platforms' },
  { value: 'robotics',  label: 'Robotics AI' },
]

const SUGGESTIONS = ['Baseten', 'Modal', 'Together', 'Fireworks', 'CoreWeave', 'Anyscale', 'Replicate', 'Groq']

interface Props {
  onBuild: (company: string, lane: string) => void
  isRunning: boolean
}

export default function OSSearchPanel({ onBuild, isRunning }: Props) {
  const [company, setCompany] = useState('')
  const [lane, setLane]       = useState('ai_infra')
  const [focused, setFocused] = useState(false)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!company.trim() || isRunning) return
    onBuild(company.trim(), lane)
  }

  return (
    <section className="card p-6 space-y-4 animate-fade-in-up">
      {/* Label */}
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-violet-500/15 border border-violet-500/20 flex items-center justify-center">
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} className="text-violet-400">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-zinc-200">Build Company Packet</p>
          <p className="text-xs text-zinc-600">Profile → Company → Problem → People → Note → Outreach → QA</p>
        </div>
      </div>

      <form onSubmit={submit} className="space-y-3">
        {/* Input row */}
        <div className="flex gap-2">
          {/* Company input */}
          <div className={`relative flex-1 rounded-xl transition-all duration-200
            ${focused ? 'ring-2 ring-violet-500/30' : ''}`}>
            <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-zinc-600">
                <path strokeLinecap="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16"/>
                <path strokeLinecap="round" d="M3 21h18M9 7h1m-1 4h1m4-4h1m-1 4h1"/>
              </svg>
            </div>
            <input
              type="text"
              value={company}
              onChange={e => setCompany(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Company name — e.g. Baseten, Modal, Fireworks"
              disabled={isRunning}
              className="w-full bg-white/[0.03] border border-white/[0.07] rounded-xl
                         pl-10 pr-4 py-3 text-sm text-zinc-100 placeholder-zinc-600
                         outline-none transition-colors disabled:opacity-50
                         focus:border-violet-500/40 focus:bg-white/[0.05]"
            />
          </div>

          {/* Lane selector */}
          <select
            value={lane}
            onChange={e => setLane(e.target.value)}
            disabled={isRunning}
            className="bg-white/[0.03] border border-white/[0.07] rounded-xl px-3 py-3
                       text-sm text-zinc-400 outline-none transition-colors
                       focus:border-violet-500/40 disabled:opacity-50 cursor-pointer"
          >
            {LANES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>

          {/* Submit */}
          <button type="submit" disabled={!company.trim() || isRunning} className="btn-primary flex items-center gap-2 px-5 shrink-0">
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

        {/* Quick-add chips */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-700 font-medium">Quick add:</span>
          {SUGGESTIONS.map(s => (
            <button
              key={s} type="button" onClick={() => setCompany(s)}
              className="text-xs text-zinc-500 hover:text-zinc-200 bg-white/[0.02] hover:bg-white/[0.05]
                         border border-white/[0.06] hover:border-violet-500/20
                         px-2.5 py-1 rounded-lg transition-all duration-150"
            >
              {s}
            </button>
          ))}
        </div>
      </form>
    </section>
  )
}
