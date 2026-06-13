# Task 033: Identity Evidence Robustness

## Goal

A live user test blocked two packets wrongly explained: Databricks failed
"technical-lane evidence" because its site serves the verifier a contentless
JS shell, and a typo'd "Oblivious GPU Cloud" first blocked with an opaque
reason, then (after the shell fix) wrongly VERIFIED against oblivious.com —
an unrelated company sharing the first word — because host match satisfied
the page-name check. Make identity evidence robust to JS shells and strict
about full-name agreement, and make rejections name the nearest real site.

## Read

- `upsearch/company_identity.py`
- `upsearch/packet_checkup.py` (failure categories)

## Write Scope

- `upsearch/company_identity.py`
- `upsearch/packet_checkup.py`
- `tests/test_company_identity_fallback.py`
- `tests/test_people_hygiene.py` (one checkup test)
- `.upsearch/agent-runs/033-identity-evidence-robustness-handoff.md`

## Required Behavior

1. `fetch_page` parses meta description/og:description/keywords into the
   evidence text, and when the first fetch returns a titleless shell it
   retries once with a browser User-Agent.
2. `page_name_match` requires the page to carry every significant name
   token (corporate suffixes excluded) or the exact name in the title; a
   host matching only the first word no longer satisfies it.
3. When every fallback fails, the returned rejection appends
   "Closest fetched candidate: <domain>." so typos explain themselves.
4. Checkups on identity-blocked packets report `failure_category`
   "identity_blocked" with a precise fix; empty problems/people are treated
   as symptoms, not separate failures. `decide_action` blocks with an
   identity-specific reason.
5. Live matrix: Databricks verifies; "Oblivious GPU Cloud" rejects with the
   oblivious.com hint; "Oblivus GPU Cloud" verifies; Baseten/Together AI
   unchanged.

## Commands

```bash
uv run pytest -q tests/test_company_identity_fallback.py tests/test_people_hygiene.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
