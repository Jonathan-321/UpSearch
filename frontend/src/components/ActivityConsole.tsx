import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types'

interface Props {
  entries: LogEntry[]
  isRunning: boolean
}

const LEVEL_COLOR: Record<string, string> = {
  STARTED:  'text-amber-400',
  SOURCE:   'text-text-2',
  INFO:     'text-text-3',
  COMPLETE: 'text-emerald-400',
  ERROR:    'text-red-400',
}

const AGENT_WIDTH = 'w-[5.5rem]'
const LEVEL_WIDTH = 'w-[5rem]'

export default function ActivityConsole({ entries, isRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  if (!isRunning && entries.length === 0) return null

  return (
    <section className="panel overflow-hidden" aria-label="Agent activity log" aria-live="polite" aria-atomic="false">
      <header className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="status-dot bg-amber-400 animate-pulse" aria-hidden="true" />
          )}
          <p className="workspace-label">Agent Activity</p>
        </div>
        <span className="font-mono text-xs text-text-3">{entries.length} events</span>
      </header>

      <div className="font-mono text-xs p-3 max-h-52 overflow-y-auto space-y-px bg-bg/40">
        {entries.map((entry, i) => (
          <div key={i} className="flex items-baseline gap-0 leading-[1.6]">
            <span className="text-text-3 shrink-0 tabular-nums w-[5.5rem]">{entry.ts}</span>
            <span className={`text-amber-500/70 shrink-0 truncate ${AGENT_WIDTH} mr-2`}>{entry.agent}</span>
            <span className={`shrink-0 ${LEVEL_WIDTH} mr-2 ${LEVEL_COLOR[entry.level] ?? 'text-text-2'}`}>
              {entry.level}
            </span>
            <span className="text-text-2 min-w-0 break-words">{entry.message}
              {entry.elapsed && (
                <span className="text-text-3 ml-2">{entry.elapsed}</span>
              )}
            </span>
          </div>
        ))}

        {isRunning && (
          <div className="flex items-baseline gap-0 leading-[1.6] text-text-3">
            <span className="w-[5.5rem]" />
            <span className={`${AGENT_WIDTH} mr-2`} />
            <span className={`${LEVEL_WIDTH} mr-2`} />
            <span className="animate-pulse select-none">▋</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </section>
  )
}
