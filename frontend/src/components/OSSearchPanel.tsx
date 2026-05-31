import { useState } from 'react'

const LANES = [
  { value: 'ai_infra', label: 'AI Infrastructure' },
  { value: 'inference', label: 'Inference Systems' },
  { value: 'agentic', label: 'Agentic AI' },
  { value: 'dev_tools', label: 'Developer Tools' },
  { value: 'data', label: 'Data Platforms' },
  { value: 'robotics', label: 'Robotics AI' },
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
    <section className="studio-command">
      <div className="studio-command-copy">
        <p>New packet</p>
        <h2>Choose a company to investigate</h2>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_190px_auto] gap-2">
          <input
            type="text"
            value={company}
            onChange={e => setCompany(e.target.value)}
            placeholder="Company name, e.g. Baseten"
            disabled={isRunning}
            className="studio-input"
            aria-label="Company name"
          />
          <select value={lane} onChange={e => setLane(e.target.value)} disabled={isRunning}
            className="studio-input cursor-pointer" aria-label="Opportunity lane">
            {LANES.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <button type="submit" disabled={!company.trim() || isRunning} className="studio-primary-action">
            {isRunning ? 'Building packet...' : 'Build packet'}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a867d]">Quick add</span>
          {SUGGESTIONS.map(item => (
            <button key={item} type="button" onClick={() => setCompany(item)}
              className="studio-suggestion">
              {item}
            </button>
          ))}
        </div>
      </form>
    </section>
  )
}
