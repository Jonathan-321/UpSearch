# Task 001: Company-Owned People Source Connector

## Goal

Improve people sourcing by retrieving candidates from company-owned team,
author, and engineering-blog pages before asking the model to rank them.

## Read First

- `agents/people.py`
- `upsearch/person_verification.py`
- `upsearch/company_identity.py`
- `tests/test_person_verification.py`

## Write Scope

- `upsearch/sourcing/company_people.py` (new)
- `agents/people.py`
- `tests/test_company_people_source.py` (new)

Do not change `person_verification.py` unless an acceptance test demonstrates a
bug in its existing evidence contract.

## Required Behavior

1. Accept a verified company website/domain and candidate page URLs.
2. Fetch only public HTTP pages on the verified company domain.
3. Extract candidate names, roles, source URLs, and short evidence snippets.
4. Return an empty list on fetch, parse, or evidence failure.
5. Feed retrieved candidates into the existing `verify_people` path.
6. Never synthesize LinkedIn, GitHub, X, or email addresses.
7. Preserve current Baseten behavior without a hardcoded trust bypass.

## Acceptance Criteria

- Off-domain pages are rejected.
- A person without name and company evidence is not verified.
- Network failure produces no fabricated fallback person.
- Duplicate people are merged by normalized name.
- Existing people-verification tests remain green.

## Commands

```bash
uv run pytest -q tests/test_company_people_source.py tests/test_person_verification.py
uv run pytest -q
git diff --check
```

## Stop Conditions

Stop and report a blocker if this requires authenticated LinkedIn access,
browser automation, or changing the company identity policy.
