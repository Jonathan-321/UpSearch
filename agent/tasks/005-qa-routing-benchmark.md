# Task 005: Strong-Model QA Routing And Benchmark

## Goal

Make verification quality measurable and ensure judgment-heavy QA uses the
configured strong model without silently falling back to a cheap model.

## Read

- `upsearch/model_router.py`
- `upsearch/qa_execution.py`
- `agents/qa.py`
- `tests/test_qa_model_routing.py`

## Write Scope

- `upsearch/model_router.py`
- `upsearch/qa_execution.py`
- `agents/qa.py`
- `tests/test_qa_model_routing.py`
- `tests/fixtures/qa_benchmark.json` (new)
- `tests/test_qa_benchmark.py` (new)
- `.upsearch/agent-runs/005-qa-routing-benchmark-handoff.md`

## Required Behavior

1. Verification and final technical-note judgment use the configured strong
   route when its provider is available.
2. Missing or failed strong routes produce an explicit degraded result and
   never claim that strong verification occurred.
3. Add a fixed offline benchmark containing supported claims, unsupported
   claims, missing sources, weak people evidence, and overlong outreach.
4. The deterministic and model-result merge must fail closed on unsupported
   claims and missing evidence.
5. Tests use fake model responses and require no network or credentials.

## Commands

```bash
uv run pytest -q tests/test_qa_model_routing.py tests/test_qa_benchmark.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
