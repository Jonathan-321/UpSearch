import type { WandbRun } from '../types'

interface WandbTrackerPanelProps {
  runs: WandbRun[]
}

function StatusDot({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={`flex items-center gap-1.5 text-xs ${active ? 'text-emerald-400' : 'text-zinc-600'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-emerald-400' : 'bg-zinc-700'}`} />
      {label}
    </span>
  )
}

function FitChip({ score }: { score: number }) {
  const color =
    score >= 8
      ? 'text-emerald-400 bg-emerald-500/10'
      : score >= 6
      ? 'text-amber-400 bg-amber-500/10'
      : 'text-red-400 bg-red-500/10'
  return (
    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${color}`}>
      {score}
    </span>
  )
}

export default function WandbTrackerPanel({ runs }: WandbTrackerPanelProps) {
  return (
    <section className="card animate-fade-in-up overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          {/* W&B logo-ish */}
          <div className="w-7 h-7 rounded-md bg-yellow-500/15 flex items-center justify-center">
            <span className="text-yellow-400 font-black text-xs">W</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100">W&amp;B Experiment Tracker</p>
            <p className="text-xs text-zinc-500">Outreach runs — track what gets replies</p>
          </div>
        </div>
        <a
          href="https://wandb.ai/home"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors border border-zinc-800 hover:border-zinc-700 px-2.5 py-1 rounded-md"
        >
          Open W&amp;B →
        </a>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800">
              {['Run ID', 'Topic', 'Source', 'Fit', 'Draft', 'Sent', 'Reply', 'Updated'].map((h) => (
                <th key={h} className="text-left text-zinc-500 font-semibold uppercase tracking-wide px-5 py-3 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((run, i) => (
              <tr
                key={run.run_id}
                className={`border-b border-zinc-800/50 transition-colors hover:bg-zinc-800/30
                  ${i === 0 ? 'bg-violet-500/5' : ''}`}
              >
                <td className="px-5 py-3 font-mono text-violet-400 whitespace-nowrap">
                  {run.run_id}
                </td>
                <td className="px-5 py-3 text-zinc-300 max-w-[200px] truncate" title={run.topic}>
                  {run.topic}
                </td>
                <td className="px-5 py-3">
                  {run.source === 'reddit' ? (
                    <span className="text-orange-400">Reddit</span>
                  ) : (
                    <span className="text-amber-400">HN</span>
                  )}
                </td>
                <td className="px-5 py-3">
                  <FitChip score={run.fit_score} />
                </td>
                <td className="px-5 py-3">
                  <StatusDot active={run.draft_created} label={run.draft_created ? 'Yes' : 'No'} />
                </td>
                <td className="px-5 py-3">
                  <StatusDot active={run.sent} label={run.sent ? 'Sent' : 'No'} />
                </td>
                <td className="px-5 py-3">
                  <StatusDot active={run.reply} label={run.reply ? 'Yes!' : 'No'} />
                </td>
                <td className="px-5 py-3 text-zinc-600 whitespace-nowrap font-mono">
                  {run.last_updated}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {runs.length === 0 && (
          <div className="text-center py-10 text-zinc-600 text-sm">
            No runs yet. Complete the pipeline and log your first outreach.
          </div>
        )}
      </div>

      {/* Footer stats */}
      {runs.length > 0 && (
        <div className="flex items-center gap-6 px-5 py-3 border-t border-zinc-800 bg-zinc-900/30">
          <span className="text-xs text-zinc-500">
            <span className="font-semibold text-zinc-300">{runs.length}</span> total runs
          </span>
          <span className="text-xs text-zinc-500">
            <span className="font-semibold text-zinc-300">{runs.filter((r) => r.sent).length}</span> sent
          </span>
          <span className="text-xs text-zinc-500">
            <span className="font-semibold text-emerald-400">{runs.filter((r) => r.reply).length}</span> replies
          </span>
          <span className="text-xs text-zinc-500">
            Reply rate:{' '}
            <span className={`font-semibold ${runs.filter((r) => r.sent).length > 0 ? 'text-zinc-300' : 'text-zinc-600'}`}>
              {runs.filter((r) => r.sent).length > 0
                ? `${Math.round((runs.filter((r) => r.reply).length / runs.filter((r) => r.sent).length) * 100)}%`
                : '—'}
            </span>
          </span>
        </div>
      )}
    </section>
  )
}
