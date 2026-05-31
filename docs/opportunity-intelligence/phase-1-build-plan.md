# Phase 1 Build Plan

Last updated: 2026-05-31

## Thesis

Given as little information as possible, UpSearch should help an early-career technical user get a foot in the door through authentic, high-quality technical conversations instead of message volume.

The system should not become another job board, application spammer, or generic LinkedIn automation tool. It should move a user from broad interest areas to company-specific technical packets:

1. Who to contact.
2. What problem to discuss.
3. What artifact to show.
4. How the user's adjacent experience maps to the problem.
5. When to send or follow up.

The user remains the decision-maker at high-risk moments: sending, scheduling, connecting, messaging, editing public/cloud docs, and attaching artifacts.

## Phase 1 lane

Start with AI infrastructure and inference systems.

Reason:

1. We already validated the loop manually with Baseten.
2. The output packet is concrete: problem, people, one-pager, outreach, approval state.
3. The lane has enough public signal: blogs, docs, papers, HN, GitHub, jobs, and engineers writing publicly.
4. It tests the hard product problem without widening too early.

Phase 1 target companies:

1. Baseten.
2. Modal.
3. Fireworks AI.
4. Together AI.

## Core constraints

| Constraint | Product response |
| --- | --- |
| API costs | Route high-token work to cheap models, reserve strong models for final synthesis and QA. |
| Token usage | Use source chunking, map/reduce extraction, structured outputs, and caching. |
| Data scraping/access | Prefer official pages, public feeds, APIs, and user-authenticated connectors only where appropriate. |
| Network communication | Use an explicit orchestration protocol with typed handoffs, not informal agent chat. |
| Agentic communication | Agents exchange structured packets through the orchestrator, not direct free-form messages. |
| User overload | Provide recommended outputs and only ask for decisions at high-risk or taste-critical gates. |
| External actions | Require exact approval before send, schedule, connect, message, or cloud write. |

## Biggest challenges

1. **State discipline.** Companies, problems, sources, people, artifacts, drafts, approvals, and send events must be represented cleanly or the product becomes an untrusted pile of prompts.
2. **Source grounding.** The system must know why it believes a person, role, problem, or company fit is real.
3. **Identity resolution.** A person found on a blog, LinkedIn, GitHub, and a job post may not be the same person unless verified.
4. **Cost-aware routing.** Broad search and extraction can be cheap; final technical notes and claim audits need better judgment.
5. **Connector reliability.** Browser automation is useful but fragile. Gmail API, Drive API, Chrome, Codex browser, Tandem, and manual handoff should all be replaceable connectors.
6. **Approval correctness.** The exact approved message must match the exact sent message.
7. **Learning loop.** W&B should track not only model metrics but which packet types actually create conversations.

## Architecture

```text
User seed
  -> Orchestrator
      -> Profile Agent
      -> Company Sourcing Agent
      -> Problem Discovery Agent
      -> People Sourcing Agent
      -> Technical Note Agent
      -> Outreach Agent
      -> QA Agent
      -> Approval Gate
      -> Action Connector
      -> Follow-up Scheduler
      -> W&B Ledger
```

The orchestrator owns state. Agents do not decide what to send. Connectors do not decide what is allowed. Models do not own final truth.

## Agent tool matrix

| Agent | Inputs | Tools | Output | Default model tier |
| --- | --- | --- | --- | --- |
| Profile Agent | Resume, GitHub, free-text goals, constraints | GitHub reader, local files, resume parser | `UserProfile`, proof bank, weak spots | Cheap first pass, strong final summary |
| Company Sourcing Agent | Target lane, constraints, existing profile | Web search, careers pages, H-1B sources, W&B cache | Company shortlist with fit and sponsor signal | Cheap/high-context |
| Problem Discovery Agent | Company shortlist | Company blogs, docs, papers, HN, Reddit, GitHub, jobs | Problem briefs with evidence URLs | Cheap extraction, strong prioritization |
| People Sourcing Agent | Company and problem brief | LinkedIn/browser, company author pages, GitHub, papers, team pages | People map and best channel | Cheap + browser/tools |
| Technical Note Agent | Problem brief, proof bank, sources | Paper/docs retrieval, local artifact generator | One-page technical proposal | Strong synthesis |
| Outreach Agent | Person, problem, note, proof bank | Draft templates, channel rules, word-count checker | Email, LinkedIn note, follow-up draft | Cheap variants, strong final polish |
| QA Agent | Whole packet | Source checker, word count, claim audit, approval checker | QA report and risk flags | Strong + deterministic checks |
| Action Agent | Approved action intent | Gmail API, Drive API, browser, manual handoff | Draft/send/schedule result | No model by default |
| Scheduler Agent | Send state, due dates, Hermes config | Hermes/Telegram, cron, W&B state | Daily brief and reminders | Cheap/no model |

## Agent communication protocol

Agents should not free-chat with each other. The orchestrator should pass typed envelopes:

```json
{
  "run_id": "run_123",
  "user_id": "local_user",
  "agent": "problem_discovery",
  "task": "extract_company_problems",
  "lane": "AI infrastructure / inference",
  "company": "Baseten",
  "input_refs": ["company:baseten", "profile:jonathan"],
  "source_refs": ["url:https://www.baseten.co/blog/..."],
  "budget": {
    "max_input_tokens": 120000,
    "max_output_tokens": 4000,
    "max_cost_usd": 0.25
  },
  "output_schema": "ProblemBrief[]",
  "requires_approval": false
}
```

Every output should include:

1. Structured JSON.
2. Human-readable summary.
3. Source URLs.
4. Confidence.
5. Missing evidence.
6. Next recommended task.

## Model harness policy

Use model classes instead of hardcoding one provider everywhere.

| Model class | Use | Examples |
| --- | --- | --- |
| `cheap_large_context` | broad search summarization, extraction, first-pass drafts | DeepSeek, Qwen, GPT mini-class models |
| `cheap_fast` | formatting, small rewrites, JSON repair, Hermes summaries | GPT mini-class, local small model |
| `strong_reasoning` | final one-pager, prioritization, claim audit, strategy | best available reviewer model |
| `no_model` | tracking, approval checks, deterministic validation | Python code |

Provider routing rules:

1. Broad reading goes cheap.
2. Final artifact synthesis goes strong.
3. QA uses deterministic checks first, then strong review if needed.
4. Tracking and approvals use no model.
5. If a model route fails or gets expensive, the harness can downshift, chunk, summarize, or ask for approval before continuing.

Do not depend on unauthorized provider rerouting. If we build a Claude-Code-like local adapter, it should be a legitimate provider abstraction for models we are allowed to call, not credential bypassing.

## Harnesses to build

1. **Agent Harness**
   Typed input, typed output, model route, budget, validators, retries, W&B logging.

2. **Model Harness**
   Provider adapter, JSON schema enforcement, token counting, cost estimate, cache key, failure policy.

3. **Source Harness**
   Fetch pages, store text snapshots, dedupe URLs, track retrieval time, preserve citation trail.

4. **Action Harness**
   Approval-matched external actions. Blocks send/schedule/connect/message/cloud-write unless the exact intent is approved.

5. **Scheduler Harness**
   Hermes/Telegram daily status: what completed, what failed, what needs user decision, what is due today.

## Harness adapters to study

Claude Code, Codex, and open-source coding agents are useful because they prove the harness pattern: a model becomes more useful when it has tools, state, budgets, validation, and a controlled environment. For UpSearch, these systems should be adapters behind our product contract, not the product itself.

| Adapter pattern | What to borrow | What not to copy |
| --- | --- | --- |
| Codex / Claude Code style | Repo-aware tools, shell access, file edits, test loops, approval-sensitive actions. | Do not make coding the only workflow or expose external account actions without approval. |
| [OpenHands](https://github.com/OpenHands/OpenHands) style | Agent SDK, CLI, local GUI, REST API, sandboxed runtime, scalable agent execution. | Do not start by adopting the whole runtime before the packet state model is stable. |
| [Aider](https://github.com/aider-ai/aider) style | Git-first edits, codebase maps, model flexibility, lint/test feedback, cheap model compatibility. | Do not treat git commits as the right primitive for sourcing, people maps, or outreach. |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) style | Task specs, agent-computer interface, configurable YAML, reproducible environments. | Do not use it for fuzzy research without a source harness and citation ledger. |

The first demo should show this as a replaceable execution layer. If browser automation slows us down, swap it. If a model route gets expensive, downshift. If a connector fails, fall back to manual handoff while preserving the packet and ledger.

## Recommended outputs

The system should make recommendations rather than ask the user to choose everything.

Default packet:

1. Recommended company.
2. Recommended problem angle.
3. Recommended first person.
4. Recommended channel.
5. Recommended artifact.
6. Recommended message.
7. Required approval decision.

User decisions should be reserved for:

1. Pick lane or accept recommended lane.
2. Approve final technical note if it represents the user.
3. Approve exact send target, channel, message, attachments, and timing.
4. Reject or edit voice/tone after seeing examples.

## Hermes scheduler role

Hermes should not do deep reasoning by default. It should be a status and reminder surface.

Daily Telegram brief:

```text
UpSearch Daily

Done:
- Built Baseten packet.
- QA passed.
- Bola connection request pending.

Needs decision:
- Approve Raymond connection note?
- Start Modal packet?

Due today:
- Follow up on any accepted LinkedIn connections.

Blocked:
- Drive write scopes missing.
```

Hermes jobs should read from the W&B/local ledger, not regenerate everything from scratch.

## Hosting path

Phase 1 should run locally.

Phase 2 can use a small server:

1. FastAPI backend for orchestration and packet state.
2. SQLite locally, Postgres when shared.
3. React frontend already started.
4. Background queue for long sourcing runs.
5. W&B for experiment and artifact tracking.
6. Hermes for scheduled Telegram summaries.

CoreWeave role:

1. Host batch sourcing workers.
2. Run scraping/browser workers if needed.
3. Run model-calling workers for large queues.
4. Emit all telemetry to W&B.

Do not move to server orchestration before local Baseten -> Modal -> Fireworks packets work end to end.

## 3-minute presentation

### 0:00 to 0:30: Problem

Early-career technical people do not just need more job links. They need a way to turn broad interests into specific, credible conversations with the right teams.

### 0:30 to 1:00: Thesis

UpSearch is an opportunity intelligence system. Given little user input, it builds company-specific technical packets: who to contact, what problem to discuss, what artifact to show, and how the user's adjacent experience maps to the problem.

### 1:00 to 1:45: System

The orchestrator coordinates specialist agents: profile, company sourcing, problem discovery, people sourcing, technical note, outreach, QA, and action. Each agent runs inside a harness with typed inputs, typed outputs, source requirements, model budgets, and W&B logging.

### 1:45 to 2:20: Differentiation

This is not Simplify, Indeed, LinkedIn, or bulk application automation. The unit of value is a high-quality technical conversation, not message volume.

### 2:20 to 2:45: Execution

Phase 1 focuses on AI infrastructure and inference. Baseten is the validated seed case. Next is making the pipeline recreate Baseten automatically, then repeating with Modal, Fireworks, and Together.

### 2:45 to 3:00: Ask

We need to build the harnesses: model routing, source capture, W&B ledger, approval-safe action layer, and a simple UI that keeps the user focused on only the key decisions.

## Q&A prep

**Why not just use LinkedIn or Indeed?**
Because they optimize discovery and applications. UpSearch optimizes technical context and warm conversation quality.

**Why multi-agent?**
The work decomposes naturally: sourcing, reading, person matching, proposal writing, QA, and action each need different tools, budgets, and failure checks.

**How do you prevent spam?**
External actions require explicit approval. The system recommends one high-quality action at a time and tracks outcomes.

**How do you control cost?**
Cheap models handle broad extraction. Strong models are reserved for final synthesis and QA. Deterministic code handles tracking and approvals.

**Where does W&B fit?**
W&B is the run ledger: model choice, cost, sources, artifacts, approval state, send state, and outcomes.

**Where does CoreWeave fit?**
CoreWeave is the scale-out runtime for sourcing and worker jobs after local orchestration works.

## Immediate build order

1. Freeze the Phase 1 schemas.
2. Add machine-readable agent specs.
3. Build source snapshot storage.
4. Add model provider interface with DeepSeek first.
5. Add W&B run logging for every harness call.
6. Generate Baseten packet from structured tasks, not hardcoded seed.
7. Wire the frontend to show packet state and approval gates.
8. Add Hermes daily brief from the ledger.
