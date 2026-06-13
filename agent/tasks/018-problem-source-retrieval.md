# Task 018: Problem Sources From All Retrieval Channels

## Goal

Run 3 of the live Baseten packet cleared identity but blocked at the problem
gate ("Source URLs may be fabricated"). Cause: `agents/problem.py` allowed the
model to cite only HN/Reddit URLs while showing it DDG web/blog results it was
forbidden (by sanitization) from citing; with HN/Reddit empty, every real
problem was stripped, the synthesized fallback fired, and the checkup gate
correctly blocked. Make every retrieval channel a first-class source.

## Read

- `agents/problem.py`
- `upsearch/packet_checkup.py` (only `_problem_source_candidate_count` and
  `unverified_model_sources`)
- `upsearch/orchestrator_service.py` (only the problem stage trace emission)
- `tests/test_problem_evidence.py`

## Write Scope

- `agents/problem.py`
- `tests/test_problem_evidence.py`
- `.upsearch/agent-runs/018-problem-source-retrieval-handoff.md`

## Required Behavior

1. HN/Reddit posts, DDG web results, and site-specific blog results merge
   into one deduplicated source catalog; the model may cite any catalog URL
   and only catalog URLs survive sanitization.
2. The agent's returned `source_urls` reports the catalog, so the trace's
   `source_candidates=` count reflects all retrieval output and the
   fabrication gate stays truthful.
3. Lane keys are naturalized (`ai_infra` -> `ai infra`) before being used as
   web-search terms.
4. The conservative fallback and its identity-gated website rule stay
   unchanged.

## Commands

```bash
uv run pytest -q tests/test_problem_evidence.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
