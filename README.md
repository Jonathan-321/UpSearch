# UpSearch

AI-powered research-to-reach pipeline. Turns public signal (Reddit, HN) into targeted cold outreach to engineers and researchers working on real open problems.

---

## Judging Criteria — How UpSearch Addresses Each

| Criterion | How |
|---|---|
| **Agent Orchestration** | Four specialized agents (Scout, Analyst, Strategist, Writer) run in sequence, each consuming the prior agent's structured output |
| **Utility** | Solves a real student problem: finding the right people working on the right problems and reaching them with a credible, specific message |
| **Technical Execution** | Tool-use Scout Agent, prompt-cached Claude Opus 4.8 calls, structured JSON handoffs between agents, W&B experiment tracking |
| **Creativity** | Reframes cold outreach as a research pipeline — signal-first, then contact — instead of shotgun emailing |
| **Sponsor Usage** | W&B tracks every outreach attempt as an experiment: fit score, draft artifact, sent/reply status, iterable over time |

---

## Agent Architecture

```
User Input (topic)
       │
       ▼
┌─────────────────────────────────────────┐
│  Scout Agent  (Claude Opus 4.8 + tools) │
│  Decides what to search, calls Reddit   │
│  and HN APIs via tool use, returns      │
│  a ranked list of raw posts             │
└──────────────────────┬──────────────────┘
                       │  posts[]
                       ▼
┌─────────────────────────────────────────┐
│  Analyst Agent  (Claude Opus 4.8)       │
│  Reads each post, scores fit (1-10),    │
│  extracts: problem, gap, contribution   │
└──────────────────────┬──────────────────┘
                       │  analysis{}  (user picks one)
                       ▼
┌─────────────────────────────────────────┐
│  Strategist Agent  (Claude Opus 4.8)    │
│  Decides: who to contact, what hook     │
│  to use, which channel, icebreaker      │
└──────────────────────┬──────────────────┘
                       │  strategy{}
                       ▼
┌─────────────────────────────────────────┐
│  Writer Agent  (Claude Opus 4.8)        │
│  Drafts ≤200-word cold email            │
│  Student voice, no dashes, one ask      │
└──────────────────────┬──────────────────┘
                       │  draft (text)
                       ▼
┌─────────────────────────────────────────┐
│  W&B Tracker                            │
│  Logs run config, fit score, draft      │
│  artifact. Reply/sent updated manually. │
└─────────────────────────────────────────┘
```

---

## Stack

| Layer | Tool |
|---|---|
| All agents | Claude Opus 4.8 (`claude-opus-4-8`) via Anthropic SDK |
| Scout sourcing | Reddit JSON API + HN Algolia API (no auth required) |
| Experiment tracking | [Weights & Biases](https://wandb.ai/home) |
| Outreach channels | School email (primary), LinkedIn, X |
| CLI | Python + Rich |

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your Anthropic API key to .env
ANTHROPIC_API_KEY=your_key_here
WANDB_API_KEY=your_wandb_key_here   # already set

# 3. Edit profile.txt with your actual background

# 4. Run
python main.py
```

---

## Outreach rules (baked into every agent)

- Email body: **200 words max**
- No em-dashes, no en-dashes, no buzzwords
- Open with a specific icebreaker tied to their actual work
- One low-friction ask at the end (15-min call or one question)
- Log everything to W&B — iterate on what gets replies

---

## File structure

```
UpSearch/
├── main.py              # Orchestrator — runs all four agents in sequence
├── profile.txt          # Your background (edit this)
├── requirements.txt
├── .env                 # API keys (gitignored)
└── upsearch/
    ├── agents/
    │   ├── scout.py     # Stage 1 — tool-use search agent
    │   ├── analyst.py   # Stage 2 — technical note + fit score
    │   ├── strategist.py# Stage 3 — who/hook/channel/icebreaker
    │   └── writer.py    # Stage 4 — cold email draft
    ├── sourcing/
    │   ├── reddit.py    # Reddit JSON API
    │   └── hackernews.py# HN Algolia API
    └── tracker.py       # W&B logging
```
