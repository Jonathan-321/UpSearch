interface HeaderProps {
  onReset: () => void
}

export default function Header({ onReset }: HeaderProps) {
  return (
    <header className="relative z-10 border-b border-zinc-800/60 bg-zinc-950/70 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <button onClick={onReset} className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-violet-900/40">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="6" cy="6" r="4" stroke="white" strokeWidth="1.5" />
              <line x1="9.5" y1="9.5" x2="14" y2="14" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
              <line x1="6" y1="3" x2="6" y2="9" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
              <line x1="3" y1="6" x2="9" y2="6" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <span className="text-lg font-bold gradient-text group-hover:opacity-90 transition-opacity">
              UpSearch
            </span>
          </div>
        </button>

        {/* Tagline — hidden on small screens */}
        <p className="hidden md:block text-sm text-zinc-500 italic">
          Research signal to credible outreach
        </p>

        {/* Status badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-zinc-800 bg-zinc-900/60 text-xs text-zinc-400">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-500 opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500" />
          </span>
          Powered by Claude + W&amp;B
        </div>
      </div>
    </header>
  )
}
