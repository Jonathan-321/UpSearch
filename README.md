# UpSearch

UpSearch is an AI-assisted research-to-reach pipeline for finding technical
opportunities and turning them into focused outreach emails. It searches public
signals from Reddit and Hacker News, ranks the results against a student
profile, suggests an outreach strategy, drafts an email, and optionally logs the
attempt to Weights & Biases.

The repository currently contains:

- A working Python CLI that runs the full pipeline with live source and LLM
  calls.
- A React and Vite frontend prototype that demonstrates the intended user
  experience with mock data. It is not connected to the Python pipeline yet.

## Pipeline

```text
Topic or role
    |
    v
Scout Agent
    Searches Reddit and Hacker News for relevant public posts
    |
    v
Analyst Agent
    Extracts the opportunity, scores fit from 1 to 10, and identifies an angle
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
Writer Agent
    Produces a direct outreach email with a 200-word body limit
    |
    v
W&B Tracker
    Optionally logs the lead, fit score, status, and draft artifact
```

## Features

- Two modes: `jobs` for hiring signals and `research` for open problems.
- Tool-guided scouting across Reddit and Hacker News.
- Support for Anthropic Claude or DeepSeek through an environment variable.
- Structured handoffs between Scout, Analyst, Strategist, and Writer agents.
- A local `profile.txt` file for tailoring the fit analysis and outreach draft.
- Optional W&B logging for outreach experiments and draft artifacts.
- A separate frontend prototype for exploring the planned browser workflow.

## Requirements

- Python 3.10 or newer
- An Anthropic API key or a DeepSeek API key
- A Weights & Biases API key
- Node.js and npm only if you want to run the frontend prototype

The source searchers use public Reddit JSON and Hacker News Algolia endpoints,
so they do not require separate credentials.

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

4. Edit `profile.txt` with the background, interests, and goals that the agents
   should use when scoring leads and writing outreach.

## Run the CLI

Start an interactive run:

```bash
python main.py
```

Or pass the mode and topic directly:

```bash
python main.py --mode jobs --topic "ML inference engineer internship"
python main.py --mode research --topic "speculative decoding"
```

Available options:

| Option | Description |
|---|---|
| `--mode research` or `--mode jobs` | Select the pipeline mode |
| `--topic "..."` | Provide the search topic or target role |
| `--pick N` | Automatically choose ranked result number `N` |
| `--no-log` | Skip the W&B logging prompt after generating the draft |

Note: the current CLI validates `WANDB_API_KEY` at startup even when
`--no-log` is used.

## Frontend Prototype

The `frontend/` directory contains a Vite-powered React prototype of the
planned browser interface. It simulates the pipeline with delays and mock
opportunities from `frontend/src/mockData.ts`. Its filter controls and W&B
actions are visual demonstrations only.

Run it locally:

```bash
cd frontend
npm install
npm run dev
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Outreach Rules

The Writer agent is prompted to keep each email direct and specific:

- Keep the email body at or below 200 words.
- Open with an icebreaker tied to the recipient's actual work.
- Use a student voice without corporate buzzwords.
- Avoid em dashes and en dashes.
- End with one low-friction ask, such as a 15-minute call or one question.

## Project Structure

```text
UpSearch/
|-- main.py                     # CLI orchestrator
|-- profile.txt                 # Student background used by the agents
|-- requirements.txt            # Python dependencies
|-- .env                        # Local API keys, ignored by git
|-- upsearch/
|   |-- llm.py                  # Claude and DeepSeek routing
|   |-- tracker.py              # W&B experiment logging
|   |-- agents/
|   |   |-- scout.py            # Searches public sources through tool use
|   |   |-- analyst.py          # Scores fit and extracts an outreach angle
|   |   |-- strategist.py       # Selects target, hook, channel, and icebreaker
|   |   `-- writer.py           # Drafts the outreach email
|   `-- sourcing/
|       |-- base.py             # Shared Post dataclass
|       |-- reddit.py           # Reddit JSON search client
|       `-- hackernews.py       # Hacker News Algolia search client
`-- frontend/
    |-- package.json            # Vite scripts and frontend dependencies
    `-- src/
        |-- App.tsx             # Prototype interface
        |-- hooks/usePipeline.ts# Mock pipeline state and delays
        `-- mockData.ts         # Demo opportunities, strategy, and W&B runs
```

## Current Limitations

- The frontend does not call a backend API yet.
- The frontend filters do not affect the mocked results yet.
- The CLI catches source request failures and continues, so a blocked or
  unavailable public endpoint may result in fewer leads.
- Reply status updates after logging are currently managed in W&B rather than
  through the CLI.
