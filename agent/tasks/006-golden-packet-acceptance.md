# Task 006: Golden End-To-End Packet Acceptance

## Goal

Create repeatable acceptance runs for Baseten and Modal that prove the complete
packet contract without depending on live network availability.

## Read

- `upsearch/harnessed_orchestrator.py`
- `upsearch/packet_checkup.py`
- `upsearch/schemas.py`
- `tests/test_problem_evidence.py`
- `tests/test_company_people_source.py`

## Write Scope

- `upsearch/acceptance.py` (new)
- `tests/fixtures/golden/baseten.json` (new)
- `tests/fixtures/golden/modal.json` (new)
- `tests/test_golden_packets.py` (new)
- `scripts/run-golden-acceptance.sh` (new)
- `.upsearch/agent-runs/006-golden-packet-acceptance-handoff.md`

## Required Behavior

For both companies, verify:

1. Verified company identity and source-backed fit.
2. At least one specific technical problem with stored evidence.
3. At least one evidence-verified relevant person.
4. A technical note with a concrete contribution and evaluation criteria.
5. Honest adjacent-proof mapping.
6. Outreach within channel limits.
7. QA/checkup result, complete trace, and exact approval requirement.
8. Deterministic fixture mode runs offline; optional live mode may refresh
   evidence but must not overwrite fixtures automatically.

## Commands

```bash
bash scripts/run-golden-acceptance.sh
uv run pytest -q tests/test_golden_packets.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
