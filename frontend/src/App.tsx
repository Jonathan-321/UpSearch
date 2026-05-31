import Header from './components/Header'
import SearchPanel from './components/SearchPanel'
import PipelineStepper from './components/PipelineStepper'
import OpportunityCard from './components/OpportunityCard'
import StrategyPanel from './components/StrategyPanel'
import EmailDraftPanel from './components/EmailDraftPanel'
import WandbTrackerPanel from './components/WandbTrackerPanel'
import SupervisorPanel from './components/SupervisorPanel'
import { usePipeline } from './hooks/usePipeline'
import type { FilterKey } from './types'

export default function App() {
  const {
    status,
    error,
    agentStatuses,
    opportunities,
    selectedOpportunity,
    strategy,
    draft,
    supervisorScores,
    wandbRuns,
    startPipeline,
    selectOpportunity,
    setDraft,
    logToWandb,
    reset,
  } = usePipeline()

  const isRunning = status === 'scouting' || status === 'analyzing'
  const isPostSelect = status === 'strategizing' || status === 'writing'

  const handleRun = (topic: string, _filters: FilterKey[]) => {
    const mode = _filters.includes('engineers') || _filters.includes('startups') ? 'jobs' : 'jobs'
    startPipeline(topic, mode)
  }

  return (
    <div className="min-h-screen flex flex-col relative">
      <Header onReset={reset} />

      <main className="flex-1 relative z-10 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 space-y-6">

        {/* Search */}
        <SearchPanel onRun={handleRun} isRunning={isRunning || isPostSelect} />

        {/* Pipeline stepper */}
        {status !== 'idle' && (
          <PipelineStepper
            agentStatuses={agentStatuses}
            opportunityCount={opportunities.length}
          />
        )}

        {/* Error state */}
        {status === 'error' && error && (
          <div className="card border-red-500/30 bg-red-500/5 p-5 flex items-start gap-3 animate-fade-in-up">
            <svg className="w-5 h-5 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-400">Pipeline error</p>
              <p className="text-xs text-zinc-400 mt-0.5">{error}</p>
              <p className="text-xs text-zinc-600 mt-1">
                Make sure the API server is running:&nbsp;
                <code className="text-zinc-400">uvicorn server:app --reload --port 8000</code>
              </p>
            </div>
          </div>
        )}

        {/* Scouting skeleton */}
        {status === 'scouting' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-xs text-zinc-500">Scout Agent searching Reddit and Hacker News...</span>
            </div>
            {[0, 1, 2].map(i => (
              <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
            ))}
          </div>
        )}

        {/* Analyzing skeleton */}
        {status === 'analyzing' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-xs text-zinc-500">Analyst Agent scoring opportunities...</span>
            </div>
            {[0, 1, 2].map(i => (
              <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
            ))}
          </div>
        )}

        {/* Opportunities grid */}
        {['selecting', 'strategizing', 'writing', 'done'].includes(status) && opportunities.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-sm font-semibold text-zinc-300">
                {opportunities.length} opportunities ranked by fit
              </h2>
              <span className="text-xs text-zinc-600">— click any to build outreach</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {opportunities.map((opp, i) => (
                <OpportunityCard
                  key={opp.post.id}
                  opportunity={opp}
                  index={i}
                  isSelected={selectedOpportunity?.post.id === opp.post.id}
                  onSelect={selectOpportunity}
                />
              ))}
            </div>
          </section>
        )}

        {/* Strategist / Writer loading */}
        {isPostSelect && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                <span className="text-xs text-zinc-500">
                  {status === 'strategizing' ? 'Strategist Agent planning outreach...' : 'Writer Agent drafting email...'}
                </span>
              </div>
              <div className="card h-64 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
            </div>
            <div className="card h-64 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
          </div>
        )}

        {/* Strategy + Email */}
        {status === 'done' && strategy && draft && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-sm font-semibold text-zinc-300">Outreach ready</h2>
              <span className="text-xs text-zinc-600">— edit the draft, then log or send</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StrategyPanel strategy={strategy} />
              <EmailDraftPanel draft={draft} onEdit={setDraft} onLog={logToWandb} />
            </div>
          </section>
        )}

        {/* Supervisor scores — shown as soon as any score arrives */}
        {Object.keys(supervisorScores).length > 0 && (
          <SupervisorPanel scores={supervisorScores} />
        )}

        {/* W&B tracker — always visible */}
        <WandbTrackerPanel runs={wandbRuns} />

      </main>

      <footer className="relative z-10 border-t border-zinc-800/50 py-4 px-6 text-center">
        <p className="text-xs text-zinc-700">
          UpSearch &nbsp;·&nbsp; Claude Opus 4.8 + DeepSeek + W&amp;B &nbsp;·&nbsp;
          <span className="text-zinc-600">Action over analysis.</span>
        </p>
      </footer>
    </div>
  )
}
