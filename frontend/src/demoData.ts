export type DemoStatus = 'waiting' | 'running' | 'complete'

export interface AgentTrace {
  id: string
  name: string
  goal: string
  modelClass: string
  tools: string[]
  input: string
  output: string
  validators: string[]
  ledgerEvent: string
}

export interface DemoPerson {
  name: string
  role: string
  why: string
  channel: string
}

export interface LedgerEvent {
  event: string
  agent: string
  status: string
  cost: string
}

export interface HarnessAdapter {
  name: string
  role: string
  bestFor: string
  keepOut: string
}

export const demoSeed = {
  lane: 'AI infrastructure / inference',
  userInput: 'I am interested in AI infra, inference systems, and technical conversations that can lead to opportunities.',
  company: 'Baseten',
}

export const traces: AgentTrace[] = [
  {
    id: 'profile',
    name: 'Profile Agent',
    goal: 'Build a compact technical map from minimal user input.',
    modelClass: 'cheap_large_context',
    tools: ['profile.txt', 'proof bank', 'local project summaries'],
    input: 'Broad interest: AI infra and inference.',
    output: 'Profile summary, target lane, adjacent proof options.',
    validators: ['No inflated experience claims', 'At least one proof point', 'Constraints captured'],
    ledgerEvent: 'profile_ingest',
  },
  {
    id: 'company',
    name: 'Company Sourcing Agent',
    goal: 'Pick one high-fit company instead of scattering across many.',
    modelClass: 'cheap_large_context',
    tools: ['careers page', 'company blog', 'H-1B signal cache', 'W&B history'],
    input: 'Lane plus profile summary.',
    output: 'Baseten selected as first target, fit 9.3/10.',
    validators: ['Company source exists', 'Hiring relevance present', 'Sponsor signal marked uncertain if not verified'],
    ledgerEvent: 'company_sourcing',
  },
  {
    id: 'problem',
    name: 'Problem Discovery Agent',
    goal: 'Extract a real open problem from public technical signal.',
    modelClass: 'cheap_large_context',
    tools: ['Baseten blog', 'vLLM docs', 'LoRAX repo', 'paper index'],
    input: 'Baseten plus AI inference lane.',
    output: 'Adapter-aware routing for continual-learning inference.',
    validators: ['Every claim has a source', 'Problem is specific', 'Contribution surface exists'],
    ledgerEvent: 'problem_discovery',
  },
  {
    id: 'people',
    name: 'People Sourcing Agent',
    goal: 'Find people close enough to the problem to be worth contacting.',
    modelClass: 'cheap_fast',
    tools: ['author pages', 'LinkedIn browser', 'company announcements'],
    input: 'Problem brief and Baseten source map.',
    output: 'Bola Malek, Raymond Cano, Joey Zwicker ranked by relevance.',
    validators: ['Person has source', 'Role matches problem', 'Profile URL verified or marked missing'],
    ledgerEvent: 'people_sourcing',
  },
  {
    id: 'note',
    name: 'Technical Note Agent',
    goal: 'Create the artifact that earns a technical conversation.',
    modelClass: 'strong_reasoning',
    tools: ['source packet', 'proof bank', 'one-pager template'],
    input: 'Problem brief, sources, adjacent proof.',
    output: 'One-page proposal: adapter-aware routing and validation service.',
    validators: ['No fake claims', 'Concrete build plan', 'Success criteria included'],
    ledgerEvent: 'technical_note',
  },
  {
    id: 'outreach',
    name: 'Outreach Agent',
    goal: 'Draft one precise message, not a generic cold email.',
    modelClass: 'cheap_fast plus strong polish',
    tools: ['channel rules', 'word counter', 'tone checker'],
    input: 'Target person, problem, note, proof mapping.',
    output: 'LinkedIn connection note for Bola under 300 characters.',
    validators: ['Under channel limit', 'Specific opener', 'One low-friction ask'],
    ledgerEvent: 'outreach_draft',
  },
  {
    id: 'qa',
    name: 'QA Agent',
    goal: 'Stop weak or unsafe packets before the user sees a send button.',
    modelClass: 'no_model then strong_reasoning',
    tools: ['source checker', 'word counter', 'claim audit', 'approval matcher'],
    input: 'Full packet.',
    output: 'QA passed with approval required before external action.',
    validators: ['Sources present', 'No unsupported claims', 'External action blocked'],
    ledgerEvent: 'verification',
  },
  {
    id: 'action',
    name: 'Action Harness',
    goal: 'Keep execution swappable and approval-bound.',
    modelClass: 'no_model',
    tools: ['manual handoff', 'browser connector', 'Gmail API', 'LinkedIn connector'],
    input: 'Exact action intent.',
    output: 'Action blocked until user approves exact target, body, channel, and timing.',
    validators: ['Exact approval match', 'Connector fallback available', 'Ledger event written'],
    ledgerEvent: 'approval_gate',
  },
]

export const people: DemoPerson[] = [
  {
    name: 'Bola Malek',
    role: 'Product / FDE surface at Baseten',
    why: 'Closest public signal to Baseten continual-learning and Frontier Gateway work.',
    channel: 'LinkedIn connection note',
  },
  {
    name: 'Raymond Cano',
    role: 'Software Engineer',
    why: 'Strong fit for Loops and checkpoint-to-deployment workflow questions.',
    channel: 'LinkedIn connection note',
  },
  {
    name: 'Joey Zwicker',
    role: 'Head of Forward Deployed Engineering',
    why: 'Good routing target for the right inference or FDE reviewer.',
    channel: 'LinkedIn after profile verification',
  },
]

export const packet = {
  company: 'Baseten',
  problem: 'Adapter-aware routing for continual-learning inference',
  artifact: 'One-page technical proposal',
  artifactSummary:
    'Build an adapter registry, deterministic router, compatibility gate, provenance log, and promotion report for candidate LoRA adapters.',
  proof:
    'Adjacent proof maps to PolyQuant and CFN evaluation work: revision history, calibration, artifact tracking, and controlled promotion logic.',
  message:
    'Hi Bola, I am a student studying inference systems for models that keep changing after deployment. Your Baseten post on continual learning made me write a short note on adapter-aware routing. Would love to connect and learn if I am framing the problem correctly.',
}

export const ledgerEvents: LedgerEvent[] = [
  { event: 'run.created', agent: 'orchestrator', status: 'ok', cost: '$0.0000' },
  { event: 'model.route', agent: 'problem', status: 'deepseek', cost: '$0.0180 est' },
  { event: 'source.snapshot', agent: 'problem', status: '4 sources', cost: '$0.0000' },
  { event: 'artifact.write', agent: 'technical_note', status: 'one-pager', cost: '$0.0440 est' },
  { event: 'qa.validation', agent: 'qa', status: 'passed', cost: '$0.0060 est' },
  { event: 'approval.required', agent: 'action', status: 'blocked', cost: '$0.0000' },
]

export const harnessAdapters: HarnessAdapter[] = [
  {
    name: 'Codex / Claude Code style',
    role: 'General tool runner',
    bestFor: 'file edits, shell commands, repo-aware implementation, test loops',
    keepOut: 'final send authority and unsupervised account actions',
  },
  {
    name: 'OpenHands style',
    role: 'Sandboxed agent runtime',
    bestFor: 'longer autonomous tasks, browser plus terminal loops, reusable agent server patterns',
    keepOut: 'user identity decisions and private account access by default',
  },
  {
    name: 'Aider style',
    role: 'Git-first pair harness',
    bestFor: 'project edits, diffs, commits, cheap model-backed coding sessions',
    keepOut: 'multi-person sourcing and external outreach actions',
  },
  {
    name: 'SWE-agent style',
    role: 'Task-spec execution loop',
    bestFor: 'clear tasks with tests, acceptance criteria, and reproducible environments',
    keepOut: 'ambiguous research synthesis without a source harness',
  },
]
