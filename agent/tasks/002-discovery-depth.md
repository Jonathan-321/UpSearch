# Task 002: Broaden Verified Company Discovery

## Goal

Increase useful rediscovery results without allowing an unverified company to
reach downstream packet generation.

## Read First

- `upsearch/auto_discovery.py`
- `upsearch/company_identity.py`
- `upsearch/github_signal.py`
- `upsearch/sourcing/rss_feeds.py`
- `upsearch/sourcing/web_search.py`
- `tests/test_auto_discovery.py`
- `tests/test_scheduler_identity_gate.py`

## Write Scope

- `upsearch/auto_discovery.py`
- `upsearch/github_signal.py`
- `upsearch/sourcing/rss_feeds.py`
- `upsearch/sourcing/web_search.py`
- `tests/test_auto_discovery.py`
- `tests/test_discovery_sources.py` (new)

## Required Behavior

1. Add company-owned engineering blogs, public GitHub organization signal, or
   curated RSS sources as discovery inputs.
2. Preserve source URLs and source labels.
3. Deduplicate by verified official domain.
4. Keep unverified candidates visible as leads, but do not bypass the scheduler
   identity gate.
5. Return empty results honestly when sources fail.

## Acceptance Criteria

- Multiple source types can contribute to one candidate.
- Identity confidence never increases merely because duplicate aggregator
  pages mention the same name.
- Repeated rediscovery does not enqueue the same verified domain.
- Existing scheduler rediscovery and identity-gate tests remain green.

## Commands

```bash
uv run pytest -q tests/test_auto_discovery.py tests/test_discovery_sources.py tests/test_scheduler_identity_gate.py
uv run pytest -q
git diff --check
```
