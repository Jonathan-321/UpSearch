export type AgentStatus = 'waiting' | 'running' | 'complete' | 'error';
export type PipelineStatus =
  | 'idle'
  | 'scouting'
  | 'analyzing'
  | 'selecting'
  | 'strategizing'
  | 'writing'
  | 'done'
  | 'error';
export type Source = 'reddit' | 'hackernews';
export type Channel = 'email' | 'linkedin' | 'x';
export type ContactType = 'engineer' | 'researcher' | 'hiring_manager';

export interface Post {
  id: string
  title: string
  body: string
  url: string
  source: Source
  author: string
  subreddit?: string
  score: number
  comments: number
}

export interface Analysis {
  problem: string
  gap: string
  contribution: string
  fit_score: number
  contact_type: ContactType
  reasoning: string
}

export interface Opportunity {
  post: Post
  analysis: Analysis
}

export interface Strategy {
  target_role: string
  hook: string
  channel: Channel
  icebreaker: string
  suggested_ask?: string
}

export interface SupervisorScore {
  score: number
  passed: boolean
  flags: string[]
  reasoning: string
  rule_checks?: Record<string, unknown>
}

export interface SupervisorScores {
  scout?: SupervisorScore
  analyst?: SupervisorScore
  strategist?: SupervisorScore
  writer?: SupervisorScore
}

export interface WandbRun {
  run_id: string
  topic: string
  source: string
  fit_score: number
  draft_created: boolean
  sent: boolean
  reply: boolean
  last_updated: string
}

export type FilterKey = 'reddit' | 'hackernews' | 'engineers' | 'researchers' | 'startups' | 'academia';

export const API_BASE = 'http://localhost:8000/api';

export type LogLevel = 'STARTED' | 'SOURCE' | 'INFO' | 'COMPLETE' | 'ERROR'

export interface LogEntry {
  ts: string
  agent: string
  level: LogLevel
  message: string
  elapsed?: string
}
