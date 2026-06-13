# Verification Contract

Run the task's focused commands first. Then run:

```bash
uv run pytest -q
uv run python -m compileall -q agents upsearch db.py orchestrator.py run_scheduler.py server.py
git diff --check
```

Run the frontend build only when frontend files changed:

```bash
cd frontend && npm run build
```

## Evidence Required In The Handoff

- files changed;
- behavior before and after;
- commands run with exact pass/fail counts;
- assumptions introduced;
- unresolved risks;
- whether a human decision is blocked.

Do not call work complete because code was written. Completion requires the
acceptance criteria and verification evidence.
