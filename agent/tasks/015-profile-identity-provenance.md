# Task 015: Identity-Safe Profile Ingestion And Provenance

## Goal

Make profile ingestion identity-safe and every profile claim traceable to its
source. Fetched facts must never silently overwrite user-typed identity, facts
from discovered links must never outrank facts from user-provided seed links,
and the harness report must expose machine-readable provenance for each proof
point instead of only "Source: url" prose.

## Read

- `.upsearch/agent-runs/014-release-integration-acceptance-handoff.md`
- `upsearch/profile_harness.py`
- `upsearch/profile_source_fetch.py`
- `agents/profile.py`
- `tests/test_profile_agent_evidence.py`
- `tests/test_profile_source_graph.py`

## Write Scope

- `upsearch/profile_harness.py`
- `upsearch/profile_source_fetch.py`
- `agents/profile.py`
- `tests/test_profile_identity_provenance.py` (new)
- `tests/test_profile_source_graph.py` (only if pinned shapes gain fields)
- `.upsearch/agent-runs/015-profile-identity-provenance-handoff.md`

Do not change server endpoints, the frontend, or the orchestrator. New report
keys must be additive so existing consumers keep working.

## Required Behavior

1. Remove the hardcoded Coursicle CMSC curriculum fetch from
   `enrich_profile_text`. It injects course signal from a fixed school
   regardless of the user's actual school and performs a live network call
   inside the enrichment path.
2. Identity trust order is explicit: user-typed `Name:` / `Email:` / `School:`
   lines in the raw profile win over fetched source facts; fetched facts win
   over model extraction (existing pinned behavior); facts from seed sources
   win over facts from discovered (depth > 0) sources.
3. In `fetch_profile_sources`, fact merging must honor the documented
   resume > github > web priority. Today last-write-wins inverts it.
4. When a fetched fact conflicts with a user-typed identity value, keep the
   user value and surface the conflict in a visible `identity_warnings` list
   on the harness report. Never resolve a conflict silently.
5. Each source in the harness report carries an `origin` of `seed` or
   `discovered`. The source-fetch report records which source supplied each
   profile fact (`fact_provenance`).
6. The harness report exposes `proof_provenance`: one record per proof-bank
   entry with claim text, source url, source kind, origin, and fetched_at.
   Proof points with no fetched source are marked `origin: "user"`.
7. Tests require no network. Existing identity tests
   (`test_model_cannot_override_verified_identity`,
   `test_harness_uses_discovered_resume_and_inferred_identity`) keep passing.

## Commands

```bash
uv run pytest -q tests/test_profile_identity_provenance.py
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Write the handoff and stop after verification.
