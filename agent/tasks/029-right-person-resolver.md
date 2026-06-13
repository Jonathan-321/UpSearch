# Task 029: Right-Person Resolver

## Goal

Outreach converts; scaling now depends on reliably reaching the RIGHT
person with verified info. People ranking was model-vibes relevance over
whoever happened to be visible. Make person-to-problem proximity
deterministic and evidence-backed: the author of the source the packet
cites is the most-proximate person, contributors of the problem-relevant
repo come next, and verification stops paying a redundant-fetch tax.

## Read

- `agents/people.py`
- `upsearch/sourcing/company_people.py`
- `upsearch/github_org_search.py`
- `upsearch/person_verification.py`

## Write Scope

- `agents/people.py`
- `upsearch/sourcing/company_people.py`
- `upsearch/github_org_search.py`
- `upsearch/person_verification.py`
- `tests/test_people_sourcing_depth.py`
- `.upsearch/agent-runs/029-right-person-resolver-handoff.md`

## Required Behavior

1. `author_from_post_url(post_url, domain)` resolves the author of a cited
   company post (author page preferred, byline fallback, name-gated); the
   people agent seeds cited-source authors at the head of the pool with
   relevance 10 and proximity "author". Unattributed pages yield None.
2. GitHub contributor sourcing ranks org repos by problem-keyword overlap
   (name/description/topics) before recency; contributors of a matched repo
   carry relevance 8 and a reason naming the repo. Keywords derive
   deterministically from the problem title/description.
3. `check_github_org_evidence` accepts a per-batch memo; `verify_people`
   shares one memo so an org profile and a contributors listing are fetched
   once per packet, not once per person.
4. All candidates still face the unchanged name gate and evidence-first
   verification; nothing pre-claims verified status.

## Commands

```bash
uv run pytest -q tests/test_people_sourcing_depth.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
