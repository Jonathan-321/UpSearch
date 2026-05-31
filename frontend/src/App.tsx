import { useEffect, useState } from 'react'
import SearchPanel from './components/SearchPanel'
import PipelineStepper from './components/PipelineStepper'
import OpportunityCard from './components/OpportunityCard'
import StrategyPanel from './components/StrategyPanel'
import EmailDraftPanel from './components/EmailDraftPanel'
import WandbTrackerPanel from './components/WandbTrackerPanel'
import SupervisorPanel from './components/SupervisorPanel'
import ActivityConsole from './components/ActivityConsole'
import { usePipeline } from './hooks/usePipeline'
import OSSearchPanel from './components/OSSearchPanel'
import OSPipelineStepper from './components/OSPipelineStepper'
import CRMTable from './components/CRMTable'
import PacketView from './components/PacketView'
import ApprovalQueue from './components/ApprovalQueue'
import { useOS } from './hooks/useOS'
import type { FilterKey } from './types'

type AppMode = 'search' | 'os'

function SearchView() {
  const {
    status, error, agentStatuses, opportunities, selectedOpportunity,
    strategy, draft, supervisorScores, wandbRuns, logEntries,
    startPipeline, selectOpportunity, setDraft, logToWandb,
  } = usePipeline()

  const isRunning = status === 'scouting' || status === 'analyzing'
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
        <div className="panel border-red-500/30 bg-red-500/5 p-5 flex items-start gap-3">
          <span className="text-red-400 font-bold">!</span>
          <div>
            <p className="text-sm font-semibold text-red-400">Pipeline error</p>
            <p className="text-sm text-text-2 mt-1">{error}</p>
            <p className="text-xs text-text-3 mt-2">
              Make sure the API server is running: <code className="text-text-2">uvicorn server:app --reload --port 8000</code>
            </p>
          </div>
        </div>
      )}

      {(status === 'scouting' || status === 'analyzing') && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-text-2">
            <span className="status-dot bg-amber-400 animate-pulse" />
            {status === 'scouting'
              ? 'Scout Agent is searching Reddit and Hacker News'
              : 'Analyst Agent is scoring opportunities'}
          </div>
          {[0, 1, 2].map(i => <div key={i} className="panel skeleton h-32" />)}
        </div>
      )}

      {['selecting', 'strategizing', 'writing', 'done'].includes(status) && opportunities.length > 0 && (
        <section>
          <div className="flex flex-wrap items-end justify-between gap-2 mb-4">
            <div>
              <p className="workspace-label">Ranked Leads</p>
              <h2 className="text-section mt-1">{opportunities.length} opportunities worth reviewing</h2>
            </div>
            <span className="text-meta">Choose a lead to build outreach</span>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {opportunities.map((opp, i) => (
              <OpportunityCard key={opp.post.id} opportunity={opp} index={i}
                isSelected={selectedOpportunity?.post.id === opp.post.id} onSelect={selectOpportunity} />
            ))}
          </div>
        </section>
      )}

      {isPostSelect && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <p className="text-sm text-text-2">
              {status === 'strategizing' ? 'Strategist is planning outreach' : 'Writer is drafting the note'}
            </p>
            <div className="panel skeleton h-64" />
          </div>
          <div className="panel skeleton h-64" />
        </div>
      )}

      {status === 'done' && strategy && draft && (
        <section>
          <div className="mb-4">
            <p className="workspace-label">Outreach Ready</p>
            <h2 className="text-section mt-1">Review the angle and edit the draft</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <StrategyPanel strategy={strategy} />
            <EmailDraftPanel draft={draft} onEdit={setDraft} onLog={logToWandb} />
          </div>
        </section>
      )}

      {Object.keys(supervisorScores).length > 0 && <SupervisorPanel scores={supervisorScores} />}
      <WandbTrackerPanel runs={wandbRuns} />
    </div>
  )
}

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

      <OSSearchPanel onBuild={buildPacket} isRunning={running} />

      {error && (
        <div className="panel border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
          {error}. Make sure uvicorn is running on port 8000.
        </div>
      )}

      {currentCompany && <OSPipelineStepper stages={stages} currentCompany={currentCompany} />}

      <ActivityConsole entries={logEntries} isRunning={running} />

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(280px,0.82fr)_minmax(0,1.6fr)] gap-6 items-start">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <CRMTable companies={companies} currentCompany={currentCompany} onSelect={selectCompany} />
        </div>
        {currentPacket?.packet ? (
          <PacketView company={currentCompany} packet={currentPacket.packet}
            problems={currentPacket.problems} people={currentPacket.people} />
        ) : currentCompany ? (
          <div className="panel p-8 min-h-48 flex items-center justify-center text-text-3 text-sm">
            {running ? 'Building packet...' : 'Select a company from the CRM to view its packet.'}
          </div>
        ) : (
          <div className="panel p-8 min-h-48 flex items-center justify-center text-text-3 text-sm">
            Build your first packet to open the intelligence workspace.
          </div>
        )}
      </div>

      <ApprovalQueue messages={pendingMessages} onApprove={approveMessage} />
    </div>
  )
}

export default function App() {
  const [mode, setMode] = useState<AppMode>('os')

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-bg/95">
        <div className="max-w-[1480px] mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4">
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
            {(['search', 'os'] as AppMode[]).map(item => (
              <button key={item} onClick={() => setMode(item)}
                aria-pressed={mode === item}
                className={`px-3 sm:px-4 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  mode === item ? 'bg-accent text-[#1a1205]' : 'text-text-2 hover:text-text-1'
                }`}>
                {item === 'search' ? 'Quick Search' : 'Opportunity OS'}
              </button>
            ))}
          </div>

          <div className="hidden sm:flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-surface text-xs text-text-2">
            <span className="status-dot bg-success" />
            DeepSeek / Claude / W&amp;B
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1480px] mx-auto w-full px-4 sm:px-6 py-8 animate-reveal">
        {mode === 'search' ? <SearchView /> : <OSView />}
      </main>

      <footer className="border-t border-border py-4 px-6 text-center">
        <p className="text-xs text-text-3">UpSearch + Opportunity OS / Action over analysis.</p>
      </footer>
    </div>
  )
}
