import type { Opportunity } from '../types'

interface OpportunityCardProps {
  opportunity: Opportunity
  index: number
  isSelected: boolean
  onSelect: (opp: Opportunity) => void
}

function FitBadge({ score }: { score: number }) {
  const color =
    score >= 8
      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
      : score >= 6
      ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30'

  const barColor =
    score >= 8 ? 'bg-emerald-400' : score >= 6 ? 'bg-amber-400' : 'bg-red-400'

  return (
    <div className="flex items-center gap-2">
      <span className={`text-sm font-bold px-2 py-0.5 rounded-md border ${color}`}>
        {score}/10
      </span>
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 w-2 rounded-sm transition-colors duration-300 ${
              i < score ? barColor : 'bg-zinc-800'
            }`}
          />
        ))}
      </div>
    </div>
  )
}

function SourceBadge({ source, subreddit }: { source: string; subreddit?: string }) {
  if (source === 'reddit') {
    return (
      <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-orange-500/15 text-orange-400 border-orange-500/30">
        r/{subreddit || 'reddit'}
      </span>
    )
  }
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-amber-500/15 text-amber-400 border-amber-500/30">
      Hacker News
    </span>
  )
}

function ContactBadge({ type }: { type: string }) {
  const color =
    type === 'researcher'
      ? 'bg-violet-500/15 text-violet-400 border-violet-500/30'
      : 'bg-sky-500/15 text-sky-400 border-sky-500/30'
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${color}`}>
      {type === 'researcher' ? 'Researcher' : 'Engineer'}
    </span>
  )
}

export default function OpportunityCard({ opportunity, index, isSelected, onSelect }: OpportunityCardProps) {
  const { post, analysis } = opportunity

  return (
    <div
      className={`card card-hover cursor-pointer p-5 flex flex-col gap-4 animate-fade-in-up
        transition-all duration-300
        ${isSelected ? 'border-violet-500/50 bg-violet-500/5 shadow-lg shadow-violet-900/20' : ''}
      `}
      style={{ animationDelay: `${index * 60}ms` }}
      onClick={() => onSelect(opportunity)}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={post.source} subreddit={post.subreddit} />
          <ContactBadge type={analysis.contact_type} />
          {isSelected && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-violet-500/20 text-violet-300 border-violet-500/40">
              Selected
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-600 shrink-0">
          <span>↑ {post.score.toLocaleString()}</span>
          <span>{post.comments} comments</span>
        </div>
      </div>

      {/* Title */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-100 leading-snug line-clamp-2">
          {post.title}
        </h3>
        <p className="text-xs text-zinc-500 mt-1">by {post.author}</p>
      </div>

      {/* Fit score */}
      <FitBadge score={analysis.fit_score} />

      {/* Analysis */}
      <div className="space-y-2 border-t border-zinc-800 pt-3">
        <div>
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Problem</span>
          <p className="text-xs text-zinc-300 mt-0.5 leading-relaxed">{analysis.problem}</p>
        </div>
        <div>
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Gap</span>
          <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{analysis.gap}</p>
        </div>
        <div>
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Your angle</span>
          <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{analysis.contribution}</p>
        </div>
      </div>

      {/* CTA */}
      <div className="flex items-center justify-between pt-1">
        <a
          href={post.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors underline underline-offset-2"
        >
          View source →
        </a>
        <button
          onClick={(e) => { e.stopPropagation(); onSelect(opportunity) }}
          className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all duration-200
            ${isSelected
              ? 'bg-violet-600/30 border-violet-500/50 text-violet-300'
              : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700 hover:border-zinc-600'
            }`}
        >
          {isSelected ? 'Selected' : 'Use this lead →'}
        </button>
      </div>
    </div>
  )
}
