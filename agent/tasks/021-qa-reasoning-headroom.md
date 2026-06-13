# Task 021: QA Reasoning Headroom And Draft Dash Normalization

## Goal

Run 5 completed every stage but QA scored 3/10 on two flags: "QA parse
error" (deepseek-r1 spent its 512-token budget on reasoning and returned
empty/truncated JSON, so the fail-closed default fired instead of a real
verdict) and "Drafts contain em-dash or en-dash" (the model ignores the
prompt rule). Give the verification call reasoning headroom and normalize
dashes deterministically.

## Read

- `agents/qa.py`, only the `qa_verify` call
- `agents/outreach.py`
- `upsearch/qa_execution.py` (context only)

## Write Scope

- `agents/qa.py`
- `agents/outreach.py`
- `tests/test_outreach_drafts.py`
- `tests/test_qa_model_routing.py` (one additive test)
- `.upsearch/agent-runs/021-qa-reasoning-headroom-handoff.md`

## Required Behavior

1. The QA verification call passes `max_tokens >= 2048` so reasoning models
   can think and still emit the JSON verdict. Fail-closed parse semantics
   unchanged.
2. Outreach drafts are normalized deterministically: em/en-dashes replaced,
   whitespace collapsed per line. The deterministic `has_dashes` rule check
   in QA stays as the independent verifier.

## Commands

```bash
uv run pytest -q tests/test_outreach_drafts.py tests/test_qa_model_routing.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
