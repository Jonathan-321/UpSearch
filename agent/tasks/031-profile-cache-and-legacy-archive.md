# Task 031: Profile Cache And Legacy Archive

## Goal

Two bounded fixes. First, `agents/profile.py run()` makes an LLM call (~12s)
on every packet run even though the profile text rarely changes: cache the
parsed extraction on disk keyed by the sha256 of the raw profile text, so a
repeat run skips only the `llm.complete` call while deterministic
source-evidence merging still runs. Second, the CRM carries pre-fix discovery
junk — 24 packets stuck at `crm_status='identity_blocked'` plus
rejected/discovered companies that never produced a packet. Extend the
024/027 maintenance surface with a reviewable, idempotent archive pass that
flips those statuses to `'archived'` (never deletes) and hides archived rows
from the CRM list. The operator reviews the read-only report first and runs
the archive via the endpoint; agents never run it against the live database.

## Read

- `agents/profile.py` (`run`, `_merge_source_evidence`, `fallback_profile`)
- `upsearch/profile_source_fetch.py` (only `CACHE_PATH`, `load_cached_report`)
- `db.py` (`list_companies`, `upsert_packet`, `people_hygiene_report`,
  `run_people_hygiene` — the 024 maintenance pattern)
- `server.py` (`/os/companies`, `/os/maintenance/people-hygiene`)
- `frontend/src/components/CRMTable.tsx` (status badge fallback)
- `tests/test_people_hygiene.py` (tmp-path `db.DB_PATH` fixture pattern)

## Write Scope

- `agents/profile.py`
- `db.py`
- `server.py`
- `tests/test_profile_cache.py`
- `tests/test_legacy_archive.py`
- `.upsearch/agent-runs/031-profile-cache-and-legacy-archive-handoff.md`

## Required Behavior

1. `agents/profile.py` caches the parsed LLM extraction at
   `.upsearch/profile/structured-cache.json` as `{"hash": ..., "profile": ...}`
   keyed by sha256 of the raw profile text. On `run()`: a hash match returns
   the cached extraction passed through `_merge_source_evidence` (the merge is
   deterministic and re-reads the source-fetch cache, so fresh source evidence
   still lands without a model call). A miss calls the model and overwrites
   the cache. A missing, corrupt, or wrong-shape cache is a miss, never an
   error. The `fallback_profile` path (LLM failure or unparseable output) is
   never cached, so a degraded result cannot mask later recovery.
2. `UPSEARCH_PROFILE_CACHE=0` disables the cache; `=1` force-enables; unset
   means enabled except under pytest, where it stays off so tests that stub
   `llm.complete` can never read or overwrite the operator's real cache.
3. `db.legacy_archive_report()` is read-only: counts plus ids and names of
   packets with `crm_status='identity_blocked'` and companies with
   `identity_status` in ('rejected', 'discovered') that have zero packets and
   zero pending (draft/approved) messages. Manually added companies
   (`identity_status='unverified'`) are never swept.
4. `db.run_legacy_archive()` runs in one transaction and is idempotent: sets
   those packets `crm_status='archived'` and those companies
   `status='archived'`. Nothing is deleted; a second run changes nothing and
   returns `{packets_archived: 0, companies_archived: 0}`.
5. `db.list_companies()` hides archived rows by default — companies whose own
   status is `'archived'` or whose packet is `'archived'` — so `/os/companies`
   and the CRM list never render them (the frontend badge map would fall back
   to a misleading "Sourced" label). `include_archived=True` or an explicit
   `status='archived'` filter still returns them for operator inspection.
6. `GET /os/maintenance/legacy-archive` returns the report without mutating;
   `POST /os/maintenance/legacy-archive` runs the archive and returns the
   summary. The agent never runs the archive against `opportunity_os.db`.

## Commands

```bash
uv run pytest -q tests/test_profile_cache.py tests/test_legacy_archive.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
