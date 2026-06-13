# Task 016: OpenRouter Route And Visible Config Validation

## Goal

Unblock real model execution. The operator's environment has an OpenRouter key
but no DeepSeek key, so every agent call silently degrades to keyword
heuristics and the strong QA route reports unconfigured, which fails QA closed
and blocks all approvals. Make OpenRouter a first-class provider for the cheap
agent path, make the router's cheap route configurable, and make missing model
configuration loudly visible at startup instead of silently degrading.

## Read

- `.upsearch/agent-runs/015-profile-identity-provenance-handoff.md`
- `upsearch/llm.py`
- `upsearch/config.py`
- `upsearch/model_router.py`
- `upsearch/model_execution.py`
- `upsearch/qa_execution.py`
- `tests/test_qa_model_routing.py`
- `server.py`, only health and startup sections

## Write Scope

- `upsearch/llm.py`
- `upsearch/config.py`
- `upsearch/model_router.py`
- `upsearch/startup_validation.py` (new)
- `server.py` (startup hook and one new read-only endpoint)
- `.env.example`
- `tests/test_model_provider_config.py` (new)
- `.upsearch/agent-runs/016-openrouter-route-and-config-validation-handoff.md`

Do not edit `.env`. Do not change the frontend. Do not change QA fail-closed
semantics: an unconfigured route must still degrade and block approval.

## Required Behavior

1. `MODEL_PROVIDER=openrouter` routes all agent completions (including tool
   use) through OpenRouter using `OPENROUTER_API_KEY`, with the model slug
   from `OPENROUTER_MODEL` (default `deepseek/deepseek-chat`).
2. The router's cheap route honors `UPSEARCH_CHEAP_MODEL_PROVIDER` and
   `UPSEARCH_CHEAP_MODEL`. Defaults preserve today's behavior exactly
   (`deepseek` / `DEEPSEEK_MODEL`).
3. A strong route of `openrouter` + a model slug reports `configured=True`
   when `OPENROUTER_API_KEY` is present and is not marked fallback, so QA
   runs for real.
4. `upsearch/startup_validation.py` exposes `model_config_problems(settings)`
   returning explicit operator-readable problems: agent provider key missing,
   strong model unconfigured or its key missing, `GITHUB_TOKEN` missing.
5. Server startup logs each problem, and `UPSEARCH_REQUIRE_MODELS=1` turns
   problems into a startup failure. A read-only
   `GET /api/config/model-status` endpoint returns providers, models, and
   problems.
6. No behavior change when the new env vars are unset; the existing QA
   routing tests keep passing unchanged.
7. Tests require no network and must not depend on the developer's real
   environment keys (explicitly set or delete env vars in each test).

## Commands

```bash
uv run pytest -q tests/test_model_provider_config.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
