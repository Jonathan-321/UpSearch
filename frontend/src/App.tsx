import { useState, useEffect } from 'react'

// UpSearch pipeline
import Header from './components/Header'
import SearchPanel from './components/SearchPanel'
import PipelineStepper from './components/PipelineStepper'
import OpportunityCard from './components/OpportunityCard'
import StrategyPanel from './components/StrategyPanel'
import EmailDraftPanel from './components/EmailDraftPanel'
import WandbTrackerPanel from './components/WandbTrackerPanel'
import SupervisorPanel from './components/SupervisorPanel'
import { usePipeline } from './hooks/usePipeline'

// OS pipeline
import OSSearchPanel from './components/OSSearchPanel'
import OSPipelineStepper from './components/OSPipelineStepper'
import CRMTable from './components/CRMTable'
import PacketView from './components/PacketView'
import ApprovalQueue from './components/ApprovalQueue'
import { useOS } from './hooks/useOS'

import type { FilterKey } from './types'

type AppMode = 'search' | 'os'

function ModeToggle({ mode, onChange }: { mode: AppMode; onChange: (m: AppMode) => void }) {
  return (
    <div className="flex items-center gap-1 p-1 bg-zinc-900 border border-zinc-800 rounded-lg">
      {(['search', 'os'] as AppMode[]).map(m => (
        <button key={m} onClick={() => onChange(m)}
          className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
            mode === m
              ? 'bg-violet-600 text-white shadow-sm'
              : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          {m === 'search' ? 'Quick Search' : 'Opportunity OS'}
        </button>
      ))}
    </div>
  )
}

// ── Quick-Search view (original UpSearch) ─────────────────────────────────────
function SearchView({ onReset }: { onReset: () => void }) {
  const {
    status, error, agentStatuses, opportunities, selectedOpportunity,
    strategy, draft, supervisorScores, wandbRuns,
    startPipeline, selectOpportunity, setDraft, logToWandb, reset,
  } = usePipeline()

  const isRunning  = status === 'scouting' || status === 'analyzing'
  const isPostSelect = status === 'strategizing' || status === 'writing'

  const handleRun = (topic: string, _filters: FilterKey[]) => startPipeline(topic)
  const handleReset = () => { reset(); onReset() }

  return (
    <div className="space-y-6">
      <SearchPanel onRun={handleRun} isRunning={isRunning || isPostSelect} />

      {status !== 'idle' && (
        <PipelineStepper agentStatuses={agentStatuses} opportunityCount={opportunities.length} />
      )}

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
    pendingMessages, error,
    buildPacket, fetchCompanies, fetchPending, approveMessage, selectCompany,
  } = useOS()

  useEffect(() => {
    fetchCompanies()
    fetchPending()
  }, [fetchCompanies, fetchPending])

  return (
    <div className="space-y-6">
      <OSSearchPanel onBuild={buildPacket} isRunning={running}/>

      {error && (
        <div className="card border-red-500/30 bg-red-500/5 p-4 text-xs text-red-400 animate-fade-in-up">
          {error} — make sure uvicorn is running on port 8000.
        </div>
      )}

      {currentCompany && (
        <OSPipelineStepper stages={stages} currentCompany={currentCompany}/>
      )}

      {/* Two-column: CRM left, Packet right */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CRMTable companies={companies} currentCompany={currentCompany} onSelect={selectCompany}/>

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
            <div className="relative w-9 h-9">
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-700
                              shadow-lg shadow-violet-950/60"/>
              <div className="absolute inset-0 rounded-xl flex items-center justify-center">
                <svg width="17" height="17" viewBox="0 0 16 16" fill="none">
                  <circle cx="6" cy="6" r="3.5" stroke="white" strokeWidth="1.5"/>
                  <line x1="9" y1="9" x2="13.5" y2="13.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
                  <line x1="6" y1="3" x2="6" y2="9" stroke="rgba(255,255,255,0.6)" strokeWidth="1.2" strokeLinecap="round"/>
                  <line x1="3" y1="6" x2="9" y2="6" stroke="rgba(255,255,255,0.6)" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold leading-none gradient-text">UpSearch</span>
              <span className="text-[10px] text-zinc-600 font-medium mt-0.5 tracking-wide">
                {mode === 'os' ? 'Opportunity Intelligence OS' : 'Quick Research Search'}
              </span>
            </div>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center bg-white/[0.03] border border-white/[0.07] rounded-xl p-1 gap-1">
            {(['search', 'os'] as AppMode[]).map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-200 ${
                  mode === m
                    ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-violet-950/50'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {m === 'search' ? 'Quick Search' : 'Opportunity OS'}
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
        {mode === 'search' ? <SearchView onReset={() => {}} /> : <OSView />}
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
