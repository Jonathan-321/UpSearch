# Task 003: Trace Integrity

## Goal

Make Packet Checkup distinguish a missing historical trace from a current run
that started tracing but skipped or failed agent stages.

## Read First

- `upsearch/packet_checkup.py`
- `upsearch/harnessed_orchestrator.py`
- `frontend/src/components/HarnessCheckup.tsx`
- `tests/test_packet_checkup_people.py`

## Write Scope

- `upsearch/packet_checkup.py`
- `tests/test_packet_checkup_trace.py` (new)
- `frontend/src/components/HarnessCheckup.tsx` only if the API already exposes
  the new state and the UI cannot render it.

## Required Behavior

1. Emit `trace_status=unavailable` when a packet contains no trace metadata.
2. Do not assign `agent_coordination_failure` solely because historical trace
   data is absent.
3. Emit `trace_status=incomplete` when tracing exists but expected stages or
   handoffs are missing.
4. Preserve `agent_coordination_failure` for genuinely incomplete or errored
   traced runs.

## Commands

```bash
uv run pytest -q tests/test_packet_checkup_trace.py tests/test_packet_checkup_people.py
uv run pytest -q
cd frontend && npm run build
git diff --check
```
