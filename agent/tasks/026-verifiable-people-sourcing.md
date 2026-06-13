# Task 026: Verifiable People Sourcing Depth

## Goal

After the person-name gate, the Fireworks packet had four real names but
zero verifiable people: hallucinated founders fail evidence checks
(correctly), LinkedIn sources cannot be fetched, and the GitHub fallback
never fired because it triggered on raw candidate count, not verified
count — and its org guesser accepted bare name matches (the real Fireworks
org is `fw-ai`, which no guess produces, while `fireworks-ai` exists and
belongs to a different company). Make the pipeline reliably find people it
can verify.

## Read

- `agents/people.py`
- `upsearch/github_org_search.py`
- `upsearch/sourcing/company_people.py`

## Write Scope

- `agents/people.py`
- `upsearch/github_org_search.py`
- `upsearch/sourcing/company_people.py`
- `tests/test_people_sourcing_depth.py` (new)
- `.upsearch/agent-runs/026-verifiable-people-sourcing-handoff.md`

## Required Behavior

1. The GitHub fallback triggers on verified scarcity (fewer than two
   verified people after verification), not on raw candidate count.
2. `find_company_org` resolves the company's org with metadata
   confirmation: website == verified company domain accepts; a declared
   website that disagrees with the domain vetoes regardless of name; bare
   name equality (plus ai/hq/labs/inc suffixes) accepts only when the org
   declares no website. Name guesses that miss fall back to the GitHub org
   search API, confirmed the same way.
3. `search_org_members` falls back from (often hidden) public org members
   to top-repo contributors, skips bots, cleans display-name parentheticals
   ("Yufei (Benny) Chen" -> "Yufei Chen"), and never pre-claims
   verification status — the evidence pipeline decides.
4. The company-people connector discovers same-domain `/author/<slug>`
   links from seed pages (one hop, bounded) and extracts the author's name
   from those pages' title/h1; author pages double as verification sources.
5. Tests cover all of the above without network; live spot-checks resolve
   Fireworks -> fw-ai and Baseten -> basetenlabs.

## Commands

```bash
uv run pytest -q tests/test_people_sourcing_depth.py tests/test_person_validation.py tests/test_company_people_source.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
