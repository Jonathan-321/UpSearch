# Multi-Agent Orchestrator Plan

Last updated: 2026-05-31

## Goal

Build UpSearch as a multi-agent opportunity intelligence system for technical people. The system should source companies, discover real technical problems, identify relevant people, generate credible one-page project proposals, draft human outreach, verify claims, and track outcomes.

The first user is Jonathan. The first lane is AI infrastructure and inference systems. The first validated case is Baseten.

## Non-negotiables

1. Cost-aware model routing.
2. DeepSeek support for cheap, high-token research and drafting passes.
3. Stronger models reserved for synthesis, final technical notes, and QA.
4. W&B as the execution ledger for every run.
5. CoreWeave as the planned GPU/cloud runtime surface for hosted workers and scheduled jobs.
6. Human approval before external actions.
7. No secrets in source control.
8. Browser automation is a replaceable connector, not a platform dependency.

## System loop

```text
User profile
  -> company sourcing
  -> company shortlist
  -> problem discovery
  -> people sourcing
  -> technical note
  -> outreach drafts
  -> verification
  -> approval gate
  -> send or schedule
  -> follow-up tracking
```

Each step should produce two outputs:

1. Structured JSON for downstream agents.
2. A human-readable artifact for review.

## Agent roles

| Agent | Responsibility | Preferred model tier |
| --- | --- | --- |
| Profile Agent | Parse resume, GitHub, projects, constraints, interests, and proof angles. | Cheap model first, stronger model for final profile summary. |
| Company Sourcing Agent | Find companies by lane and score fit, sponsorship signal, hiring stage, and technical overlap. | DeepSeek or other cheap high-context model. |
| Problem Discovery Agent | Read blogs, docs, papers, HN, Reddit, GitHub, jobs, and LinkedIn posts to extract open problems. | DeepSeek for extraction, stronger model for prioritization. |
| People Sourcing Agent | Find engineers, researchers, founders, FDEs, hiring managers, and recruiters. | Cheap model plus browser/search tools. |
| Technical Note Agent | Convert company/problem evidence into a one-page technical proposal. | Stronger model for final synthesis. |
| Outreach Agent | Draft LinkedIn notes, emails, follow-ups, and accepted-connection messages. | Cheap draft pass, stronger model for final voice polish. |
| QA Agent | Check sources, word count, claims, tone, missing evidence, and approval gates. | Stronger model or deterministic validators. |
| Orchestrator | Own task graph, state, retries, approvals, model routing, and W&B logging. | Deterministic code plus task-specific model calls. |

## Harness principle

The durable product is the harness around the model, not any one model or browser.

Every agent should run inside a harness that defines:

1. Input schema.
2. Output schema.
3. Source requirements.
4. Token and cost budget.
5. Validation checks.
6. W&B logging fields.
7. Retry rules.
8. Approval gates for any external action.

This lets the system swap DeepSeek, a stronger reviewer model, a browser connector, a direct API, or a manual handoff without changing the core workflow.

## Model routing strategy

The orchestrator should choose models by job shape, not by a single default.

| Task type | Default choice | Reason |
| --- | --- | --- |
| Broad source extraction | DeepSeek API | High token volume and lower cost. |
| Page summarization | DeepSeek API | Good for cheap map/reduce over many pages. |
| Candidate ranking | DeepSeek API, then stronger reviewer if needed | Ranking needs breadth first, precision second. |
| Final one-pager | Strong model | Needs judgment, technical coherence, and clean prose. |
| Outreach draft | Cheap model for variants, strong model for final | Generate options cheaply, polish carefully. |
| QA and claim audit | Strong model plus deterministic checks | Avoid fabricated claims and weak sourcing. |
| Tracking/logging | No model | Deterministic code path. |

Initial provider interface:

```text
LLMProvider
  - name
  - model
  - max_context_tokens
  - input_cost_per_million
  - output_cost_per_million
  - supports_json
  - supports_tool_calls
  - call(messages, response_schema, budget)
```

Required environment variables:

```text
DEEPSEEK_API_KEY
WANDB_API_KEY
WANDB_PROJECT
WANDB_ENTITY
```

Optional environment variables:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
COREWEAVE_NAMESPACE
COREWEAVE_CLUSTER
```

No provider key should ever be copied into a doc, fixture, prompt log, or commit.

## W&B tracking

W&B should track the system like an experiment and operating ledger, not only model metrics.

Run types:

1. `profile_ingest`
2. `company_sourcing`
3. `problem_discovery`
4. `people_sourcing`
5. `technical_note`
6. `outreach_draft`
7. `verification`
8. `approval_gate`
9. `send_action`
10. `follow_up`

Core fields:

| Field | Example |
| --- | --- |
| `run_id` | Unique orchestrator run id. |
| `user_id` | Local user or account id. |
| `company` | Baseten. |
| `lane` | AI infra, inference. |
| `agent` | Problem Discovery Agent. |
| `model_provider` | deepseek. |
| `model_name` | configured model id. |
| `input_tokens` | Count from provider or tokenizer. |
| `output_tokens` | Count from provider or tokenizer. |
| `estimated_cost_usd` | Model cost estimate. |
| `source_urls` | List of evidence URLs. |
| `artifact_paths` | Generated local or cloud artifacts. |
| `approval_status` | pending, approved, rejected. |
| `external_action` | none, draft_created, sent, scheduled. |

Artifacts to log:

1. Company dossier JSON.
2. Problem evidence JSON.
3. People map JSON.
4. Technical note Markdown.
5. Outreach drafts.
6. QA report.
7. Final send packet.

## CoreWeave role

CoreWeave should be treated as the scalable runtime target, not the tracking system itself.

Planned use:

1. Run scheduled sourcing jobs.
2. Host browser or scraping workers where appropriate.
3. Run batched problem discovery over many companies.
4. Run queue workers for model calls.
5. Emit all run telemetry and artifacts to W&B.

Local development should remain simple first. The CoreWeave path should come after the local orchestrator can complete a Baseten-style packet end to end.

## Connector strategy

The action layer should choose the fastest reliable connector available for the job.

| Connector | Preferred use | Risk note |
| --- | --- | --- |
| Gmail API | Creating drafts, sending approved email, scheduling approved email. | Requires correct OAuth scopes and explicit approval for sends. |
| Google Drive API | Creating, reading, writing, and uploading docs. | Use when create/edit scopes are available. |
| Codex browser | Authenticated LinkedIn or web workflows. | Useful fallback when API access is unavailable. |
| Tandem browser | Browser workflows if stable in the user session. | Helpful but not required. |
| Chrome | User-profile-dependent pages and sessions. | Good for logged-in surfaces. |
| Manual handoff | Anything flaky or high-risk. | Always acceptable; preserves user control. |

The orchestrator should never care whether an approved LinkedIn connection request is executed through Tandem, Codex browser, Chrome, or a future API. It should only care that the action intent matches the approval record and that the outcome is logged.

## State model

Minimum tables or JSON collections:

| Entity | Key fields |
| --- | --- |
| `UserProfile` | skills, projects, proof_bank, constraints, target_lanes. |
| `Company` | name, website, careers_url, lanes, fit_score, sponsorship_signal. |
| `Problem` | company_id, title, evidence_urls, problem_summary, buildable_angle. |
| `Person` | company_id, name, role, relevance_reason, profile_urls, channel_status. |
| `Artifact` | type, path, company_id, problem_id, version, source_run_id. |
| `OutreachDraft` | person_id, channel, subject, body, word_count, approval_status. |
| `ActionLog` | action_type, target, timestamp, approval_id, status, follow_up_date. |

Start with SQLite or local JSONL. Move to Postgres only after the schema stabilizes.

## MVP milestones

### P0: Product brief and seed corpus

1. Import the Oppprep seed materials.
2. Preserve the Baseten execution record.
3. Define the orchestrator plan and safety rules.

### P1: Local structured packet generator

Input:

```text
company name + lane + user profile
```

Output:

```text
company dossier
problem brief
people map
technical note
outreach drafts
QA report
```

Use local files and W&B logging.

### P2: Model router

1. Add DeepSeek provider.
2. Add provider abstraction.
3. Add per-agent model budgets.
4. Track token and cost estimates in W&B.

### P3: Approval workflow

1. Draft-only external integrations.
2. Explicit approval records.
3. Send action blocked unless approved.
4. Follow-up reminders after send.

### P4: Scalable workers

1. Move batch sourcing workers to CoreWeave.
2. Add queue-based orchestration.
3. Keep W&B as the run ledger.
4. Add dashboard views for company, problem, people, and outcome metrics.

## First build target

Recreate the Baseten result automatically from structured inputs.

Success criteria:

1. The system sources Baseten from public evidence.
2. It identifies continual-learning inference as the core problem.
3. It produces a credible adapter-aware routing one-pager.
4. It identifies three relevant people.
5. It drafts three outreach messages under 200 words.
6. It logs every step to W&B.
7. It stops at approval before sending.

After Baseten works, repeat with Modal, Fireworks AI, and Together AI.
