# UpSearch

UpSearch is an AI-assisted research-to-reach pipeline for finding technical opportunities and turning them into focused outreach. It searches public signals, ranks the results against a technical profile, identifies open problems, drafts outreach, evaluates each agent's output quality, and logs the attempt to Weights and Biases.

The repository contains:

- A working Python CLI that runs the current sourcing and writing pipeline with live source and LLM calls.
- A React and Vite frontend prototype that demonstrates the intended user experience with mock data.
- An Opportunity Intelligence OS seed corpus and multi-agent orchestration plan for the next product layer.

## Pipeline

```text
Topic or role
    |
    v
Scout Agent
    Searches Reddit and Hacker News for relevant public posts
    |
    v
Supervisor (Scout evaluation)
    Scores source relevance and post diversity
    |
    v
Analyst Agent
    Extracts the opportunity, scores fit from 1 to 10, identifies an angle
    |
    v
Supervisor (Analyst evaluation)
    Checks score calibration, result quality, and contact type accuracy
    |
    v
User selection
    Choose one of the highest-fit leads
    |
    v
Strategist Agent
    Recommends a target role, hook, channel, and icebreaker
    |
    v
Supervisor (Strategist evaluation)
    Checks icebreaker specificity and hook quality
    |
    v
Writer Agent
    Produces a direct outreach email with a 200-word body limit
    |
    v
Supervisor (Writer evaluation)
    Rule-based checks plus LLM tone review
    |
    v
Supervisor Summary
    Overall pipeline score, per-agent scores, and flag list
    |
    v
W&B Tracker
    Logs the lead, fit score, draft artifact, and supervisor scores
```

## Features

- Two modes: `jobs` for hiring signals and `research` for open problems.
- Tool-guided scouting across Reddit and Hacker News.
- Support for Anthropic Claude or DeepSeek via a single environment variable.
- Structured handoffs between Scout, Analyst, Strategist, and Writer agents.
- Supervisor agent that evaluates every stage and scores output quality 1 to 10.
- Rule-based Writer checks for word count, dash usage, and buzzword language.
- Per-agent and overall pipeline scores logged to W&B alongside the draft.
- A local `profile.txt` file for tailoring fit analysis and outreach drafts.
- A separate frontend prototype for exploring the planned browser workflow.

## Opportunity Intelligence OS

The current product direction is a multi-agent opportunity intelligence system for technical people. The first seed corpus and architecture plan live in:

- [Opportunity Intelligence OS docs](docs/opportunity-intelligence/README.md)
- [Multi-agent orchestrator plan](docs/opportunity-intelligence/multi-agent-orchestrator-plan.md)

The product loop is:

```text
Profile -> Company -> Problem -> People -> Technical note -> Outreach -> QA -> Approval -> Send -> Track
```

Key decisions:

- Phase 1 lane: AI infrastructure and inference systems.
- First validated packet: Baseten.
- DeepSeek is the preferred cheap/high-context backend for broad sourcing, extraction, and first-pass drafts.
- Stronger models are reserved for final synthesis, final one-pagers, and QA.
- W&B is the execution ledger for runs, artifacts, model routing, approvals, and outcomes.
- CoreWeave is the planned scalable worker/runtime surface.
- Browser automation is a replaceable connector, not a hard dependency. Tandem, Codex browser, Chrome, Gmail API, Drive API, and manual handoff should all sit behind the same action/approval contract.
- External sends, schedules, LinkedIn requests, messages, and cloud writes require explicit approval.

The local harness CLI currently supports:

```bash
python3 -m upsearch.cli phase1
python3 -m upsearch.cli connectors
python3 -m upsearch.cli build-seed --company baseten
```

## Requirements

- Python 3.11 or newer.
- An Anthropic API key or a DeepSeek API key for live LLM runs.
- A Weights and Biases API key for W&B logging.
- Node.js and npm only if you want to run the frontend prototype.

The source searchers use public Reddit JSON and Hacker News Algolia endpoints and do not require separate credentials.

## CLI Setup

1. Create and activate a virtual environment.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install the Python dependencies.

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root.

   For Claude:

   ```dotenv
   MODEL_PROVIDER=claude
   ANTHROPIC_API_KEY=your_anthropic_key
   WANDB_API_KEY=your_wandb_key
   ```

   For DeepSeek:

   ```dotenv
   MODEL_PROVIDER=deepseek
   DEEPSEEK_API_KEY=your_deepseek_key
   WANDB_API_KEY=your_wandb_key
   ```

   For the orchestration harness:

   ```dotenv
   DEEPSEEK_API_KEY=your_deepseek_key
   WANDB_API_KEY=your_wandb_key
   WANDB_PROJECT=upsearch
   WANDB_ENTITY=your_wandb_entity
   ```

4. Edit `profile.txt` with your background, interests, and goals.

## Run the CLI

Start an interactive run:

```bash
python main.py
```

Pass arguments directly to skip prompts:

```bash
python main.py --mode jobs --topic "ML inference engineer internship"
python main.py --mode research --topic "speculative decoding"
```

Available options:

| Option | Description |
|---|---|
| `--mode research` or `--mode jobs` | Select the pipeline mode |
| `--topic "..."` | Provide the search topic or target role |
| `--pick N` | Automatically select ranked result number N |
| `--no-log` | Skip the W&B logging prompt |
| `--no-supervise` | Skip all Supervisor evaluations for faster, cheaper runs |

## Supervisor Agent

After each pipeline stage the Supervisor evaluates the agent's output and assigns a score from 1 to 10. A score below 6 is flagged as a failure.

| Agent | What the Supervisor checks |
|---|---|
| Scout | On-topic posts, source diversity, result count |
| Analyst | Score calibration, specificity of problem and contribution, contact type accuracy |
| Strategist | Icebreaker specificity, hook quality, channel appropriateness |
| Writer | Word count, dash usage, buzzword scan, tone, and ask quality |

At the end of the pipeline a summary table shows all four scores, any flags, and an overall average. Everything is logged to W&B as numeric metrics so you can compare runs over time.

Run without the Supervisor when you want faster output or want to save LLM tokens:

```bash
python main.py --mode jobs --topic "your topic" --no-supervise
```

## Frontend Prototype

The `frontend/` directory contains a Vite-powered React prototype of the planned browser interface. It simulates the pipeline with delays and mock opportunities from `frontend/src/mockData.ts`.

```bash
cd frontend
npm install
npm run dev
```

## Outreach Rules

The Writer agent is prompted to follow these constraints:

- Keep the email body at or below 200 words.
- Open with an icebreaker tied to the recipient's actual work.
- Use a student voice without corporate buzzwords.
- Avoid em dashes and en dashes.
- End with one low-friction ask such as a 15-minute call or one question.

The Supervisor enforces word count, dash usage, and buzzword presence automatically using rule-based checks before the LLM quality review.

## Project Structure

```text
UpSearch/
|-- main.py                         # CLI orchestrator
|-- profile.txt                     # Student background used by the agents
|-- requirements.txt                # Python dependencies
|-- pyproject.toml                  # Harness package metadata
|-- .env                            # Local API keys, ignored by git
|-- agents/                         # Current root-level agent modules
|-- packets/                        # Seed packet outputs
|-- docs/
|   `-- opportunity-intelligence/   # Product docs and Oppprep seed corpus
|-- upsearch/
|   |-- llm.py                      # Claude and DeepSeek routing
|   |-- supervisor.py               # Per-agent quality evaluator
|   |-- tracker.py                  # W&B logging for current pipeline
|   |-- cli.py                      # Local harness CLI
|   |-- connectors.py               # Replaceable action connector contracts
|   |-- harness.py                  # Agent harness contracts
|   |-- model_router.py             # Cost-aware model routing
|   |-- schemas.py                  # Opportunity packet schemas
|   |-- tracking.py                 # Local/W&B run ledger
|   |-- agents/
|   `-- sourcing/
`-- frontend/
    |-- package.json
    `-- src/
```

## W&B Metrics

Each logged run includes:

| Metric | Description |
|---|---|
| `fit_score` | Analyst fit score for the selected lead |
| `word_count` | Word count of the draft body |
| `sent` | Whether the email was marked as sent |
| `supervisor_overall_score` | Average score across all four agents |
| `supervisor_scout_score` | Scout evaluation score |
| `supervisor_analyst_score` | Analyst evaluation score |
| `supervisor_strategist_score` | Strategist evaluation score |
| `supervisor_writer_score` | Writer evaluation score |

A `supervisor_report.json` artifact is attached to every logged run containing the full flag list and per-agent reasoning.

## Current Limitations

- The frontend does not call a backend API yet.
- The frontend filters do not affect the mocked results yet.
- Reply status updates after logging are currently managed in W&B directly.
- The Supervisor adds two to four extra LLM calls per run. Use `--no-supervise` to skip them when speed matters.
- The Opportunity Intelligence harness currently builds a deterministic Baseten seed packet before live DeepSeek/W&B execution is wired end to end.
