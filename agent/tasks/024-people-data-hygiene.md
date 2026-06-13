# Task 024: People Data Hygiene

## Goal

Task 022 added the deterministic name gate (`upsearch/person_validation.py`),
so new junk "people" (nav labels like "Pricing", "Use Cases", group labels
like "Fireworks GitHub Contributors", blog titles) can no longer enter the
pipeline. The live database still holds the junk admitted before the gate:
non-person people rows with scores and source links, and pending outreach
messages addressed to them or to unverified recipients. Add a reviewable,
idempotent maintenance pass that purges the stored junk. The operator reviews
the read-only report first and runs the purge via the endpoint; agents never
run it against the live database.

## Read

- `upsearch/person_validation.py` (only `person_name_rejection`)
- `db.py` (messages schema, `reject_message`, `get_review_messages`,
  `upsert_packet` people_map handling)
- `tests/test_delivery_followup.py` (tmp-path `db.DB_PATH` fixture pattern)

## Write Scope

- `db.py`
- `server.py`
- `tests/test_people_hygiene.py`
- `.upsearch/agent-runs/024-people-data-hygiene-handoff.md`

## Required Behavior

1. `db.people_hygiene_report()` is read-only: counts of people rows failing
   `person_name_rejection`, live messages (status draft/approved) addressed
   to them, to missing person rows, or to recipients whose
   `verification_status != 'verified'`, plus the failing rows and reasons so
   the operator can review before purging.
2. `db.run_people_hygiene()` runs in one transaction and is idempotent:
   deletes failing people rows and their person-evidence `sources` rows;
   rejects the flagged messages the same way `reject_message` does
   (status='rejected' plus an approvals note
   `recipient failed person validation: <reason>`); rewrites each packet's
   `people_map` to drop entries failing the same gate. Returns
   `{people_removed, messages_rejected, packets_updated, people_kept}`.
3. Already-rejected messages, drafts with no recipient, and messages to
   verified real people stay untouched. A second run changes nothing.
4. `GET /os/maintenance/people-hygiene` returns the report without mutating;
   `POST /os/maintenance/people-hygiene` runs the purge and returns the
   summary. The agent never runs the purge against `opportunity_os.db`.

## Commands

```bash
uv run pytest -q tests/test_people_hygiene.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
