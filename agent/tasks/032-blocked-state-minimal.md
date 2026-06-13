# Task 032: One Status Card For Identity-Blocked Packets

## Goal

An identity-blocked packet shouted one root cause six ways: a page-level
"Review required" banner under the profile section, a red stage-stepper row,
a "REVIEW REQUIRED: EMPTY PROBLEM SET" box with irrelevant advice, two dashed
empty-state boxes with their own advice, and "Checkup 0.2/10" / "QA 0/10"
chips for stages that never ran. Collapse the blocked state into one status
card with the precise identity reason, the closest-candidate typo hint when
present, and the existing rebuild action. Non-blocked packets render exactly
as before.

## Read

- `frontend/src/hooks/useOS.ts` (`OSCompany.identity_reason`, `OSPacket.crm_status`, `OSCheckup.failure_category`, `buildPacket`)
- `frontend/src/components/PacketView.tsx` (header chips, reliability warning, empty states, QA flag echo)
- `frontend/src/components/PacketStudio.tsx` (`studio-error` banner, canvas-bar chips, `buildPacket` wiring)
- `frontend/src/index.css` (packet band/badge idioms only)
- Live payloads, read-only: `GET /os/packet/{company}` for a `crm_status="identity_blocked"` row

## Write Scope

- `frontend/src/components/PacketView.tsx`
- `frontend/src/components/PacketStudio.tsx` (gating and prop wiring only)
- `frontend/src/index.css` (identity card classes in existing idiom)
- `.upsearch/agent-runs/032-blocked-state-minimal-handoff.md`

No backend changes. The blocked signals already exist: packets carry
`crm_status="identity_blocked"`, checkups report
`failure_category="identity_blocked"` with a precise `suggested_fix`, and
companies carry `identity_status`/`identity_reason` that may end with
`"Closest fetched candidate: <domain>."`.

## Required Behavior

1. A packet is blocked when `packet.crm_status === "identity_blocked"` or
   `checkup.failure_category === "identity_blocked"`. Gate every change on
   that state; non-blocked packets must render byte-identically.
2. When blocked, ONE status card under the packet header owns the page:
   title "Identity blocked", the company `identity_reason` verbatim, and —
   when the reason ends with "Closest fetched candidate: X." — a prominent
   "Did you mean X?" line. One primary action reuses the existing
   `buildPacket(company, lane)` rebuild flow; do not invent endpoints.
3. When blocked, suppress the symptom noise: the reliability-warning box,
   both dashed empty-state boxes (replaced by one muted line "Later stages
   were skipped until identity verifies."), the QA-flags section that echoes
   the same identity reason, and the header Checkup/QA score chips. The
   canvas-bar chips render an em-dash instead of fake scores.
4. The page-level red "Review required:" banner renders under the profile
   panel and implies a profile problem; when the loaded packet is blocked,
   the status card covers it, so suppress that banner. All other errors
   (connection loss, non-identity blocks) keep the banner unchanged.
5. Styling uses the existing index.css idioms; TypeScript compiles.

## Commands

```bash
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
