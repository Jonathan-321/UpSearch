export type AgentStatus = 'waiting' | 'running' | 'complete';
export type PipelineStatus =
  | 'idle'
  | 'scouting'
  | 'analyzing'
  | 'selecting'
  | 'strategizing'
  | 'writing'
  | 'done';
export type Source = 'reddit' | 'hackernews';
export type Channel = 'email' | 'linkedin' | 'x';
export type ContactType = 'engineer' | 'researcher';

export interface Post {
  id: string;
  title: string;
  body: string;
  url: string;
  source: Source;
  author: string;
  subreddit?: string;
  score: number;
  comments: number;
}

export interface Analysis {
  problem: string;
  gap: string;
  contribution: string;
  fit_score: number;
  contact_type: ContactType;
  reasoning: string;
}

export interface Opportunity {
  post: Post;
  analysis: Analysis;
}

export interface Strategy {
  target_role: string;
  hook: string;
  channel: Channel;
  icebreaker: string;
  suggested_ask: string;
}

export interface WandbRun {
  run_id: string;
  topic: string;
  source: string;
  fit_score: number;
  draft_created: boolean;
  sent: boolean;
  reply: boolean;
  last_updated: string;
}

export type FilterKey = 'reddit' | 'hackernews' | 'engineers' | 'researchers' | 'startups' | 'academia';
