# Task 027: Storage Correctness And Honesty

## Goal

A release audit found the storage layer lying in four small ways: `db.py`
hardcoded its database path and ignored `UPSEARCH_DB_PATH`, so the release
acceptance script's "empty temporary state" steps silently ran against the
real repository database; people rows persisted `verification_status` but
dropped the `verification_reason` the verifier produced; the same human could
be stored twice for one company (e.g. "Erik Bernhardsson" twice for Modal);
and `scripts/run-release-acceptance.sh` printed a hardcoded PASS report no
matter what actually ran. Fix all four without breaking the existing
test-suite patterns or touching the live database.

## Read

- `upsearch/runtime.py` (`resolve_db_path`, `DEFAULT_DB_PATH`; confirm it
  never imports `db` at module scope)
- `db.py` (`init_db` guarded-migration pattern, `insert_person`,
  `people_hygiene_report`, `run_people_hygiene` from task 024)
- `upsearch/orchestrator_service.py` (the single `db.insert_person` call)
- `tests/test_people_hygiene.py` (tmp-path `db.DB_PATH` fixture pattern)
- `tests/test_runtime_recovery.py` (chdir-based tests that rely on the
  CWD-relative default path)

## Write Scope

- `db.py`
- `scripts/run-release-acceptance.sh`
- `upsearch/orchestrator_service.py` (only the `verification_reason` kwarg on
  the `db.insert_person` call)
- `tests/test_people_hygiene.py` (extend)
- `tests/test_db_path.py` (new)
- `agent/tasks/027-storage-correctness.md`
- `.upsearch/agent-runs/027-storage-correctness-handoff.md`

## Required Behavior

1. `db.DB_PATH` derives from `upsearch.runtime` at import: when
   `UPSEARCH_DB_PATH` is set, `resolve_db_path()` wins; without the override
   the path stays the relative `DEFAULT_DB_PATH` so it keeps resolving
   against the current working directory per connection (several tests chdir
   to a tmp dir before `init_db()`, and freezing the CWD at import would
   redirect their writes into the real database). Tests that monkeypatch
   `db.DB_PATH` directly keep working unchanged. No import cycle:
   `upsearch.runtime` imports `db` only inside function bodies.
2. The people schema gains an additive `verification_reason TEXT DEFAULT ''`
   column using the same guarded `PRAGMA table_info` + `ALTER TABLE` pattern
   `init_db` already uses. `insert_person` stores it; the orchestrator passes
   it through from the person dict. People endpoints `SELECT *`, so the field
   reaches the UI tooltip without frontend changes.
3. The hygiene pass also collapses duplicate people by
   `(company_id, lower(name))` among rows passing the name gate, keeping the
   best row (verified beats unverified, then highest `relevance_score`, then
   lowest id). Messages addressed to a removed duplicate are repointed at the
   kept row so no message references a deleted person; message flagging
   judges the post-dedupe recipient; the duplicate's evidence sources move to
   the kept row unless an identical url+claim row already exists. Report and
   run dicts gain `duplicates_removed`; `people_kept` counts surviving rows.
   Same-name people at different companies are never deduped. Idempotent.
4. `scripts/run-release-acceptance.sh` records a measured PASS/FAIL per
   executed step, runs every step even after a failure, prints only measured
   statuses (the first step asserts `db.DB_PATH` equals the exported
   `UPSEARCH_DB_PATH`), and exits nonzero when any step failed. Manual checks
   remain listed as manual, not as PASS lines.

## Commands

```bash
uv run pytest -q tests/test_people_hygiene.py tests/test_db_path.py
uv run pytest -q
bash scripts/run-release-acceptance.sh
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
