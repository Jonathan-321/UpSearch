import type { Opportunity, Strategy, WandbRun } from './types'

// ---------------------------------------------------------------------------
// Mock opportunities returned by Scout + Analyst agents
// ---------------------------------------------------------------------------
export const MOCK_OPPORTUNITIES: Opportunity[] = [
  {
    post: {
      id: 'r-001',
      title: 'Speculative decoding memory overhead is killing us at scale — looking for approaches',
      body: "We're running speculative decoding with a 7B draft model serving a 70B target and the memory overhead is brutal. At small batch sizes we get the 2.5x throughput gain but as batch size grows the draft model's memory just tanks the whole operation. We've tried tree-based drafting but managing the speculative tree state is its own nightmare. Anyone dealt with this at production scale?",
      url: 'https://reddit.com/r/MachineLearning/comments/abc123',
      source: 'reddit',
      author: 'ml_infra_eng',
      subreddit: 'MachineLearning',
      score: 847,
      comments: 143,
    },
    analysis: {
      problem:
        'Teams running speculative decoding at scale face 2–3x memory overhead from draft models, which degrades overall serving efficiency as batch size increases.',
      gap: 'Current approaches treat draft model memory as a fixed cost, ignoring dynamic pruning of speculative trees based on historical acceptance rates.',
      contribution:
        'A motivated CS student with ML systems coursework could prototype a dynamic draft-tree pruning strategy and benchmark it against static approaches on open-source serving stacks like vLLM.',
      fit_score: 9,
      contact_type: 'engineer',
      reasoning: 'Active pain point with a clear engineering angle that requires no specialized hardware to prototype.',
    },
  },
  {
    post: {
      id: 'hn-001',
      title: 'Ask HN: How are teams handling KV-cache eviction in long-context LLM serving?',
      body: "We're building an internal LLM service that needs to handle 100k+ token contexts. KV-cache eviction is becoming the bottleneck — we can't keep full KV caches for all active sessions. Looking for practical approaches beyond the standard sliding window. PagedAttention helps but we're hitting edge cases with reuse patterns. What's actually working in production?",
      url: 'https://news.ycombinator.com/item?id=39abc123',
      source: 'hackernews',
      author: 'throwing_away_llm',
      score: 612,
      comments: 89,
    },
    analysis: {
      problem:
        'LLM services handling very long contexts cannot retain full KV caches across active sessions, causing expensive recomputation or quality degradation from naive eviction.',
      gap: 'PagedAttention addresses fragmentation but does not solve intelligent eviction based on attention patterns and reuse likelihood across sessions.',
      contribution:
        'A student familiar with transformers and OS-level caching could survey attention-based eviction heuristics from recent papers and prototype a simple scoring function on top of an existing serving framework.',
      fit_score: 8,
      contact_type: 'engineer',
      reasoning: 'Real production problem actively discussed, engineering contribution well-scoped for someone studying systems.',
    },
  },
  {
    post: {
      id: 'r-002',
      title: 'We built an interpretability tool for finding monosemantic features in MLP layers — feedback wanted',
      body: "Built a tool that identifies monosemantic neurons in MLP layers using sparse probing + activation patching. We can surface features that correspond to specific concepts with about 78% precision on GPT-2 small. Curious if anyone has tried this approach on larger models and what challenges you hit. We're planning to open-source the core analysis library next month.",
      url: 'https://reddit.com/r/MachineLearning/comments/def456',
      source: 'reddit',
      author: 'interp_researcher',
      subreddit: 'MachineLearning',
      score: 1204,
      comments: 217,
    },
    analysis: {
      problem:
        'Current mechanistic interpretability tools for finding monosemantic features do not scale gracefully beyond small models, and precision degrades significantly with model size.',
      gap: 'Sparse probing works well on GPT-2 scale but replication studies on GPT-4 or Claude-family models are sparse, and no open benchmark exists to compare methods.',
      contribution:
        'A CS student could contribute reproducibility testing on their open-source library once released, or write a comparison script against existing Anthropic superposition research on public models.',
      fit_score: 9,
      contact_type: 'researcher',
      reasoning: "They explicitly asked for feedback and are open-sourcing the tool — ideal entry point for a student interested in interpretability.",
    },
  },
  {
    post: {
      id: 'hn-002',
      title: 'Show HN: Streaming RAG with coherent citations across chunk boundaries',
      body: "Built a RAG pipeline that maintains citation coherence when streaming responses across retrieved chunk boundaries. The core issue was that naive streaming breaks mid-sentence when the model transitions between source documents. We solve it with a lookahead buffer and a secondary coherence model. Happy to share the approach — found zero prior work on this specific problem.",
      url: 'https://news.ycombinator.com/item?id=40bcd234',
      source: 'hackernews',
      author: 'rag_builder',
      score: 478,
      comments: 62,
    },
    analysis: {
      problem:
        'Streaming RAG systems break citation coherence at document boundaries, producing fragmented or mis-attributed responses that undermine user trust.',
      gap: 'Lookahead buffering adds latency and the coherence model adds inference cost — neither is obviously optimal and no public benchmark evaluates this tradeoff.',
      contribution:
        'A student could design a benchmark for streaming citation coherence and evaluate the tradeoff between latency budget and coherence quality, contributing a dataset and evaluation script.',
      fit_score: 7,
      contact_type: 'engineer',
      reasoning: "Builder explicitly noted 'zero prior work' and shared approach publicly — open to collaboration. Good scope for a student project.",
    },
  },
  {
    post: {
      id: 'r-003',
      title: 'P99 latency spikes in model serving — nothing obvious in the traces, anyone else?',
      body: "Our model serving latency is fine at P50 and P95 but P99 spikes every few minutes in a way that doesn't correlate with load. GPU utilization is steady, memory isn't thrashing, CUDA errors are zero. Traces show the spike in the attention computation itself. We're on H100s with FlashAttention 2. Starting to wonder if this is a thermal throttle artifact or something in the batching logic.",
      url: 'https://reddit.com/r/mlops/comments/ghi789',
      source: 'reddit',
      author: 'infra_confused',
      subreddit: 'mlops',
      score: 334,
      comments: 91,
    },
    analysis: {
      problem:
        'Unexplained P99 latency spikes in transformer inference on H100s that are invisible in standard GPU utilization metrics and CUDA error logs.',
      gap: 'Standard profiling tools do not expose sub-kernel timing at the level needed to distinguish thermal throttling from batching scheduler artifacts in FlashAttention kernels.',
      contribution:
        'A student with systems coursework could run a controlled reproduction using NVIDIA Nsight Systems, comparing attention kernel timing variance across thermal states and batch compositions.',
      fit_score: 6,
      contact_type: 'engineer',
      reasoning: 'Specific and unsolved, but the student needs H100 access to contribute directly — lower fit unless they have cluster access.',
    },
  },
]

// ---------------------------------------------------------------------------
// Mock strategy returned by Strategist agent for the first opportunity
// ---------------------------------------------------------------------------
export const MOCK_STRATEGY: Strategy = {
  target_role: 'ML Infrastructure Engineer or tech lead at the company',
  hook: 'You described the exact memory-throughput tradeoff in speculative decoding that I have been reading about in Medusa and SpecInfer — and you hit the part that neither paper addresses at production batch sizes.',
  channel: 'email',
  icebreaker:
    "Your note about draft-tree state management becoming its own 'nightmare' at scale — that's the part I couldn't find addressed anywhere in the literature.",
  suggested_ask: 'Would you be open to a 15-minute call? I have a rough idea about adaptive tree pruning based on prefix acceptance rates and I want to gut-check it with someone running this in production.',
}

// ---------------------------------------------------------------------------
// Mock email draft from Writer agent
// ---------------------------------------------------------------------------
export const MOCK_DRAFT = `Subject: Your post on speculative decoding memory overhead

Hi [Name],

I found your post about draft-tree state management becoming a nightmare at scale and it lined up exactly with something I have been digging into from the Medusa and SpecInfer papers.

I am Luis, a CS student at UConn studying ML systems. I have been modeling the tradeoff between draft tree depth and acceptance rate and I think there might be something in pruning the tree adaptively based on prefix acceptance history rather than keeping a fixed structure across different batch sizes.

I don't have production infrastructure to test this at scale, which is exactly why I am reaching out. Would you be open to a 15-minute call? I mostly want to understand where the real bottlenecks show up that the papers don't capture.

Luis Mendez
UConn CS`

// ---------------------------------------------------------------------------
// Pre-existing W&B runs shown in the tracker (historical)
// ---------------------------------------------------------------------------
export const INITIAL_WANDB_RUNS: WandbRun[] = [
  {
    run_id: 'us-7f3a2b',
    topic: 'LLM inference optimization',
    source: 'hackernews',
    fit_score: 8,
    draft_created: true,
    sent: true,
    reply: true,
    last_updated: '2026-05-28 14:32',
  },
  {
    run_id: 'us-4c8d1e',
    topic: 'AI safety interpretability',
    source: 'reddit',
    fit_score: 9,
    draft_created: true,
    sent: true,
    reply: false,
    last_updated: '2026-05-29 09:15',
  },
  {
    run_id: 'us-2a9f0c',
    topic: 'EEG signal processing',
    source: 'reddit',
    fit_score: 7,
    draft_created: true,
    sent: false,
    reply: false,
    last_updated: '2026-05-30 18:04',
  },
]
