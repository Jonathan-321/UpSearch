# Task 019: Surface Config Problems And QA Degraded Mode In The UI

## Goal

The backend knows when model config is broken and when QA ran degraded, but
the UI showed neither: `GET /api/config/model-status` had zero frontend
consumers and `server.py` stripped `model_route` from QA payloads. Make the
UI honestly reflect system state.

## Read

- `server.py`, only `packet_qa` and config endpoints
- `agents/qa.py`, only the emitted `model_route` shape
- `frontend/src/hooks/useOS.ts`
- `frontend/src/components/PacketView.tsx`, `PacketStudio.tsx`, `App.tsx`

## Write Scope

- `upsearch/api_schemas.py`
- `server.py` (`packet_qa` passthrough only)
- `frontend/src/hooks/useOS.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/PacketView.tsx`
- `frontend/src/components/PacketStudio.tsx`
- `tests/test_api_contract.py`
- `.upsearch/agent-runs/019-ui-config-and-qa-honesty-handoff.md`

## Required Behavior

1. A dismissible banner on app load lists `problems[]` from
   `/api/config/model-status` whenever `ok` is false.
2. QA payloads carry `model_route` (provider, model, configured, is_fallback,
   degraded_mode, reason) additively through `PacketDetailOut.qa` and
   `RunStateOut.qa`; legacy packets yield `model_route = null`.
3. The packet view badges degraded QA: "QA degraded — not strong-model
   verified" next to the score.
4. `OSCompany` types reflect reality (`hiring_status: string | null`,
   identity fields present).
5. Frontend build and backend tests pass.

## Commands

```bash
uv run pytest -q tests/test_api_contract.py
uv run pytest -q
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
