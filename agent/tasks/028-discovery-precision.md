# Task 028: Discovery Freshness And Lane Precision

## Goal

A live probe returned 9 candidates with only ~1/9 lane-matched by the code's
own matcher. Causes: HN Algolia had no date filter (2017–2020 posts surfaced),
unauthenticated Reddit search 403s and is swallowed silently, the system.yaml
lane `ai_infrastructure_and_inference` is not a `LANE_KEYWORDS` key so it
degrades to a literal-string search, and HN/Reddit-derived candidates skip the
`_matches_lane_signal` gate that github/RSS candidates pass through. Make
discovery fresh and lane-precise without zeroing out recall.

## Read

- `upsearch/auto_discovery.py` (lane keywords, `_matches_lane_signal`,
  `discover`)
- `upsearch/sourcing/hackernews.py`
- `upsearch/sourcing/reddit.py`
- `tests/test_discovery_sources.py`
- `tests/test_auto_discovery.py`

## Write Scope

- `upsearch/auto_discovery.py`
- `upsearch/sourcing/hackernews.py`
- `upsearch/sourcing/reddit.py`
- `tests/test_discovery_precision.py`
- `.upsearch/agent-runs/028-discovery-precision-handoff.md`

## Required Behavior

1. HN Algolia queries carry a `numericFilters` `created_at_i` lower bound
   (default last 540 days), overridable per call (`max_age_days=None`
   disables it). Public function signatures stay backward compatible.
2. A lane alias map resolves canonical lane names:
   `ai_infrastructure_and_inference` -> `["ai_infra", "inference_systems"]`,
   accepting hyphen/space variants. `discover(lane)` with an alias expands to
   its mapped lanes and merges results; unknown lanes keep the existing
   literal-keyword degrade behavior.
3. HN/Reddit-derived candidates pass the same lane-signal gate as github/RSS.
   Escape hatch: post titles with hiring/launch markers ("Launch HN",
   "Show HN", "is hiring") pass a weaker bar — ANY single lane term in the
   title. The fallback-to-unverified-candidates behavior is unchanged.
4. Reddit search uses a browser-style User-Agent against
   `old.reddit.com/r/<sub>/search.json`; if still blocked (403/429), keep
   explicit-empty (no fabrication) and log once per run at info level.
5. No live network in tests; mock all HTTP.

## Commands

```bash
uv run pytest -q tests/test_discovery_precision.py tests/test_discovery_sources.py tests/test_auto_discovery.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
