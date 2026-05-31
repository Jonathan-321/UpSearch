# Component Audit

Last updated: 2026-05-31

## Purpose

This audit maps every current UpSearch component to what it can serve in the product, where it is brittle, and what needs to be added so the loop does not break under real usage.

## Current components

| Component | Current files | What it serves | What is brittle | Keep / change |
| --- | --- | --- | --- | --- |
| Original search-to-email CLI | `main.py`, `upsearch/agents/*`, `upsearch/sourcing/*` | A working demo of source -> analyze -> strategy -> email -> supervisor -> W&B. Good for proving the basic agent pipeline. | It starts from posts, not company-specific packets. It does not model people, artifacts, approvals, or follow-ups as first-class state. | Keep as a quick pipeline, but do not make it the core product loop. |
| Opportunity OS orchestrator | `orchestrator.py`, `os_main.py`, root `agents/*` | The right product loop: profile -> company -> problem -> people -> note -> outreach -> QA -> action gate. | Agents return loose dicts, sources are weak, outputs are not enforced by a harness, and it overlaps with the older agent stack. | Wrap this flow in the new harness contracts and make it the Phase 1 core. |
| SQLite CRM | `db.py`, `opportunity_os.db` | Companies, problems, people, packets, messages, approvals, sends, follow-ups. This is close to the right product data model. | The committed `.db` file should not be the long-term state source. Source snapshots, run events, exact approval intents, and W&B IDs are missing. | Keep schema direction. Move local DB output to ignored runtime state and add migrations or schema versioning. |
| LLM provider layer | `upsearch/llm.py` | Claude/DeepSeek switch for current agents, including tool-use support. | Provider is global, no per-agent budget, no token/cost accounting, no JSON schema enforcement, no retries/cache. | Replace with model harness while preserving DeepSeek support. |
| Supervisor / QA | `upsearch/supervisor.py`, `agents/qa.py` | Quality checks, score reporting, word-count and tone checks. | Split across two systems. Some QA depends on LLM calls even when deterministic checks would be enough. | Consolidate into one QA harness: deterministic checks first, model review second. |
| W&B tracking | `upsearch/tracker.py`, `upsearch/tracking.py` | Tracks pipeline runs and can become the execution ledger. | There are two logging paths. Current W&B tracking is outreach-run oriented, not packet-run oriented. | Keep W&B, unify event schema around packet runs and agent harness calls. |
| Harness contracts | `upsearch/harness.py`, `upsearch/model_router.py`, `upsearch/schemas.py` | The durable boundary: typed inputs, typed outputs, model routes, budgets, validation, local/W&B logging. | Newly added and not integrated into root agents yet. | Make this the main execution contract for every agent. |
| Connector contracts | `upsearch/connectors.py` | Defines swappable action surfaces: manual, Codex browser, Tandem, Chrome, Gmail API, Drive API. Includes approval matching. | Contract only. No concrete connector implementations yet. | Keep. Add implementations only after packet loop is stable. |
| FastAPI server | `server.py` | Bridges frontend to the old pipeline. Useful API pattern. | Endpoints are for Scout/Analyst/Strategist/Writer, not company packets or approvals. | Add new packet endpoints instead of overloading old ones. |
| Frontend prototype | `frontend/src/*` | Good visual shell: pipeline status, agent cards, opportunities, strategy, draft, W&B panel. | It reflects the old post-based pipeline. It has no packet view, people map, artifact view, or approval inbox. | Keep UI shell, replace core state model with packets and decisions. |
| Seed packets and Oppprep corpus | `packets/baseten/*`, `docs/opportunity-intelligence/oppprep-seed/*` | Golden examples of what good output looks like. Baseten is the first validated case. | Mixed markdown, DOCX, screenshots, and generated previews. Not normalized as test fixtures. | Keep as seed corpus. Extract canonical JSON fixtures for tests. |
| Hermes scheduler | External under `~/.hermes` | Telegram status surface: done, blocked, due, needs decision. | Not in repo and should not regenerate strategy itself. | Treat Hermes as a scheduler/notification connector that reads the ledger. |
| CoreWeave hosting | Planned | Scale-out runtime for scheduled sourcing, queues, browser/scraping workers, and batch model calls. | Too early until local packet loop is stable. | Phase 2. Keep local first. |

## What completes the loop

The loop is only durable when these pieces exist together:

1. **Single packet state model**
   One packet should contain company, lane, problem, source evidence, people, artifact, outreach drafts, QA, approval status, action status, and follow-up schedule.

2. **Source snapshot store**
   Every source URL used by an agent should be fetched, timestamped, deduped, summarized, and stored. Outputs should cite source IDs, not just loose URLs.

3. **Agent spec registry**
   Each agent needs a machine-readable spec: inputs, outputs, tools, allowed models, budget, validators, and next step.

4. **Model harness**
   DeepSeek/Qwen/GPT-mini-class models handle broad reading and first drafts. Stronger models handle final synthesis and QA. The harness tracks tokens, cost, retries, and JSON validity.

5. **Decision inbox**
   The user should not inspect every intermediate. They should see only key decisions: accept lane, approve one-pager, approve exact send, approve follow-up.

6. **Approval-bound action layer**
   External actions must match the approved intent exactly: target, channel, body, attachment, and timing.

7. **Connector fallback stack**
   Preferred: direct API. Fallback: browser. Fallback: manual handoff. The orchestrator should not care which connector succeeds.

8. **Run ledger**
   Local JSONL and W&B should log every agent call, model route, source, artifact, QA result, approval, send action, and outcome.

9. **Hermes daily status**
   Hermes should summarize ledger state: what completed, what is blocked, what needs approval, what is due, and what should happen next.

10. **Golden packet tests**
   Baseten should become the first regression test. If a new pipeline cannot recreate a packet close to the manual Baseten packet, it is not good enough.

## Anti-breakage principles

1. Agents do not talk directly to each other. They pass typed outputs through the orchestrator.
2. Every step is idempotent: rerunning company sourcing should update state without duplicating people, messages, or follow-ups.
3. Every model call has a budget and timeout.
4. Every source-backed claim has a source ID.
5. Every draft has deterministic checks before model QA.
6. Every external action requires exact approval matching.
7. Every connector has a fallback.
8. Every packet can be reconstructed from stored state.
9. Every generated artifact has a version.
10. The system must degrade gracefully: if browser automation fails, it should still produce a packet and manual action instructions.

## Recommended near-term architecture

```text
React UI
  -> FastAPI packet endpoints
    -> Orchestrator state machine
      -> Agent harness
        -> Model harness
        -> Source harness
        -> Tool connectors
      -> SQLite local state
      -> JSONL + W&B ledger
      -> Approval gate
      -> Action connector
      -> Hermes status job
```

## Build order

1. Make `upsearch/schemas.py` the canonical packet schema.
2. Add an `AgentSpec` registry for Profile, Company, Problem, People, Technical Note, Outreach, QA, Action, Scheduler.
3. Wrap the root Opportunity OS agents with `AgentHarness`.
4. Add source snapshot storage before adding more sources.
5. Add packet API endpoints to `server.py`.
6. Update frontend types to packet state, not post state.
7. Add decision inbox UI.
8. Wire W&B/local ledger for every harness call.
9. Add Hermes daily summary from the ledger.
10. Only then add browser/API action connectors.
