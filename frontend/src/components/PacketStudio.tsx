import { useEffect } from 'react'
import OSSearchPanel from './OSSearchPanel'
import CRMTable from './CRMTable'
import PacketView from './PacketView'
import ApprovalQueue from './ApprovalQueue'
import type { LogEntry } from '../types'
import { useOS, type OSStage } from '../hooks/useOS'

const STUDIO_STEPS = [
  { number: '01', label: 'Source', detail: 'company, roles, public signal' },
  { number: '02', label: 'Build', detail: 'problem, people, artifact' },
  { number: '03', label: 'Verify', detail: 'claims, tone, evidence' },
  { number: '04', label: 'Approve', detail: 'exact action gate' },
]

const RUN_STRIP = [
  { company: 'Baseten', lane: 'Inference systems', status: 'Now playing' },
  { company: 'Modal', lane: 'Serverless GPUs', status: 'Play next' },
  { company: 'Fireworks', lane: 'LoRA deployment', status: 'Play next' },
  { company: 'Together', lane: 'Speculative decoding', status: 'Play next' },
]

function stageCopy(stage: OSStage | undefined) {
  if (!stage) return 'Waiting for a packet run'
  if (stage.status === 'running') return `${stage.label} is working`
  if (stage.status === 'complete') return `${stage.label} complete`
  if (stage.status === 'error') return `${stage.label} needs attention`
  return stage.label
}

function StageRail({ stages }: { stages: OSStage[] }) {
  return (
    <aside className="studio-stage-rail" aria-label="Packet stages">
      {stages.map((stage, index) => {
        const active = stage.status === 'running'
        const done = stage.status === 'complete'
        const failed = stage.status === 'error'
        return (
          <div
            key={stage.key}
            className={`studio-stage-row ${active ? 'is-active' : ''} ${done ? 'is-done' : ''} ${failed ? 'is-failed' : ''}`}
          >
            <span className="studio-stage-number">{String(index + 1).padStart(2, '0')}</span>
            <div className="min-w-0">
              <p>{stage.label}</p>
              <span>{stage.message || stage.description}</span>
            </div>
          </div>
        )
      })}
    </aside>
  )
}

function StreamEvent({ entry }: { entry: LogEntry }) {
  return (
    <div className="stream-event">
      <div className="stream-event-meta">
        <span>{entry.ts}</span>
        <span>{entry.agent}</span>
        <strong>{entry.level}</strong>
      </div>
      <p>{entry.message}</p>
      {entry.elapsed && <span className="stream-event-time">{entry.elapsed}</span>}
    </div>
  )
}

function StreamPanel({ entries, running, activeStage }: { entries: LogEntry[]; running: boolean; activeStage?: OSStage }) {
  const visibleEntries = entries.slice(-6)

  return (
    <aside className="studio-stream-panel">
      <div className="studio-stream-header">
        <div>
          <p className="studio-kicker">Live stream</p>
          <h3>{stageCopy(activeStage)}</h3>
        </div>
        <span className={running ? 'studio-live-pill is-live' : 'studio-live-pill'}>
          {running ? 'Streaming' : 'Idle'}
        </span>
      </div>

      <div className="studio-stream-body">
        {visibleEntries.length > 0 ? (
          visibleEntries.map((entry, index) => <StreamEvent key={`${entry.ts}-${entry.agent}-${index}`} entry={entry} />)
        ) : (
          <div className="stream-empty">
            <p>Start a packet build to watch agents add evidence, people, drafts, and QA results here.</p>
          </div>
        )}
        {running && <div className="stream-cursor">writing packet state</div>}
      </div>
    </aside>
  )
}

function PacketPlaceholder({ currentCompany, running }: { currentCompany: string; running: boolean }) {
  return (
    <div className="packet-placeholder">
      <div className="packet-placeholder-header">
        <span>UPSEARCH PACKET</span>
        <strong>{currentCompany || 'Choose a company'}</strong>
      </div>
      <div className="packet-placeholder-grid">
        <div>
          <p className="studio-kicker">Problem frame</p>
          <h3>{running ? 'Extracting source-backed problems' : 'A technical packet will appear here'}</h3>
          <p>
            The canvas is reserved for the actual artifact: company fit, open problem, evidence, people,
            one-page note, drafts, and QA gate.
          </p>
        </div>
        <div className="packet-placeholder-lines" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  )
}

function RunStrip({ onSelect }: { onSelect: (company: string) => void }) {
  return (
    <section className="run-strip" aria-label="Packet replay queue">
      {RUN_STRIP.map((run, index) => (
        <button key={run.company} type="button" onClick={() => onSelect(run.company)} className="run-card">
          <span className="run-index">{String(index + 1).padStart(2, '0')}</span>
          <div>
            <p>{run.status}</p>
            <h3>{run.company}</h3>
            <span>{run.lane}</span>
          </div>
          <span className="run-play" aria-hidden="true">▶</span>
        </button>
      ))}
    </section>
  )
}

export default function PacketStudio() {
  const {
    running, stages, companies, currentCompany, currentPacket,
    pendingMessages, error, logEntries,
    buildPacket, fetchCompanies, fetchPending, approveMessage, selectCompany,
  } = useOS()

  useEffect(() => {
    fetchCompanies()
    fetchPending()
  }, [fetchCompanies, fetchPending])

  const doneCount = stages.filter(stage => stage.status === 'complete').length
  const activeStage = stages.find(stage => stage.status === 'running') || [...stages].reverse().find(stage => stage.status === 'complete')

  return (
    <div className="packet-studio">
      <section className="studio-hero">
        <div className="studio-hero-copy">
          <p className="studio-kicker">Opportunity packet studio</p>
          <h1>Watch a technical opportunity packet assemble from public signal.</h1>
          <p>
            Source the company, isolate a real problem, map the right people, write the artifact,
            verify the claims, and hold every external action behind approval.
          </p>
        </div>

        <div className="studio-hero-meter" aria-label="Current run summary">
          <span>{doneCount}/{stages.length}</span>
          <p>agent stages complete</p>
          <strong>{running ? 'Building live' : currentPacket?.packet ? 'Packet ready' : 'Ready'}</strong>
        </div>
      </section>

      <section className="studio-workbench">
        <div className="studio-step-grid">
          {STUDIO_STEPS.map(step => (
            <div key={step.number} className="studio-step">
              <span>{step.number}</span>
              <strong>{step.label}</strong>
              <p>{step.detail}</p>
            </div>
          ))}
        </div>

        <OSSearchPanel onBuild={buildPacket} isRunning={running} />

        {error && (
          <div className="studio-error">
            {error}. Make sure uvicorn is running on port 8000.
          </div>
        )}

        <div className="studio-cinema">
          <StageRail stages={stages} />

          <main className="studio-canvas" aria-label="Packet canvas">
            <div className="studio-canvas-bar">
              <div>
                <span>Packet canvas</span>
                <strong>{currentCompany || 'No company selected'}</strong>
              </div>
              <div className="studio-canvas-actions">
                <span>{currentPacket?.packet?.crm_status?.replace('_', ' ') || 'draft'}</span>
                <span>QA {currentPacket?.packet?.qa_score ?? '--'}/10</span>
              </div>
            </div>

            <div className="studio-canvas-body">
              {currentPacket?.packet ? (
                <PacketView
                  company={currentCompany}
                  packet={currentPacket.packet}
                  problems={currentPacket.problems}
                  people={currentPacket.people}
                />
              ) : (
                <PacketPlaceholder currentCompany={currentCompany} running={running} />
              )}
            </div>
          </main>

          <StreamPanel entries={logEntries} running={running} activeStage={activeStage} />
        </div>

        <RunStrip onSelect={selectCompany} />
      </section>

      <section className="studio-lower-grid">
        <CRMTable companies={companies} currentCompany={currentCompany} onSelect={selectCompany} />
        <ApprovalQueue messages={pendingMessages} onApprove={approveMessage} />
      </section>
    </div>
  )
}
