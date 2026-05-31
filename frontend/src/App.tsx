import { useState } from 'react'

// UpSearch pipeline
import SearchPanel from './components/SearchPanel'
import PipelineStepper from './components/PipelineStepper'
import OpportunityCard from './components/OpportunityCard'
import StrategyPanel from './components/StrategyPanel'
import EmailDraftPanel from './components/EmailDraftPanel'
import WandbTrackerPanel from './components/WandbTrackerPanel'
import SupervisorPanel from './components/SupervisorPanel'
import ActivityConsole from './components/ActivityConsole'
import { usePipeline } from './hooks/usePipeline'

import HarnessDemo from './components/HarnessDemo'
import PacketStudio from './components/PacketStudio'

import type { FilterKey } from './types'

type AppMode = 'search' | 'os' | 'demo'

const modeLabels: Record<AppMode, string> = {
  search: 'Quick Search',
  os: 'Opportunity OS',
  demo: 'Harness Demo',
}

const modeMeta: Record<AppMode, { number: string; label: string; title: string; detail: string }> = {
  search: {
    number: '01',
    label: 'Scout',
    title: 'Find raw opportunity signal.',
    detail: 'Fast community and source search when the target is still vague.',
  },
  os: {
    number: '02',
    label: 'Build',
    title: 'Assemble the technical packet.',
    detail: 'The main studio for company-specific problems, people, notes, drafts, QA, and approval.',
  },
  demo: {
    number: '03',
    label: 'Prove',
    title: 'Show the harness behind the agents.',
    detail: 'A traceable demo of model routing, typed handoffs, validators, costs, and approval gates.',
  },
}

// ── Quick-Search view (original UpSearch) ─────────────────────────────────────
function SearchView() {
  const {
    status, error, agentStatuses, opportunities, selectedOpportunity,
    strategy, draft, supervisorScores, wandbRuns, logEntries,
    startPipeline, selectOpportunity, setDraft, logToWandb,
  } = usePipeline()

  const isRunning  = status === 'scouting' || status === 'analyzing'
  const isPostSelect = status === 'strategizing' || status === 'writing'
  const isPipelineActive = isRunning || isPostSelect
  const handleRun = (topic: string, _filters: FilterKey[]) => startPipeline(topic)

  return (
    <div className="mode-page quick-search-page">
      <section className="mode-hero">
        <div className="mode-hero-copy">
          <p className="studio-kicker">Quick search</p>
          <h1>Turn public signal into the first credible lead.</h1>
          <p>
            Use this when the user only has an interest area. The scout searches communities,
            ranks useful opportunities, and creates a first outreach angle before the deeper packet build.
          </p>
        </div>
        <div className="mode-side-card">
          <span>01</span>
          <strong>Signal scout</strong>
          <p>Reddit, Hacker News, engineers, researchers, startups, and academia.</p>
        </div>
      </section>

      <section className="mode-workbench">
        <div className="mode-section-head">
          <div>
            <p className="studio-kicker">Search brief</p>
            <h2>Start broad. Keep the output narrow.</h2>
          </div>
          <span>feeds the packet studio</span>
        </div>

        <SearchPanel onRun={handleRun} isRunning={isPipelineActive} />

        {status !== 'idle' && (
          <PipelineStepper agentStatuses={agentStatuses} opportunityCount={opportunities.length} />
        )}

        <ActivityConsole entries={logEntries} isRunning={isPipelineActive} />
      </section>

      {status === 'error' && error && (
        <div className="card border-red-500/30 bg-red-500/5 p-5 flex items-start gap-3 animate-fade-in-up">
          <svg className="w-5 h-5 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <div>
            <p className="text-sm font-semibold text-red-400">Pipeline error</p>
            <p className="text-xs text-zinc-400 mt-0.5">{error}</p>
            <p className="text-xs text-zinc-600 mt-1">
              Make sure the API server is running: <code className="text-zinc-400">uvicorn server:app --reload --port 8000</code>
            </p>
          </div>
        </div>
      )}

      {status === 'scouting' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
            <span className="text-xs text-zinc-500">Scout Agent searching Reddit and Hacker News...</span>
          </div>
          {[0,1,2].map(i => <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-[#fffdf8] via-[#ece8df] to-[#fffdf8] bg-[length:200%_100%]"/>)}
        </div>
      )}

      {status === 'analyzing' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
            <span className="text-xs text-zinc-500">Analyst Agent scoring opportunities...</span>
          </div>
          {[0,1,2].map(i => <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-[#fffdf8] via-[#ece8df] to-[#fffdf8] bg-[length:200%_100%]"/>)}
        </div>
      )}

      {['selecting','strategizing','writing','done'].includes(status) && opportunities.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-text-1">{opportunities.length} opportunities ranked by fit</h2>
            <span className="text-xs text-text-2">click any to build outreach</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {opportunities.map((opp, i) => (
              <OpportunityCard key={opp.post.id} opportunity={opp} index={i}
                isSelected={selectedOpportunity?.post.id === opp.post.id} onSelect={selectOpportunity}/>
            ))}
          </div>
        </section>
      )}

      {isPostSelect && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
              <span className="text-xs text-zinc-500">
                {status === 'strategizing' ? 'Strategist planning outreach...' : 'Writer drafting email...'}
              </span>
            </div>
            <div className="card h-64 animate-shimmer bg-gradient-to-r from-[#fffdf8] via-[#ece8df] to-[#fffdf8] bg-[length:200%_100%]"/>
          </div>
          <div className="card h-64 animate-shimmer bg-gradient-to-r from-[#fffdf8] via-[#ece8df] to-[#fffdf8] bg-[length:200%_100%]"/>
        </div>
      )}

      {status === 'done' && strategy && draft && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-text-1">Outreach ready</h2>
            <span className="text-xs text-text-2">edit the draft, then log or send</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StrategyPanel strategy={strategy}/>
            <EmailDraftPanel draft={draft} onEdit={setDraft} onLog={logToWandb}/>
          </div>
        </section>
      )}

      {Object.keys(supervisorScores).length > 0 && <SupervisorPanel scores={supervisorScores}/>}
      <WandbTrackerPanel runs={wandbRuns}/>
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
            {(['search', 'os', 'demo'] as AppMode[]).map(item => (
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

      <main className="relative z-10 mx-auto w-full max-w-[1620px] flex-1 px-4 pb-10 sm:px-6">
        {mode === 'search' ? <SearchView /> : mode === 'demo' ? <HarnessDemo /> : <PacketStudio />}
      </main>

      <footer className="relative z-10 px-6 py-4 text-center">
        <p className="text-xs text-zinc-400">
          UpSearch + Opportunity OS &nbsp;·&nbsp; Action over analysis.
        </p>
      </footer>
    </div>
  )
}
