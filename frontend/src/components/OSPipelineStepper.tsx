import type { OSStage } from '../hooks/useOS'

interface Props {
  stages: OSStage[]
  currentCompany: string
}

const ICONS: Record<string, JSX.Element> = {
  profile:        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><circle cx="12" cy="8" r="4"/><path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>,
  company:        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16M3 21h18M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>,
  problem:        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>,
  people:         <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>,
  technical_note: <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>,
  outreach:       <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>,
  qa:             <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}><path strokeLinecap="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
}

const CHECK = (
  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
  </svg>
)

export default function OSPipelineStepper({ stages, currentCompany }: Props) {
  if (!currentCompany) return null

  const doneCount  = stages.filter(s => s.status === 'complete').length
  const totalCount = stages.length
  const pct        = Math.round((doneCount / totalCount) * 100)

  return (
    <section className="card p-5 animate-fade-in-up space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-violet-500 animate-ping-slow" />
          <span className="text-xs font-bold text-zinc-300 uppercase tracking-widest">
            OS Pipeline — {currentCompany}
          </span>
        </div>
        <span className="text-xs tabular-nums text-zinc-500">
          {doneCount}/{totalCount} stages · {pct}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-600 to-cyan-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stage row */}
      <div className="flex items-start gap-0">
        {stages.map((stage, i) => {
          const isDone    = stage.status === 'complete'
          const isRunning = stage.status === 'running'
          const isError   = stage.status === 'error'
          const isLast    = i === stages.length - 1

          return (
            <div key={stage.key} className="flex items-start flex-1 min-w-0">
              {/* Stage column */}
              <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0 px-1">
                {/* Circle */}
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-300
                  ${isDone    ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-900/40' : ''}
                  ${isRunning ? 'bg-blue-600 text-white ring-running animate-glow-pulse' : ''}
                  ${isError   ? 'bg-red-600/80 text-white' : ''}
                  ${!isDone && !isRunning && !isError ? 'bg-zinc-800/80 text-zinc-600 border border-zinc-700' : ''}
                `}>
                  {isDone    ? CHECK : isRunning
                    ? <span className="w-2.5 h-2.5 rounded-full bg-white animate-pulse"/>
                    : <span className="text-xs font-bold">{i + 1}</span>
                  }
                </div>

                {/* Label */}
                <span className={`text-xs font-semibold text-center leading-tight truncate w-full
                  ${isDone ? 'text-zinc-300' : isRunning ? 'text-blue-300' : 'text-zinc-600'}`}>
                  {stage.label}
                </span>

                {/* Message */}
                {stage.message && (
                  <span className="text-xs text-zinc-500 text-center leading-tight truncate w-full"
                    title={stage.message}>
                    {stage.message}
                  </span>
                )}
              </div>

              {/* Connector */}
              {!isLast && (
                <div className="flex items-center mt-4 w-4 shrink-0">
                  <div className={`h-px w-full transition-colors duration-500 ${
                    isDone ? 'bg-emerald-500/40' : 'bg-zinc-800'
                  }`}/>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
