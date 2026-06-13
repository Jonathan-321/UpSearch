# UpSearch Phase 1 Release Checklist

## Automated Gate

Run:

```bash
bash scripts/run-release-acceptance.sh
uv run pytest -q
cd frontend && npm run build
docker compose config
git diff --check
```

The release acceptance script uses an empty temporary state directory and
requires all of the following:

- database initialization with no pending migrations;
- Baseten and Modal golden packet acceptance;
- one fake-agent packet through the shared orchestrator service;
- one stable run ID across the result, run record, trace, progress events, and
  persisted QA metrics;
- external action blocked before exact approval;
- digest-bound prepared and sent delivery events after approval;
- a digest-bound follow-up;
- restart without duplicate packet, approval, trace, send, or follow-up rows.

## Manual Gate

- Configure a real model provider and run one reviewed packet.
- Confirm the selected person and problem sources in the review UI.
- Approve one exact draft, then open Gmail or LinkedIn.
- Confirm UpSearch records `opened` only when the platform is opened.
- Confirm the user must explicitly mark the message `sent`.
- Schedule and complete one follow-up.
- Edit an approved draft and confirm the old delivery state disappears until
  the new text is approved.
- Restart the API and confirm the run trace and review state remain visible.
- Exercise backup and restore on the intended deployment host.

## Release Boundaries

- UpSearch does not automatically send email or LinkedIn messages.
- Delivery state is user-reported until an authorized connector provides a
  verifiable receipt.
- Historical approvals without a message digest are stale by design.
- Real-model quality and authenticated browser handoffs remain manual release
  checks because automated acceptance uses no credentials or network access.
