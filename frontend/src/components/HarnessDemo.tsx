import { useEffect, useMemo, useState } from 'react'
import {
  demoSeed,
  harnessAdapters,
  ledgerEvents,
  packet,
  people,
  traces,
  type AgentTrace,
  type DemoStatus,
} from '../demoData'

const statusClasses: Record<DemoStatus, string> = {
  waiting: 'border-white/[0.06] bg-white/[0.02] text-zinc-500',
  running: 'border-sky-500/40 bg-sky-500/10 text-sky-300 ring-running',
  complete: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 ring-done',
}

function statusFor(index: number, current: number, running: boolean): DemoStatus {
  if (!running) return 'waiting'
  if (index < current) return 'complete'
  if (index === current) return current === traces.length - 1 ? 'complete' : 'running'
  return 'waiting'
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-1 text-base font-semibold text-zinc-100">{value}</p>
    </div>
  )
}

function TraceCard({ trace, status }: { trace: AgentTrace; status: DemoStatus }) {
  return (
    <article className={`rounded-xl border p-4 transition-all duration-300 ${statusClasses[status]}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                status === 'complete'
                  ? 'bg-emerald-400'
                  : status === 'running'
                    ? 'animate-pulse bg-sky-400'
                    : 'bg-zinc-700'
              }`}
            />
            <h3 className="text-sm font-semibold text-zinc-100">{trace.name}</h3>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500">{trace.goal}</p>
        </div>
        <span className="rounded-full border border-white/[0.07] bg-black/30 px-2.5 py-1 text-[11px] text-zinc-400">
          {trace.modelClass}
        </span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="section-label">Allowed tools</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {trace.tools.map((tool) => (
              <span key={tool} className="rounded-md border border-white/[0.06] bg-black/25 px-2 py-1 text-xs text-zinc-300">
                {tool}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="section-label">Trace summary</p>
          <p className="mt-2 text-xs leading-relaxed text-zinc-300">{trace.output}</p>
        </div>
      </div>

      <div className="mt-4 border-t border-white/[0.06] pt-3">
        <p className="section-label">Validators</p>
        <div className="mt-2 grid gap-1.5 sm:grid-cols-3">
          {trace.validators.map((validator) => (
            <span key={validator} className="rounded-md bg-black/25 px-2 py-1 text-xs text-zinc-500">
              {validator}
            </span>
          ))}
        </div>
      </div>
    </article>
  )
}

function HarnessAdapters() {
  return (
    <section className="card p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="section-label">Replaceable harness layer</p>
          <h2 className="mt-1 text-lg font-semibold text-zinc-100">
            Claude Code, Codex, and open-source runners become adapters
          </h2>
        </div>
        <span className="rounded-full border border-white/[0.07] bg-black/30 px-3 py-1 text-xs text-zinc-500">
          tool layer, not product core
        </span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {harnessAdapters.map((adapter) => (
          <article key={adapter.name} className="rounded-xl border border-white/[0.06] bg-black/20 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-100">{adapter.name}</h3>
                <p className="mt-1 text-xs text-sky-300">{adapter.role}</p>
              </div>
              <span className="rounded-md bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">adapter</span>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-zinc-300">
              <span className="font-semibold text-zinc-100">Best for: </span>
              {adapter.bestFor}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-zinc-500">
              <span className="font-semibold text-zinc-300">Keep out: </span>
              {adapter.keepOut}
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}

function PacketPanel({ approved, onApprove }: { approved: boolean; onApprove: () => void }) {
  return (
    <aside className="space-y-4">
      <section className="card p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="section-label">Recommended packet</p>
            <h2 className="mt-1 text-xl font-semibold text-zinc-100">{packet.company}</h2>
          </div>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
            QA passed
          </span>
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <p className="section-label">Problem</p>
            <p className="mt-1 text-sm leading-relaxed text-zinc-200">{packet.problem}</p>
          </div>
          <div>
            <p className="section-label">Artifact</p>
            <p className="mt-1 text-sm leading-relaxed text-zinc-300">{packet.artifactSummary}</p>
          </div>
          <div>
            <p className="section-label">Adjacent proof</p>
            <p className="mt-1 text-sm leading-relaxed text-zinc-300">{packet.proof}</p>
          </div>
        </div>
      </section>

      <section className="card p-5">
        <p className="section-label">People map</p>
        <div className="mt-4 space-y-3">
          {people.map((person) => (
            <div key={person.name} className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-zinc-100">{person.name}</p>
                  <p className="text-xs text-zinc-500">{person.role}</p>
                </div>
                <span className="rounded-md bg-sky-500/10 px-2 py-1 text-xs text-sky-300">{person.channel}</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">{person.why}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
        <p className="section-label text-amber-300">Decision inbox</p>
        <h3 className="mt-1 text-sm font-semibold text-zinc-100">Approve exact LinkedIn note?</h3>
        <p className="mt-3 rounded-xl border border-amber-500/20 bg-black/30 p-3 text-sm leading-relaxed text-zinc-200">
          {packet.message}
        </p>
        <button
          type="button"
          onClick={onApprove}
          disabled={approved}
          className="mt-4 w-full rounded-xl border border-amber-400/40 bg-amber-400/15 px-4 py-2 text-sm font-semibold text-amber-200 transition hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:border-emerald-500/30 disabled:bg-emerald-500/10 disabled:text-emerald-300"
        >
          {approved ? 'Approved. Action connector can proceed.' : 'Approve exact action'}
        </button>
        <p className="mt-2 text-xs text-amber-200/70">
          External sends stay blocked until target, channel, body, attachment, and timing match approval.
        </p>
      </section>
    </aside>
  )
}

function Ledger({ started, approved }: { started: boolean; approved: boolean }) {
  const rows = useMemo(
    () => (approved ? [...ledgerEvents, { event: 'approval.recorded', agent: 'action', status: 'approved', cost: '$0.0000' }] : ledgerEvents),
    [approved],
  )

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-zinc-100">W&amp;B-style run ledger</p>
          <p className="text-xs text-zinc-600">Local demo events now. Real W&amp;B sync later.</p>
        </div>
        <span className="rounded-full border border-white/[0.07] bg-black/30 px-3 py-1 text-xs text-zinc-500">
          {started ? rows.length : 0} events
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-600">
            <tr>
              <th className="px-5 py-3 font-semibold uppercase tracking-wide">Event</th>
              <th className="px-5 py-3 font-semibold uppercase tracking-wide">Agent</th>
              <th className="px-5 py-3 font-semibold uppercase tracking-wide">Status</th>
              <th className="px-5 py-3 font-semibold uppercase tracking-wide">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.06]">
            {(started ? rows : []).map((row) => (
              <tr key={`${row.event}-${row.status}`} className="text-zinc-300">
                <td className="px-5 py-3 font-mono text-zinc-200">{row.event}</td>
                <td className="px-5 py-3">{row.agent}</td>
                <td className="px-5 py-3">{row.status}</td>
                <td className="px-5 py-3 font-mono text-zinc-600">{row.cost}</td>
              </tr>
            ))}
            {!started && (
              <tr>
                <td className="px-5 py-6 text-center text-zinc-700" colSpan={4}>
                  Run the demo to emit ledger events.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function HarnessDemo() {
  const [running, setRunning] = useState(false)
  const [current, setCurrent] = useState(0)
  const [approved, setApproved] = useState(false)

  useEffect(() => {
    if (!running || current >= traces.length - 1) return
    const timer = window.setTimeout(() => setCurrent((value) => value + 1), 700)
    return () => window.clearTimeout(timer)
  }, [running, current])

  const completedCount = running ? Math.min(current + 1, traces.length) : 0

  const start = () => {
    setApproved(false)
    setCurrent(0)
    setRunning(true)
  }

  const reset = () => {
    setRunning(false)
    setCurrent(0)
    setApproved(false)
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="card p-6">
          <p className="section-label">Smallest useful demo</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-50">
            From broad interest to company-specific technical packet.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-zinc-400">
            This demo shows the harness pattern: each agent gets a goal, allowed tools, model route,
            validators, and a ledger event. It shows trace summaries and outputs, not hidden chain-of-thought.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Seed lane" value={demoSeed.lane} />
            <Metric label="Target" value={demoSeed.company} />
            <Metric label="Trace events" value={`${completedCount}/${traces.length}`} />
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" onClick={start} className="btn-primary">
              Run agent demo
            </button>
            <button
              type="button"
              onClick={reset}
              className="rounded-xl border border-white/[0.07] bg-black/20 px-4 py-2 text-sm font-semibold text-zinc-300 transition hover:bg-white/[0.04]"
            >
              Reset
            </button>
          </div>
        </div>

        <div className="card p-6">
          <p className="section-label">What this proves</p>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-zinc-300">
            <li>1. Agents coordinate through typed state, not free-form chat.</li>
            <li>2. Cheap models can do broad work when the harness is strict.</li>
            <li>3. External actions stay blocked until explicit approval.</li>
            <li>4. If a connector fails, the packet is still usable manually.</li>
          </ul>
        </div>
      </section>

      <HarnessAdapters />

      <section className="grid gap-6 lg:grid-cols-[1fr_420px]">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="section-label">Agent coordination trail</p>
              <h2 className="text-lg font-semibold text-zinc-100">Harnessed task sequence</h2>
            </div>
            <span className="rounded-full border border-white/[0.07] bg-black/20 px-3 py-1 text-xs text-zinc-500">
              {running ? 'running demo' : 'waiting'}
            </span>
          </div>
          {traces.map((trace, index) => (
            <TraceCard key={trace.id} trace={trace} status={statusFor(index, current, running)} />
          ))}
        </div>

        <PacketPanel approved={approved} onApprove={() => setApproved(true)} />
      </section>

      <Ledger started={running} approved={approved} />
    </div>
  )
}
