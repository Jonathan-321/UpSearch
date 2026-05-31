import { useState, useEffect } from 'react'

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

// OS pipeline
import OSSearchPanel from './components/OSSearchPanel'
import OSPipelineStepper from './components/OSPipelineStepper'
import CRMTable from './components/CRMTable'
import PacketView from './components/PacketView'
import ApprovalQueue from './components/ApprovalQueue'
import HarnessDemo from './components/HarnessDemo'
import { useOS } from './hooks/useOS'

import type { FilterKey } from './types'

type AppMode = 'search' | 'os' | 'demo'

const modeLabels: Record<AppMode, string> = {
  search: 'Quick Search',
  os: 'Opportunity OS',
  demo: 'Harness Demo',
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
    <div className="space-y-6">
      <section>
        <p className="workspace-label">Quick Search</p>
        <h1 className="text-workspace mt-2">Turn public signals into credible outreach.</h1>
        <p className="text-body text-text-2 mt-2 max-w-3xl">
          Search technical communities, rank useful leads, and draft a specific first note.
        </p>
      </section>

      <SearchPanel onRun={handleRun} isRunning={isPipelineActive} />

      {status !== 'idle' && (
        <PipelineStepper agentStatuses={agentStatuses} opportunityCount={opportunities.length} />
      )}

      <ActivityConsole entries={logEntries} isRunning={isPipelineActive} />

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
          {[0,1,2].map(i => <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]"/>)}
        </div>
      )}

      {status === 'analyzing' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
            <span className="text-xs text-zinc-500">Analyst Agent scoring opportunities...</span>
          </div>
          {[0,1,2].map(i => <div key={i} className="card h-36 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]"/>)}
        </div>
      )}

      {['selecting','strategizing','writing','done'].includes(status) && opportunities.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-zinc-300">{opportunities.length} opportunities ranked by fit</h2>
            <span className="text-xs text-zinc-600">— click any to build outreach</span>
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
            <div className="card h-64 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]"/>
          </div>
          <div className="card h-64 animate-shimmer bg-gradient-to-r from-zinc-900 via-zinc-800/40 to-zinc-900 bg-[length:200%_100%]"/>
        </div>
      )}

      {status === 'done' && strategy && draft && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-zinc-300">Outreach ready</h2>
            <span className="text-xs text-zinc-600">— edit the draft, then log or send</span>
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

// ── Opportunity OS view ───────────────────────────────────────────────────────
function OSView() {
  const {
    running, stages, companies, currentCompany, currentPacket,
    pendingMessages, error, logEntries,
    buildPacket, fetchCompanies, fetchPending, approveMessage, selectCompany,
  } = useOS()

  useEffect(() => {
    fetchCompanies()
    fetchPending()
  }, [fetchCompanies, fetchPending])

  return (
    <div className="space-y-6">
      <section>
        <p className="workspace-label">Opportunity Intelligence OS</p>
        <h1 className="text-workspace mt-2">Build a sharper case before you reach out.</h1>
        <p className="text-body text-text-2 mt-2 max-w-3xl">
          Research a company, isolate real technical problems, map the right people, and review every note before it leaves your desk.
        </p>
      </section>

      <OSSearchPanel onBuild={buildPacket} isRunning={running}/>

      {error && (
        <div className="card border-red-500/30 bg-red-500/5 p-4 text-xs text-red-400 animate-fade-in-up">
          {error} — make sure uvicorn is running on port 8000.
        </div>
      )}

      {currentCompany && (
        <OSPipelineStepper stages={stages} currentCompany={currentCompany}/>
      )}

      <ActivityConsole entries={logEntries} isRunning={running} />

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(280px,0.82fr)_minmax(0,1.6fr)] gap-6 items-start">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <CRMTable companies={companies} currentCompany={currentCompany} onSelect={selectCompany} />
        </div>

        {currentPacket?.packet ? (
          <PacketView
            company={currentCompany}
            packet={currentPacket.packet}
            problems={currentPacket.problems}
            people={currentPacket.people}
          />
        ) : currentCompany ? (
          <div className="card p-6 flex items-center justify-center text-zinc-600 text-sm">
            {running ? 'Building packet...' : 'Select a company from the CRM to view its packet.'}
          </div>
        ) : null}
      </div>

      {pendingMessages.length > 0 && (
        <ApprovalQueue messages={pendingMessages} onApprove={approveMessage}/>
      )}
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [mode, setMode] = useState<AppMode>('os')

  return (
    <div className="min-h-screen flex flex-col relative">

      {/* Header */}
      <header className="relative z-10 border-b border-white/[0.05] bg-[#080810]/80 backdrop-blur-xl">
        {/* Gradient line at very top */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent"/>

        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg border border-amber-500/40 bg-amber-500/10 flex items-center justify-center text-amber-400" aria-hidden="true">
              <svg width="17" height="17" viewBox="0 0 16 16" fill="none">
                <circle cx="6" cy="6" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                <line x1="9" y1="9" x2="13.5" y2="13.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                <line x1="6" y1="3" x2="6" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="3" y1="6" x2="9" y2="6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
            </div>
            <p className="text-base font-bold leading-none text-text-1">UpSearch</p>
          </div>

          <div role="group" aria-label="Application mode" className="flex items-center bg-surface border border-border rounded-lg p-1 gap-1">
            {(['search', 'os', 'demo'] as AppMode[]).map(item => (
              <button key={item} onClick={() => setMode(item)}
                aria-pressed={mode === item}
                className={`px-3 sm:px-4 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  mode === item ? 'bg-accent text-[#1a1205]' : 'text-text-2 hover:text-text-1'
                }`}>
                {modeLabels[item]}
              </button>
            ))}
          </div>

          {/* Status pill */}
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-white/[0.07]
                          bg-white/[0.02] text-xs text-zinc-500 font-medium">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping-slow absolute inline-flex h-full w-full rounded-full bg-violet-500 opacity-50"/>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"/>
            </span>
            DeepSeek · Claude · W&amp;B
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 relative z-10 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8">
        {mode === 'search' ? <SearchView /> : mode === 'demo' ? <HarnessDemo /> : <OSView />}
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/[0.04] py-4 px-6 text-center">
        <p className="text-xs text-zinc-800">
          UpSearch + Opportunity OS &nbsp;·&nbsp; Action over analysis.
        </p>
      </footer>
    </div>
  )
}
