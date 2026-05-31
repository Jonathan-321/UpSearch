import type { WandbRun } from '../types'

interface Props { runs: WandbRun[] }

export default function WandbTrackerPanel({ runs }: Props) {
  const sent = runs.filter(run => run.sent).length
  const replies = runs.filter(run => run.reply).length
  const rate = sent ? `${Math.round((replies / sent) * 100)}%` : '--'

  return (
    <details className="panel overflow-hidden">
      <summary className="px-5 py-4 cursor-pointer list-none flex flex-wrap items-center justify-between gap-3 group" aria-label="Toggle W&B experiment history">
        <div>
          <p className="workspace-label">Experiment History</p>
          <h2 className="text-base font-semibold text-text-1 mt-1">W&amp;B outreach tracker</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="badge font-mono">{runs.length} runs</span>
          <span className="badge font-mono">{sent} sent</span>
          <span className="badge badge-success font-mono">{rate} reply rate</span>
          <svg className="w-4 h-4 text-text-3 transition-transform details-chevron" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </summary>

      <div className="overflow-x-auto border-t border-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-2 text-text-3 uppercase tracking-wider">
            <tr>{['Run ID', 'Topic', 'Source', 'Fit', 'Draft', 'Sent', 'Reply', 'Updated'].map(head => <th key={head} className="text-left px-5 py-3 font-semibold whitespace-nowrap">{head}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-border">
            {runs.map(run => (
              <tr key={run.run_id} className="hover:bg-surface-2">
                <td className="px-5 py-3 font-mono text-amber-400">{run.run_id}</td>
                <td className="px-5 py-3 text-text-1 max-w-[220px] truncate">{run.topic}</td>
                <td className="px-5 py-3 text-text-2">{run.source}</td>
                <td className="px-5 py-3 font-mono text-text-2">{run.fit_score}/10</td>
                <td className="px-5 py-3 text-text-2">{run.draft_created ? 'Yes' : 'No'}</td>
                <td className="px-5 py-3 text-text-2">{run.sent ? 'Yes' : 'No'}</td>
                <td className="px-5 py-3 text-text-2">{run.reply ? 'Yes' : 'No'}</td>
                <td className="px-5 py-3 font-mono text-text-3 whitespace-nowrap">{run.last_updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-5 py-3 border-t border-border">
        <a href="https://wandb.ai/home" target="_blank" rel="noopener noreferrer" className="text-xs text-amber-400 hover:text-amber-300">Open W&amp;B</a>
      </div>
    </details>
  )
}
