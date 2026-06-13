# Task 025: Production-Honest People Map, Evidence Links, And Decision Inbox

## Goal

The UI made junk look researched: unverified people carried "5/10" relevance
badges, every person card showed a generic underlined "Public source" link,
evidence chips showed bare domains with no path, and the decision inbox put
72 mostly needs-review drafts to unverified recipients in front of the
operator. Cut the visual junk and make verification state visible.

## Read

- `frontend/src/hooks/useOS.ts` (`OSPerson`, `OSMessage`)
- `frontend/src/components/PacketView.tsx` (people map, problem evidence)
- `frontend/src/components/ApprovalQueue.tsx` (decision inbox)
- `frontend/src/components/HarnessCheckup.tsx` (people verification audit row)
- `frontend/src/index.css` (existing chip/badge/link idioms only)
- Live payloads, read-only: `GET /os/packet/{name}`, `GET /os/messages/review`

## Write Scope

- `frontend/src/types.ts` (shared `evidenceLabel` helper)
- `frontend/src/hooks/useOS.ts`
- `frontend/src/components/PacketView.tsx`
- `frontend/src/components/ApprovalQueue.tsx`
- `frontend/src/components/HarnessCheckup.tsx`
- `.upsearch/agent-runs/025-ui-people-honesty-handoff.md`

No backend changes. A missing API field is a handoff note, not an edit.

## Required Behavior

1. People cards: only `verification_status == "verified"` people show the
   relevance score badge; unverified people show a muted "unverified" chip
   instead, with `verification_reason` (when present) as the title attribute.
   Verified people sort above unverified, relevance order within each group.
2. Evidence links render as anchors whose text is host plus truncated
   path/query (e.g. `baseten.co/author/bola-malek`), href = full URL,
   `target="_blank" rel="noopener noreferrer"`. No "Public source" text, no
   bare-domain chips, no "Evidence N" labels. No source URL means no link
   text at all.
3. Decision inbox defaults to actionable messages addressed to verified
   recipients (`actionable !== false` and no "Unverified recipient" QA flag).
   A "Show needs-review (N)" toggle reveals the hidden rest. Approve/reject,
   delivery, and follow-up flows are untouched.
4. Types extended locally (`verification_status`, `verification_reason`)
   without inventing backend fields; absent fields stay optional.

## Commands

```bash
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
