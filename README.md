# UpSearch

AI-powered research-to-reach pipeline for identifying open technical problems and executing targeted cold outreach to the teams working on them.

---

## What it does

UpSearch turns public signal (LinkedIn, Reddit, Hacker News, papers, job posts) into structured intelligence about what problems real teams are actively trying to solve, then helps you draft and send precise, human cold outreach to the right people.

**Core loop:**

```
Source → Analyze → Position → Draft → Send → Track
```

1. **Source** — Surface companies and open problems from LinkedIn, Reddit (r/MachineLearning, r/compsci, etc.), Hacker News "Who's Hiring" / "Ask HN", arXiv, and GitHub issues.
2. **Analyze** — Write a tight technical note: what the problem is, where existing solutions fall short, what you can contribute given current open-source tooling or research.
3. **Position** — Hint at analogous work you've done (or studied) to frame credibility without overstating experience.
4. **Draft** — Generate a ≤200-word cold email written like a human student: clear, direct, no dashes, no jargon, one quirky icebreaker if the context warrants it.
5. **Send** — Browser automation (Copilot Tandem) dispatches emails and LinkedIn DMs across configured accounts.
6. **Track** — W&B logs every outreach attempt: who was contacted, which angle was used, open/reply rates, what worked.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        UpSearch                             │
│                                                             │
│  ┌────────────┐    ┌─────────────┐    ┌──────────────────┐ │
│  │  Sourcing  │───▶│  Analyzer   │───▶│  Draft Engine    │ │
│  │  Layer     │    │  (Claude    │    │  (Claude         │ │
│  │            │    │  Opus 4.8)  │    │  Opus 4.8)       │ │
│  │ - LinkedIn │    │             │    │                  │ │
│  │ - Reddit   │    │ - Problem   │    │ - Email (≤200w)  │ │
│  │ - HN       │    │   summary   │    │ - LinkedIn DM    │ │
│  │ - arXiv    │    │ - Tech note │    │ - Human tone     │ │
│  │ - GitHub   │    │ - Fit score │    │ - Icebreaker     │ │
│  └────────────┘    └─────────────┘    └────────┬─────────┘ │
│                                                 │           │
│  ┌──────────────────────────────────────────────▼─────────┐ │
│  │                  Send Layer                             │ │
│  │     Copilot Tandem Browser (Email / LinkedIn / X)      │ │
│  └──────────────────────────────────────────────┬─────────┘ │
│                                                 │           │
│  ┌──────────────────────────────────────────────▼─────────┐ │
│  │              Tracking (W&B)                             │ │
│  │  - Contact log  - Angle used  - Reply rate  - Wins     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Stack

| Layer | Tool |
|---|---|
| Intelligence / writing | Claude Opus 4.8 (`claude-opus-4-8`) |
| Experiment tracking | [Weights & Biases](https://wandb.ai/home) |
| Browser automation | Copilot Tandem Browser |
| Outreach channels | School email, LinkedIn, X |
| Runtime | Python 3.11+ |

---

## Guiding principles

- **Action over analysis** — if you can write a draft, write it. Don't wait for perfect research.
- **≤200 words per email** — every word must earn its place.
- **Write like a student** — no dashes, no corporate tone, no AI-sounding phrasing.
- **Precision beats volume** — one well-researched, well-positioned email beats ten generic ones.
- **Track everything** — W&B logs let you iterate on what actually gets replies.

---

## Recommended outreach flow

```
1. Find a company/team working on problem X
2. Read their recent work (papers, talks, GitHub, HN posts)
3. Write a 3-sentence technical note: problem → gap → your angle
4. Pick the person (engineer or researcher, not recruiter)
5. Draft email with UpSearch → review → send via school email
6. If no reply in 7 days → one LinkedIn follow-up
7. Log result in W&B
```

---

## Status

Early-stage scaffold. Sourcing and draft engine in progress.
