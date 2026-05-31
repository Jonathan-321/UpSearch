import { useState } from 'react'
import type { FilterKey } from '../types'

interface Props {
  onRun: (topic: string, filters: FilterKey[]) => void
  isRunning: boolean
}

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'reddit', label: 'Reddit' },
  { key: 'hackernews', label: 'Hacker News' },
  { key: 'engineers', label: 'Engineers' },
  { key: 'researchers', label: 'Researchers' },
  { key: 'startups', label: 'Startups' },
  { key: 'academia', label: 'Academia' },
]

const EXAMPLES = ['LLM inference optimization', 'AI safety interpretability', 'robotics perception']

export default function SearchPanel({ onRun, isRunning }: Props) {
  const [topic, setTopic] = useState('')
  const [activeFilters, setActiveFilters] = useState<FilterKey[]>(['reddit', 'hackernews'])

  return (
    <section className="panel panel-raised p-5 sm:p-6">
      <form onSubmit={e => {
        e.preventDefault()
        if (topic.trim() && !isRunning) onRun(topic.trim(), activeFilters)
      }} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto] gap-2">
          <input className="input !py-3" value={topic} onChange={e => setTopic(e.target.value)}
            placeholder="What technical problem space do you want to explore?"
            disabled={isRunning} aria-label="Technical topic" />
          <button className="btn btn-primary" type="submit" disabled={!topic.trim() || isRunning}>
            {isRunning ? 'Pipeline running...' : 'Run research pipeline'}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-meta">Try:</span>
          {EXAMPLES.map(example => <button key={example} type="button" className="btn btn-ghost !px-2.5 !py-1 !text-xs" onClick={() => setTopic(example)}>{example}</button>)}
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-border">
          <span className="text-meta mr-1">Filters:</span>
          {FILTERS.map(filter => {
            const active = activeFilters.includes(filter.key)
            return (
              <button key={filter.key} type="button" aria-pressed={active}
                onClick={() => setActiveFilters(prev => active ? prev.filter(item => item !== filter.key) : [...prev, filter.key])}
                className={`badge transition-colors ${active ? 'badge-accent' : 'hover:text-text-1'}`}>
                {filter.label}
              </button>
            )
          })}
        </div>
      </form>
    </section>
  )
}
