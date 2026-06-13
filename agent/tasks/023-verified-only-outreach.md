# Task 023: Verified-Only Outreach Targets

## Goal

Live runs queued outreach drafts addressed to people the system itself could
not verify ("Unverified recipient: Liang Xiong (status=unverified)" flags in
the decision inbox). Cause: `upsearch/orchestrator_service.py` picked
`top_person` as the first inserted person regardless of
`verification_status`, then drafted outreach and inserted messages for them.
The person-name gate (task 022) cleans the candidate pool; this task makes
the orchestrator refuse to target anyone who is not verified.

## Read

- `upsearch/orchestrator_service.py` (top_person selection, outreach stage,
  packet persistence)
- `upsearch/packet_checkup.py` (only `evaluate_packet` people scoring and
  `weak_person_mapping`)
- `tests/test_orchestrator_service.py`

## Write Scope

- `upsearch/orchestrator_service.py`
- `tests/test_outreach_gating.py` (new)
- `.upsearch/agent-runs/023-verified-only-outreach-handoff.md`

## Required Behavior

1. `top_person` is chosen only from people with
   `verification_status == "verified"`, ranked by `relevance_score`.
   Unverified people stay in the packet's `people_map` for research context
   but are never outreach targets.
2. With zero verified people the outreach-drafting model call is skipped
   entirely; the outreach stage completes with 0 drafts plus the log line
   "No verified person; outreach skipped pending review"; the packet
   persists with empty drafts and `crm_status` `needs_review`; no messages
   are inserted. The run does not crash and reaches QA and the final
   checkup normally (checkup categorizes `weak_person_mapping`).
3. `db.insert_message` is never called for a person whose
   `verification_status` is not `"verified"` (asserted via test spy).
4. Tests cover: a verified person selected over a higher-scoring unverified
   one, and the zero-verified-people skip path, using fake agents and a
   temporary database.

## Commands

```bash
uv run pytest -q tests/test_outreach_gating.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
