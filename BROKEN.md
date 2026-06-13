# UpSearch — Things That Need Work (June 7, 2026)

## Fixed since the initial list
- ✅ QA model execution: `model_execution.py` now uses `deepseek-chat` instead of the invalid `deepseek-v4-flash` model name. QA calls work and return real evaluations.
- ✅ Profile proof points in QA context: `agents/qa.py` now injects the user's proof bank from the enriched profile into the LLM evaluation prompt. QA can distinguish "unsupported claim" from "this claim matches a known proof point."
- ✅ DeepSeek model fallback: `model_execution.py` validates the model name and defaults to `deepseek-chat` if the env-configured model isn't valid.
- ✅ Idle rediscovery: `--duration` now correctly triggers idle rediscovery instead of draining and exiting. Rediscovery interval defaults to 3600s (1 hour). Verified with 5s test: 2 idle cycles, 6 total jobs, 0 failures.
- ✅ Broader company discovery: `auto_discovery.py` now extracts from "Launch HN", "Hiring CompanyName", and title-separator patterns. Falls back to unverified candidates when identity resolution fails. Generic-word filter prevents non-company names. Now returns candidates across 3-4 lanes instead of 0.

## Still broken or not done

### P0 — QA quality needs a strong-model route and a fixed evaluation set
Even with `deepseek-chat` working and profile proof points in context, DeepSeek isn't Claude. The model router sends QA through the cheap route because `strong_model` defaults to `manual-review`. Fix: configure environment var. This is an operational fix, not a code fix.

### P1 — People sourcing needs broader live validation
Company-owned team pages, GitHub organizations, and author pages are now wired,
but coverage still varies by company. The next proof point is an end-to-end
evaluation across Baseten, Modal, Fireworks, and Together rather than more
prompt changes.

### P1 — Company discovery quality needs a fixed benchmark
HN, Reddit, RSS, web search, and GitHub signals are available. The remaining
question is precision: whether the system consistently discovers companies
that match the user's lane and have enough evidence for a trustworthy packet.

### P1 — Opportunity OS metrics are not yet wired end to end
The local-first, privacy-filtered W&B tracker core is complete. The orchestrator
still needs to emit route, latency, source count, verification state, QA score,
retry count, and final packet status through that tracker.

### P2 — No golden end-to-end acceptance run
The system needs repeatable acceptance fixtures for at least Baseten and Modal:
profile ingestion, company research, source-backed problems, verified people,
technical note, outreach, QA, trace, approval record, and follow-up state.

### P2 — External action recovery is not fully proven
Approval and platform handoffs exist, but connector failure, retry, duplicate
send prevention, and exact approval matching need explicit integration tests.

### P3 — Deployment and operational recovery are incomplete
The application still needs a documented production runtime, database backup
and migration handling, health checks, and restart-safe background workers.

### P3 — Quick Search + OS remain fused in the same server
This is architectural debt rather than a current product blocker.

## Honest assessment
The architecture runs and the main harness layers are now covered by 143 tests.
The remaining work is proving output quality on fixed companies, wiring metrics
through the full run, strengthening QA routing, and validating action/deployment
recovery. None of those require a rewrite.
