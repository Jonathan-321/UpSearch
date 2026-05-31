# UpSearch — Opportunity Intelligence OS

An AI-powered research-to-reach system for technical students and early-career builders. It runs two integrated workflows from a single codebase: a quick outreach search (UpSearch) and a full company packet builder (Opportunity OS).

---

## What it does

**Quick Search (UpSearch):** Type a topic or role. Four agents — Scout, Analyst, Strategist, Writer — run in sequence against live Reddit and HN data and produce a ready-to-send cold email. A Supervisor evaluates every stage. Results log to Weights and Biases.

**Opportunity OS:** Type a company name. Eight agents — Profile, Company, Problem, People, Technical Note, Outreach, QA, Action — build a full company packet: open problem brief, people map with LinkedIn links, one-page technical note, outreach variants for email and LinkedIn, and QA flags. Packets are stored in a local SQLite CRM. A live dashboard shows all companies, packet details, and a one-click approval queue.

---

## Quick start

### Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- Anthropic API key or DeepSeek API key
- Weights and Biases API key

### Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Create .env in the project root
MODEL_PROVIDER=deepseek          # or claude
DEEPSEEK_API_KEY=your_key
ANTHROPIC_API_KEY=your_key       # only needed if MODEL_PROVIDER=claude
WANDB_API_KEY=your_key

# 3. Edit profile.txt with your background, skills, and goals

# 4. Install frontend dependencies
cd frontend && npm install && cd ..
```

### Run

```bash
# Terminal 1 — API server (required for the frontend)
uvicorn server:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
# Opens at http://localhost:5180
```

The frontend opens in **Opportunity OS** mode by default. Toggle to **Quick Search** in the header.

---

## CLI usage

### Quick Search (UpSearch)

```bash
python main.py --mode jobs --topic "ML inference engineer internship"
python main.py --mode research --topic "speculative decoding"
python main.py --mode jobs --topic "LLM serving" --pick 1 --no-log
```

| Option | Description |
|---|---|
| `--mode jobs` or `--mode research` | Pipeline mode |
| `--topic "..."` | Search topic or target role |
| `--pick N` | Auto-select result N (skips prompt) |
| `--no-log` | Skip W&B logging prompt |
| `--no-supervise` | Skip Supervisor evaluations (faster) |

### Opportunity OS

```bash
# Build a full company packet
python os_main.py packet --company Baseten --lane ai_infra

# List all companies in the CRM
python os_main.py list

# Show a specific packet
python os_main.py show --company Together

# Review and approve pending outreach drafts
python os_main.py approve

# CRM overview and due follow-ups
python os_main.py crm
```

Available lanes: `ai_infra`, `inference`, `agentic`, `dev_tools`, `data`, `robotics`

---

## Architecture

### Quick Search pipeline

```text
Topic or role
    |
Scout Agent           Searches Reddit and HN via tool use
    |
Supervisor            Scores source relevance and diversity
    |
Analyst Agent         Fits posts to user profile, scores 1-10
    |
Supervisor            Checks score calibration and contact type
    |
User selects a lead
    |
Strategist Agent      Picks target role, hook, channel, icebreaker
    |
Supervisor            Checks icebreaker specificity and hook quality
    |
Writer Agent          Drafts cold email, max 200 words
    |
Supervisor            Word count, em-dash, buzzword, tone checks
    |
W&B Tracker           Logs run, scores, and draft artifact
```

### Opportunity OS pipeline

```text
Company name + lane
    |
Profile Agent         Parses profile.txt into a structured technical map
    |
Company Agent         Researches fit, tech stack, hiring signal, open source
    |
Problem Agent         Extracts open technical problems from public sources
    |
People Agent          Finds and ranks relevant people by proximity to problem
    |
Technical Note Agent  Writes a one-page problem brief with contribution idea
    |
Outreach Agent        Drafts email, LinkedIn note, and connection follow-up
    |
QA Agent              Checks claims, sources, word count, tone, and fabrication
    |
Action Agent          Surfaces drafts for approval — never sends autonomously
    |
SQLite CRM            Stores company, problems, people, packet, and messages
W&B Tracker           Logs packet, QA scores, and supervisor metrics
```

---

## Agents

### Quick Search agents

| Agent | What it does |
|---|---|
| Scout | Searches Reddit and HN using Claude or DeepSeek tool use. Picks subreddits and queries. |
| Analyst | Scores each post for fit 1-10. Extracts problem, gap, and contribution angle. |
| Strategist | Decides who to contact, what hook to use, which channel, and what icebreaker. |
| Writer | Drafts a cold email under 200 words in student voice. No dashes or buzzwords. |
| Supervisor | Runs after every stage. Scores quality 1-10. Flags specific issues. |

### Opportunity OS agents

| Agent | What it does |
|---|---|
| Profile | Extracts technical map, skills, coursework, and proof points from profile.txt. |
| Company | Researches company: product, tech stack, fit score, hiring status, open source. |
| Problem | Finds real open problems from HN, Reddit, GitHub, and blog signal. |
| People | Maps 3-6 relevant people by proximity to the problem, with public profile links. |
| Technical Note | Writes a one-page problem brief: landscape, contribution idea, evaluation approach. |
| Outreach | Drafts email, LinkedIn connection note, and post-connection follow-up. |
| QA | Rule-based and LLM checks: word count, em-dashes, fabricated claims, generic icebreakers, missing sources. |
| Action | Surfaces drafts for human approval. Never sends autonomously. Records outcomes. |

---

## Outreach rules (enforced in every draft)

- Email body: 200 words maximum.
- Open with an icebreaker specific to the recipient's actual work, not a generic compliment.
- Student voice: direct, human, no corporate phrasing.
- No em dashes or en dashes.
- No buzzwords: leverage, synergy, excited to connect, touch base.
- One low-friction ask at the end: a 15-minute call or one specific question.
- No fabricated experience: use "studying", "working through", or "prototyping", not "I built" or "I deployed".

The QA Agent enforces these automatically and flags violations before any draft reaches the approval queue.

---

## Frontend

Two modes in one interface, toggled from the header.

**Quick Search mode:** Search panel, 4-stage pipeline stepper with live status, opportunity cards ranked by fit, strategy panel, editable email draft, Supervisor scores panel, W&B tracker table.

**Opportunity OS mode:** Company input with lane selector, 7-stage pipeline stepper updating via SSE as each agent completes, two-column layout with Company CRM on the left and packet detail on the right, approval queue below with Approve / Skip / Copy per draft.

---

## Model routing

Both pipelines support Claude and DeepSeek. Switch with one line in `.env`.

```dotenv
MODEL_PROVIDER=deepseek   # fast, cost-effective, OpenAI-compatible
MODEL_PROVIDER=claude     # claude-opus-4-8, with prompt caching
```

The Scout agent has separate implementations for each provider since tool-use APIs differ. All other agents use a shared `llm.complete()` wrapper.

---

## W&B metrics

Every logged Quick Search run includes:

| Metric | Description |
|---|---|
| `fit_score` | Analyst fit score for the selected lead |
| `word_count` | Draft word count |
| `sent` | Whether the email was marked sent |
| `supervisor_overall_score` | Average across all four supervisor evaluations |
| `supervisor_scout_score` | Scout evaluation |
| `supervisor_analyst_score` | Analyst evaluation |
| `supervisor_strategist_score` | Strategist evaluation |
| `supervisor_writer_score` | Writer evaluation |

A `supervisor_report.json` artifact is attached to every run with the full flag list and per-agent reasoning.

---

## Project structure

```text
UpSearch/
|-- main.py                      # Quick Search CLI
|-- os_main.py                   # Opportunity OS CLI
|-- server.py                    # Unified FastAPI server (/api/* + /os/*)
|-- db.py                        # SQLite CRM schema and query helpers
|-- orchestrator.py              # OS task graph and agent dispatch
|-- profile.txt                  # User background (edit this)
|-- requirements.txt
|-- .env                         # API keys (gitignored)
|-- opportunity_os.db            # SQLite CRM (gitignored)
|
|-- agents/                      # Opportunity OS agents
|   |-- profile.py
|   |-- company.py
|   |-- problem.py
|   |-- people.py
|   |-- technical_note.py
|   |-- outreach.py
|   |-- qa.py
|   `-- action.py
|
|-- upsearch/                    # Quick Search agents and sourcing
|   |-- llm.py                   # Claude and DeepSeek routing
|   |-- supervisor.py            # Per-agent quality evaluator
|   |-- tracker.py               # W&B logging
|   |-- agents/
|   |   |-- scout.py
|   |   |-- analyst.py
|   |   |-- strategist.py
|   |   `-- writer.py
|   `-- sourcing/
|       |-- base.py
|       |-- reddit.py
|       `-- hackernews.py
|
|-- packets/                     # Reference company packets (P0)
|   `-- baseten/
|       |-- packet.json
|       |-- technical_note.md
|       `-- outreach/
|           |-- email.md
|           `-- linkedin_note.md
|
`-- frontend/
    |-- src/
    |   |-- App.tsx              # Root with Quick Search / OS mode toggle
    |   |-- hooks/
    |   |   |-- usePipeline.ts   # Quick Search state + API calls
    |   |   `-- useOS.ts         # OS state + SSE streaming + CRM calls
    |   `-- components/
    |       |-- SearchPanel.tsx
    |       |-- PipelineStepper.tsx
    |       |-- AgentCard.tsx
    |       |-- OpportunityCard.tsx
    |       |-- StrategyPanel.tsx
    |       |-- EmailDraftPanel.tsx
    |       |-- SupervisorPanel.tsx
    |       |-- WandbTrackerPanel.tsx
    |       |-- OSSearchPanel.tsx
    |       |-- OSPipelineStepper.tsx
    |       |-- CRMTable.tsx
    |       |-- PacketView.tsx
    |       `-- ApprovalQueue.tsx
    `-- package.json
```

---

## Operating principles

- Action over confusion. If a draft is ready, show it. Do not wait for perfect research.
- Never send autonomously. Every external message requires explicit user approval.
- No fabricated experience. Agents use "studying" and "prototyping", not "I built" or "I deployed".
- No uncontrolled mass outreach. Targeted, specific, and human.
- QA before approval. Every draft passes a rule-based and LLM quality check first.
- Track everything. W&B logs let you iterate on what actually gets replies.
