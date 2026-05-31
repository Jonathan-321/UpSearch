import type { OSStage } from '../hooks/useOS'

interface Props {
  stages: OSStage[]
  currentCompany: string
}

const ICONS: Record<string, React.ReactNode> = {
  profile: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><circle cx="12" cy="8" r="4"/><path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>,
  company: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16"/><path strokeLinecap="round" d="M3 21h18M9 7h1m-1 4h1m4-4h1m-1 4h1"/></svg>,
  problem: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>,
  people:  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>,
  technical_note: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>,
  outreach: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>,
  qa: <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
}

export default function OSPipelineStepper({ stages, currentCompany }: Props) {
  if (!currentCompany) return null

  const completedCount = stages.filter(s => s.status === 'complete').length

  return (
    <section className="animate-fade-in-up space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
          OS Pipeline — {currentCompany}
        </span>
        <span className="text-xs text-zinc-600">{completedCount}/{stages.length} stages</span>
      </div>

      {/* Mobile: vertical stack. Desktop: horizontal scroll */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {stages.map((stage) => {
          const isRunning = stage.status === 'running'
          const isDone = stage.status === 'complete'
          const isError = stage.status === 'error'

          return (
            <div key={stage.key}
              className={`card p-3 flex flex-col gap-2 transition-all duration-300
                ${isRunning ? 'border-blue-500/40 animate-glow-pulse' : ''}
                ${isDone    ? 'border-emerald-500/25' : ''}
                ${isError   ? 'border-red-500/30' : ''}`}
            >
              <div className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors
                ${isDone    ? 'bg-emerald-500/15 text-emerald-400' : ''}
                ${isRunning ? 'bg-blue-500/15 text-blue-400' : ''}
                ${isError   ? 'bg-red-500/15 text-red-400' : ''}
                ${stage.status === 'waiting' ? 'bg-zinc-800 text-zinc-500' : ''}`}
              >
                {ICONS[stage.key]}
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-200 leading-tight">{stage.label}</p>
                {stage.message ? (
                  <p className="text-xs text-zinc-500 mt-0.5 leading-snug truncate" title={stage.message}>
                    {stage.message}
                  </p>
                ) : (
                  <p className="text-xs text-zinc-700 mt-0.5">{stage.description}</p>
                )}
              </div>

              <div className={`mt-auto flex items-center gap-1.5 text-xs font-medium px-1.5 py-0.5 rounded-full border w-fit
                ${isDone    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : ''}
                ${isRunning ? 'bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse' : ''}
                ${isError   ? 'bg-red-500/15 text-red-400 border-red-500/30' : ''}
                ${stage.status === 'waiting' ? 'bg-zinc-800/50 text-zinc-600 border-zinc-700' : ''}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full
                  ${isDone ? 'bg-emerald-400' : isRunning ? 'bg-blue-400' : isError ? 'bg-red-400' : 'bg-zinc-600'}`}
                />
                {isDone ? 'Done' : isRunning ? 'Running' : isError ? 'Error' : 'Waiting'}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
