import type { OSStage } from '../hooks/useOS'

interface Props {
  stages: OSStage[]
  currentCompany: string
}

export default function OSPipelineStepper({ stages, currentCompany }: Props) {
  const doneCount = stages.filter(stage => stage.status === 'complete').length
  const pct = Math.round((doneCount / stages.length) * 100)

  return (
    <section className="panel p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="workspace-label">Packet Pipeline</p>
          <h2 className="text-base font-semibold text-text-1 mt-1">{currentCompany}</h2>
        </div>
        <span className="font-mono text-xs text-text-2">{doneCount}/{stages.length} stages / {pct}%</span>
      </div>

      <div className="h-1 bg-surface-3 rounded-full overflow-hidden">
        <div className="h-full bg-accent transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {stages.map((stage, index) => {
          const done = stage.status === 'complete'
          const active = stage.status === 'running'
          const failed = stage.status === 'error'
          return (
            <div key={stage.key} className={`min-w-[138px] flex-1 rounded-lg border p-3 transition-colors ${
              active ? 'border-amber-500/60 bg-amber-500/10' :
              done ? 'border-emerald-500/20 bg-emerald-500/5' :
              failed ? 'border-red-500/30 bg-red-500/5' :
              'border-border bg-surface-2'
            }`}>
              <div className="flex items-center justify-between gap-2">
                <span className={`font-mono text-[10px] ${active ? 'text-amber-400' : done ? 'text-emerald-400' : 'text-text-3'}`}>
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className={`status-dot ${active ? 'bg-amber-400 animate-pulse' : done ? 'bg-emerald-400' : failed ? 'bg-red-400' : ''}`} />
              </div>
              <p className="text-xs font-semibold text-text-1 mt-3">{stage.label}</p>
              <p className="text-[11px] text-text-3 mt-1 truncate" title={stage.message || stage.description}>
                {stage.message || stage.description}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}
