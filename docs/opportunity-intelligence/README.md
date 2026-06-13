# Opportunity Intelligence OS

This directory captures the working materials behind the UpSearch pivot from a personal sourcing workflow into a multi-agent opportunity intelligence system.

## Product thesis

UpSearch should help technical people turn their background into precise company targeting, real problem understanding, credible technical artifacts, and human-approved outreach.

The core loop is:

```text
Profile -> Company -> Problem -> People -> Technical note -> Outreach -> QA -> Approval -> Send -> Track
```

The product should feel like a small research and outreach team. It should not feel like a bulk messaging tool.

## Current seed corpus

The initial seed material is preserved in:

```text
docs/opportunity-intelligence/oppprep-seed/
```

Important files:

| File | Purpose |
| --- | --- |
| `ai-opportunity-sourcing.md` | Company lanes, sponsorship sources, target tiers, and Hermes brief format. |
| `outreach-operating-system.md` | Manual workflow, approval gates, and execution rules. |
| `adjacent-proof-bank.md` | Mapping from user projects to credible proof angles. |
| `ai-infra-outreach-notebook.md` | Strategy notebook for Baseten, Modal, Fireworks, and Together AI. |
| `company-one-pagers.md` | Combined technical proposal pack. |
| `one-pagers/` | Final per-company one-pagers in Markdown and Docs-ready DOCX form. |
| `baseten-first-target-dossier.md` | First complete target dossier. |
| `baseten-first-send-packet.md` | First live outreach packet and tracking status. |
| `opportunity-intelligence-os-brief.gdocs.docx` | Teammate-ready brief for the product idea. |

## Baseline execution result

The first manual execution test was Baseten.

Outcome:

1. Sourced Baseten as a strong inference infrastructure target.
2. Wrote an adapter-aware routing one-pager.
3. Built a first-send packet for Bola Malek, Raymond Cano, and Joey Zwicker.
4. Sent the approved LinkedIn connection request to Bola Malek.
5. Verified the request as pending.

No other outreach should be assumed sent.

## Design direction

The next implementation step is not more one-off sourcing. It is to turn the manual loop into an orchestrated workflow with:

1. Structured state.
2. Model routing by task type and cost.
3. Source-grounded outputs.
4. W&B logging for every run.
5. Human approval gates before external actions.

Start with `upsearch-first-use-case-charter.md` for the problem framing, done criteria, constraints, and Phase 1 success definition.

See `multi-agent-orchestrator-plan.md` for the implementation plan.

For the concrete Phase 1 build path, agent/tool matrix, Hermes role, hosting path, and short presentation outline, see:

```text
docs/opportunity-intelligence/phase-1-build-plan.md
```

For the component-by-component audit and anti-breakage checklist, see:

```text
docs/opportunity-intelligence/component-audit.md
```

## Safety rules

1. Do not store API keys in docs, prompts, screenshots, commits, or source files.
2. Use environment variables or a secret manager for provider keys.
3. Any key that has been pasted into chat or notes should be rotated.
4. Sending email, LinkedIn messages, connection requests, or scheduled sends requires explicit approval.
