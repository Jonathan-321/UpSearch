# Task 030: One Decision Card Per Person In The Approval Inbox

## Goal

Sent messages convert; the bottleneck is review friction. The decision inbox
rendered one row per outreach variant, so one person became three separate
decisions, QA flags repeated near-duplicate strings, rows had no readiness
order, and the reviewer reassembled "who is this, why them, is the info
trusted" from scattered fields. Collapse each (company, person) into one
decision card with channel tabs, deduped flags, and readiness ordering.

## Read

- `frontend/src/hooks/useOS.ts` (`OSMessage`, `OSPerson`, approve/reject flows)
- `frontend/src/components/ApprovalQueue.tsx` (decision inbox, verification inference)
- `frontend/src/components/PacketStudio.tsx` (mount point, packet payload in scope)
- `frontend/src/index.css` (decision/tab/badge idioms only)
- Live payloads, read-only: `GET /os/messages/pending`, `GET /os/messages/review`

## Write Scope

- `frontend/src/components/ApprovalQueue.tsx`
- `frontend/src/components/PacketStudio.tsx` (prop wiring only)
- `frontend/src/index.css` (new decision card classes in existing idiom)
- `.upsearch/agent-runs/030-approval-decision-cards-handoff.md`

No backend changes. A missing API field is a handoff note, not an edit.

## Required Behavior

1. Group messages client-side by `(company_name, person_name)` into one card
   per person. Rows without a `person_name` stay single-message cards;
   merging anonymous legacy rows would hide decisions. Card header: person
   name, role, company, verified/unverified recipient badge (reuse the
   existing QA-flag inference), and a one-line WHY built as
   `"<problem title> — <relevance reason or proximity>"` from the loaded
   packet's people (matched only when the card's company equals the loaded
   packet's company); otherwise fall back to the existing why-this-exists
   copy.
2. Channel tabs inside the card (email / LinkedIn note / follow-up, unknown
   variants after), defaulting to email, else linkedin_note, else
   connection_followup. The selected variant renders in the existing draft
   area. Approve and reject act ONLY on the selected variant through the
   existing endpoints; other variants stay pending. No batch-approve
   endpoint. Duplicate drafts on one channel stay reachable via draft chips.
3. QA flags dedupe per card with case-insensitive substring matching ("X"
   and "X (already flagged)" collapse to the shorter line). At most 3 show,
   with a "+N more" expander.
4. Cards order by readiness: actionable+verified first, then QA score desc,
   then packet checkup score when present. The task 025 needs-review toggle
   keeps working at card level and the default view stays ready-only.
5. All approve/reject/copy/delivery/follow-up flows and endpoints unchanged.
   A "reject all for this person" convenience calls the existing reject
   endpoint once per pending draft, sequentially.
6. Styling uses the existing index.css idioms; TypeScript compiles.

## Commands

```bash
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
