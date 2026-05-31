import Header from './components/Header'
import SearchPanel from './components/SearchPanel'
import PipelineStepper from './components/PipelineStepper'
import OpportunityCard from './components/OpportunityCard'
import StrategyPanel from './components/StrategyPanel'
import EmailDraftPanel from './components/EmailDraftPanel'
import WandbTrackerPanel from './components/WandbTrackerPanel'
import { usePipeline } from './hooks/usePipeline'
import type { FilterKey } from './types'

export default function App() {
  const {
    status,
    agentStatuses,
    opportunities,
    selectedOpportunity,
    strategy,
    draft,
    wandbRuns,
    startPipeline,
    selectOpportunity,
    setDraft,
    logToWandb,
    reset,
  } = usePipeline()

  const isRunning = status === 'scouting' || status === 'analyzing'
  const isPostSelect = status === 'strategizing' || status === 'writing'

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleRun = (topic: string, _filters: FilterKey[]) => {
    // TODO: pass filters to the backend API when connected
    startPipeline(topic)
  }

  return (
    <div className="min-h-screen flex flex-col relative">
      <Header onReset={reset} />

      <main className="flex-1 relative z-10 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 space-y-6">

        {/* ── Search ──────────────────────────────────────────────────────── */}
        <SearchPanel onRun={handleRun} isRunning={isRunning || isPostSelect} />

        {/* ── Pipeline stepper (always shown once pipeline starts) ─────── */}
        {status !== 'idle' && (
          <PipelineStepper
            agentStatuses={agentStatuses}
            opportunityCount={opportunities.length}
          />
        )}

        {/* ── Loading skeleton while scouting ─────────────────────────── */}
        {status === 'scouting' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-xs text-zinc-500">Scout Agent searching Reddit and Hacker News...</span>
            </div>
            {[0, 1, 2].map((i) => (
              <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
            ))}
          </div>
        )}

        {/* ── Analyzing skeleton ───────────────────────────────────────── */}
        {status === 'analyzing' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-xs text-zinc-500">Analyst Agent scoring opportunities...</span>
            </div>
            {opportunities.slice(0, 3).map((_, i) => (
              <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]" />
            ))}
          </div>
        )}

        {/* ── Opportunities grid ───────────────────────────────────────── */}
        {(status === 'selecting' || status === 'strategizing' || status === 'writing' || status === 'done') &&
          opportunities.length > 0 && (
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

        {/* ── Strategist/Writer loading ────────────────────────────────── */}
        {(status === 'strategizing' || status === 'writing') && (
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

        {/* ── Strategy + Email side by side ────────────────────────────── */}
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

        {/* ── W&B Tracker (always visible with historical runs) ────────── */}
        <WandbTrackerPanel runs={wandbRuns} />

      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-zinc-800/50 py-4 px-6 text-center">
        <p className="text-xs text-zinc-700">
          UpSearch &nbsp;·&nbsp; Claude Opus 4.8 + W&amp;B &nbsp;·&nbsp;{' '}
          <span className="text-zinc-600">Action over analysis.</span>
        </p>
      </footer>
    </div>
  )
}
