# UpSearch

UpSearch is an AI-powered research-to-reach system for technical students and
early-career builders. It turns public signals into a source-backed company
**opportunity packet** and human-approved outreach, while keeping a person in
control of every external action.

The product is **Opportunity OS**: give it a company name and a technical lane,
and it researches the company, extracts a real technical problem, maps relevant
people, drafts a one-page technical note and outreach, runs QA, and lands the
result in a human approval queue. It optimizes for high-quality technical
conversations started, not message volume.

![UpSearch architecture](docs/assets/upsearch-architecture-clean.svg)

## What it does

- Builds a company packet from a company name and technical lane.
- Runs Profile, Company, Problem, People, Technical Note, Outreach, and QA
  stages with live SSE progress updates.
- Verifies company identity and blocks downstream generation when it cannot be
  established from retrieved evidence.
- Stores companies, problems, people, packets, and messages in a local SQLite
  CRM.
- Surfaces drafts in a human approval queue and never sends messages
  autonomously.
- Runs a background scheduler that can rediscover companies for a requested
  duration.

## Hard invariants

- No fabricated companies, people, URLs, sources, or experience claims.
- Missing evidence stays visible as an explicit state.
- Unverified company identity blocks downstream generation.
- External actions require exact human approval.
- Model confidence is not verification; deterministic checks run first.

## User Data and LinkedIn

UpSearch does not automatically fetch your LinkedIn profile. Your personal
background comes from `profile.txt`, which you edit manually with your skills,
coursework, interests, and goals.

For target contacts, the People Agent searches public signal (Hacker News,
GitHub, company pages) and may suggest public LinkedIn or GitHub URLs when
available. Those profile links must be verified before they are used for
outreach.

## Product planning docs

- [Opportunity Intelligence OS docs](docs/opportunity-intelligence/README.md)
- [First use case charter](docs/opportunity-intelligence/upsearch-first-use-case-charter.md)
- [Current-state architecture](docs/architecture/current-state.md)
- [Target architecture](docs/architecture/target-state.md)

## Quick Start

### Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- An OpenRouter, DeepSeek, or Anthropic API key

### Setup

1. Install Python dependencies (uv is the canonical tool; pip also works).

   ```bash
   uv sync
   # or: pip install -e .
   ```

2. Create `.env` in the project root. Start from `.env.example`, which documents
   the agent provider and the strong/QA model route. The simplest single-key
   setup uses OpenRouter:

   ```dotenv
   MODEL_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_key
   UPSEARCH_CHEAP_MODEL_PROVIDER=openrouter
   UPSEARCH_CHEAP_MODEL=deepseek/deepseek-chat
   UPSEARCH_STRONG_MODEL_PROVIDER=openrouter
   UPSEARCH_STRONG_MODEL=openai/gpt-5
   ```

   When the strong model is unset, QA falls back to the cheap model and runs in
   degraded mode (it will not claim strong-model verification).

3. Edit `profile.txt` with your background, skills, interests, and goals.

4. Install frontend dependencies.

   ```bash
   cd frontend
   npm install
   ```

### Run the Web App

Start the backend:

```bash
python -m uvicorn server:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm run dev -- --port 5180
```

Open:

- Frontend: [http://localhost:5180](http://localhost:5180)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

The frontend opens in **Build Packet** mode. Use the header toggle to switch to
**Review** for profile truth, source grounding, people verification, approval
gates, and run traces.

## CLI Usage

```bash
python os_main.py packet --company Baseten --lane ai_infra
python os_main.py list
python os_main.py show --company Together
python os_main.py approve
python os_main.py crm
```

Available lanes:

```text
ai_infra, inference, agentic, dev_tools, data, robotics
```

## Architecture

```text
Company name + lane
    |
Profile Agent         Parses profile.txt into structured proof points
    |
Company Agent         Researches fit, stack, hiring signal; verifies identity
    |
Problem Agent         Extracts source-backed open technical problems
    |
People Agent          Maps relevant people by proximity to the problem
    |
Technical Note Agent  Writes a focused one-page brief + adjacent proof
    |
Outreach Agent        Drafts email and LinkedIn variants (verified people only)
    |
QA Agent              Checks claims, sources, word count, and tone
    |
Packet checkup        Blocks weak runs instead of polishing them
    |
Human approval queue  Requires an explicit approve action
    |
SQLite CRM            Stores local packet, trace, and outreach records
```

A single `run_pipeline` entry point in `upsearch/orchestrator_service.py` is
shared by the SSE stream (`server.py`), the CLI (`os_main.py`/`orchestrator.py`),
and the background scheduler (`run_scheduler.py`).

## Outreach Rules

- Keep the email body at or below 200 words.
- Start with an icebreaker tied to the recipient's actual work.
- Use a direct student voice without corporate buzzwords.
- Avoid em dashes and en dashes.
- End with one low-friction ask, such as a 15-minute call or one question.
- Do not fabricate experience.
- Require explicit human approval before sending any external message.

## Run Tracking

Pipeline runs emit local-first, privacy-filtered metrics through
`upsearch/tracking.py` (`RunLogger`), written as JSONL under
`UPSEARCH_TRACKING_DIR`. Set `WANDB_API_KEY` (and install the optional
`tracking` extra) to also mirror metrics to Weights & Biases.

## Project Structure

```text
UpSearch/
|-- os_main.py                   # Opportunity OS CLI
|-- server.py                    # FastAPI server (/os/* + /api/{health,profile,config})
|-- db.py                        # SQLite CRM schema and query helpers
|-- orchestrator.py              # CLI adapter over the orchestrator service
|-- run_scheduler.py             # Background rediscovery worker
|-- profile.txt                  # User background used by agents
|-- .env                         # Local API keys, ignored by git
|-- opportunity_os.db            # Local CRM database
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
|-- upsearch/                    # Pipeline support modules
|   |-- orchestrator_service.py  # Single run_pipeline entry point
|   |-- llm.py                   # Agent LLM provider routing
|   |-- model_router.py          # Cost-aware route selection
|   |-- model_execution.py       # Provider call wrapper
|   |-- packet_checkup.py        # Stage gating
|   |-- tracking.py              # Local JSONL + optional W&B logging
|   |-- auto_discovery.py        # Company discovery
|   `-- sourcing/                # web, rss, github, hackernews, reddit
|
|-- tests/                       # pytest suite
|
`-- frontend/
    |-- src/
    |   |-- App.tsx
    |   |-- hooks/
    |   `-- components/
    `-- package.json
```

## Current Limitations

- People sourcing coverage varies by company; verify contacts before outreach.
- Approval records open the destination surface but do not send emails or
  LinkedIn messages automatically.
- A server restart mid-stream loses in-flight generator state, though runs and
  traces are persisted to the database.
