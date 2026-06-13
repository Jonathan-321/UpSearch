# Task 017: Official-Domain Fallback For Company Identity

## Goal

A live Baseten run blocked at the identity gate because discovery evidence was
polluted by a competitor's "Show HN" link (hyperpodai.com), and nothing ever
attempted Baseten's real official domain. Add a deterministic fallback that
probes name-derived domains and an official-site web search when discovery
evidence fails verification. The strict identity scorer remains the only
judge; this widens the candidate pool, never the verification bar.

## Read

- `upsearch/company_identity.py`
- `agents/company.py`
- `upsearch/sourcing/web_search.py`
- `tests/test_company_agent.py`

## Write Scope

- `upsearch/company_identity.py`
- `agents/company.py`
- `tests/test_company_identity_fallback.py` (new)
- `tests/test_company_agent.py` (monkeypatch points only)
- `.upsearch/agent-runs/017-company-identity-official-domain-fallback-handoff.md`

## Required Behavior

1. `official_site_candidates(name)` returns name-derived domain guesses
   (`https://<normalized>.com/.ai/.co/.io`), empty for empty names.
2. `resolve_company_identity_with_fallback(...)` first resolves from the
   given discovery evidence; when rejected it tries, in order: the domain
   probes, then a DuckDuckGo `"<name> official website"` search (existing
   free connector, injectable for tests). The search runs only if the probes
   fail. Each batch is re-verified by the unchanged strict scorer.
3. When no fallback candidate verifies, the returned rejection is the
   highest-confidence one, so the operator sees the most informative reason.
   Network failure remains an explicit fetch-failure state, never a guess.
4. `agents/company.py` uses the fallback resolver for the initial identity
   attempt; the model-website-candidate re-verification stays as is.
5. Tests require no network: fetcher and search are injected fakes.

## Commands

```bash
uv run pytest -q tests/test_company_identity_fallback.py tests/test_company_agent.py tests/test_company_identity.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
