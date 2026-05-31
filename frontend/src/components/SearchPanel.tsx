import { useState } from 'react'
import type { FilterKey } from '../types'

interface SearchPanelProps {
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

const EXAMPLES = [
  'AI safety interpretability research',
  'LLM inference optimization at scale',
  'robotics perception systems',
  'EEG wellness applications',
  'federated learning privacy',
]

export default function SearchPanel({ onRun, isRunning }: SearchPanelProps) {
  const [topic, setTopic] = useState('')
  const [activeFilters, setActiveFilters] = useState<FilterKey[]>(['reddit', 'hackernews'])

  const toggleFilter = (key: FilterKey) => {
    setActiveFilters((prev) =>
      prev.includes(key) ? prev.filter((f) => f !== key) : [...prev, key],
    )
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim() || isRunning) return
    onRun(topic.trim(), activeFilters)
  }

  const handleExample = (ex: string) => {
    setTopic(ex)
  }

  return (
    <section className="card p-6 animate-fade-in-up">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Main input */}
        <div className="relative">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <svg className="w-5 h-5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <circle cx="11" cy="11" r="7" />
              <path strokeLinecap="round" d="M16.5 16.5L21 21" />
            </svg>
          </div>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What problem space do you want to explore?"
            className="w-full bg-zinc-800/50 border border-zinc-700 rounded-xl pl-12 pr-4 py-4 text-base
                       text-zinc-100 placeholder-zinc-500 outline-none
                       focus:border-violet-500/70 focus:ring-2 focus:ring-violet-500/10
                       transition-all duration-200"
            disabled={isRunning}
          />
        </div>

        {/* Examples */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-zinc-600 font-medium">Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => handleExample(ex)}
              className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-800 hover:border-zinc-700
                         px-2.5 py-1 rounded-md transition-colors duration-150"
            >
              {ex}
            </button>
          ))}
        </div>

        {/* Filters + submit */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map(({ key, label }) => {
              const active = activeFilters.includes(key)
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleFilter(key)}
                  className={`chip ${
                    active
                      ? 'bg-violet-600/20 border-violet-500/50 text-violet-300'
                      : 'bg-zinc-800/50 border-zinc-700 text-zinc-500 hover:border-zinc-600 hover:text-zinc-400'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>

          <button
            type="submit"
            disabled={!topic.trim() || isRunning}
            className="btn-primary ml-auto flex items-center gap-2 min-w-[180px] justify-center"
          >
            {isRunning ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Pipeline running...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 3l14 9-14 9V3z" />
                </svg>
                Run Research Pipeline
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  )
}
