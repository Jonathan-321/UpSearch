import type { Opportunity } from '../types'

interface Props {
  opportunity: Opportunity
  index: number
  isSelected: boolean
  onSelect: (opp: Opportunity) => void
}

export default function OpportunityCard({ opportunity, isSelected, onSelect }: Props) {
  const { post, analysis } = opportunity
  const scoreStyle = analysis.fit_score >= 8 ? 'badge-success' : analysis.fit_score >= 6 ? 'badge-warning' : 'badge-error'

  return (
    <article className={`panel p-5 transition-colors ${isSelected ? 'border-amber-500/60 bg-amber-500/[0.04]' : 'hover:bg-surface-2'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <span className="badge">{post.source === 'reddit' ? `r/${post.subreddit || 'reddit'}` : 'Hacker News'}</span>
          <span className="badge">{analysis.contact_type.replace('_', ' ')}</span>
        </div>
        <span className={`badge font-mono ${scoreStyle}`}>{analysis.fit_score}/10 fit</span>
      </div>

      <h3 className="text-base font-semibold text-text-1 leading-snug mt-4">{post.title}</h3>
      <p className="text-xs text-text-3 mt-1">by {post.author} / {post.comments} comments</p>

      <div className="mt-4 pt-4 border-t border-border space-y-3">
        <div>
          <p className="section-head">Problem</p>
          <p className="text-sm text-text-2 leading-relaxed mt-1">{analysis.problem}</p>
        </div>
        <div>
          <p className="section-head">Your angle</p>
          <p className="text-sm text-text-1 leading-relaxed mt-1">{analysis.contribution}</p>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 mt-4">
        <a href={post.url} target="_blank" rel="noopener noreferrer" className="text-xs text-amber-400 hover:text-amber-300 underline underline-offset-4">
          View source
        </a>
        <button className={`btn ${isSelected ? 'btn-ghost' : 'btn-primary'}`} onClick={() => onSelect(opportunity)}>
          {isSelected ? 'Selected' : 'Use this lead'}
        </button>
      </div>
    </article>
  )
}
