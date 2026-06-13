# Task 022: Deterministic Person-Name Gate

## Goal

Live packets showed website navigation labels ("Pricing", "Platform", "Use
Cases"), group placeholders ("Fireworks GitHub Contributors", "ML Systems
Engineers"), and blog titles ("Frontier RL Is Cheaper Than You Think", role
"3/10/2026") as scored people with "Public source" links. Evidence checks
cannot reject these: they only prove a string appears on a company page,
which nav labels do by definition. Add a deterministic is-this-a-human-name
gate and apply it at every layer of the people pipeline.

## Read

- `upsearch/sourcing/company_people.py`
- `upsearch/person_verification.py`
- `agents/people.py`
- `tests/test_company_people_source.py`

## Write Scope

- `upsearch/person_validation.py` (new)
- `upsearch/sourcing/company_people.py`
- `upsearch/person_verification.py`
- `agents/people.py`
- `tests/test_person_validation.py` (new)
- `tests/test_company_people_source.py` (fixture name only)
- `.upsearch/agent-runs/022-person-name-gate-handoff.md`

## Required Behavior

1. `person_validation.person_name_rejection(name)` rejects: empty/oversize
   strings, digits/dates, single tokens, >4 tokens, nav/marketing vocabulary
   tokens, group nouns, acronym tokens, malformed capitalization. Real names
   (including initials and lowercase particles) pass.
2. The company-people connector drops non-name candidates at extraction.
3. `verify_person` rejects non-names with reason `not_a_person_name:<why>`
   without fetching anything.
4. The people agent filters its merged candidate pool through the gate
   before verification, and curated seed candidates merge additively instead
   of replacing live sourcing.
5. Tests pin the exact junk strings observed in production screenshots.

## Commands

```bash
uv run pytest -q tests/test_person_validation.py tests/test_company_people_source.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
