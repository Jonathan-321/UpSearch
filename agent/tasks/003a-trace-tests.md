# Task 003a: Trace Integrity Tests

## Goal

Write focused regression tests for the trace-state behavior already implemented
in `upsearch/packet_checkup.py`.

## Read

- `upsearch/packet_checkup.py`, only `TraceEvent`, `agent_step`,
  `handoff_event`, `_score_coordination`, and `evaluate_packet`
- `tests/test_packet_checkup_people.py`

## Write Scope

- `tests/test_packet_checkup_trace.py` only
- `.upsearch/agent-runs/003a-trace-tests-handoff.md`

Do not edit production code, the frontend, the task queue, or other tests.

## Required Tests

Create a reusable high-quality packet fixture and verify:

1. Omitted trace returns `trace_status=unavailable` and does not produce
   `agent_coordination_failure`.
2. Explicit empty trace returns `trace_status=incomplete` and does produce
   `agent_coordination_failure`.
3. Partial trace returns `trace_status=incomplete` and coordination failure.
4. All seven expected agent steps plus six handoffs returns
   `trace_status=complete` and no coordination failure.
5. A full trace containing an errored event remains incomplete and produces
   coordination failure.

## Commands

```bash
uv run pytest -q tests/test_packet_checkup_trace.py tests/test_packet_checkup_people.py
```

Stop after the focused tests pass. Write a concise handoff with changed files,
commands, results, and remaining concerns.
