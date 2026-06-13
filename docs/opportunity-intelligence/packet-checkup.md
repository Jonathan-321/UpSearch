# Packet Checkup

Packet Checkup is the reliability layer for UpSearch. It borrows the useful part of Swarm Checkup: every run should leave evidence of what happened, where the packet is strong, and what needs repair before any external action.

## What It Checks

- Source grounding: whether open problems carry source URLs.
- Problem specificity: whether the problem is concrete enough to build around.
- People mapping: whether contacts have profile evidence and relevance to the problem.
- Technical note quality: whether the note is substantial enough to show understanding.
- Outreach safety: whether drafts exist and stay under the 200-word rule.
- Agent coordination: whether the run recorded agent steps and handoffs.
- QA: whether the final packet passed claim, source, tone, and approval checks.

## How Open Problems Are Found

The Problem Agent starts from the company brief, lane, tech stack, and user profile. It searches public discussion sources, currently Hacker News and Reddit, for company engineering signals. The model receives the retrieved snippets and must return JSON problems with source URLs, a source signal, relevance score, and a contribution surface.

If the model returns malformed JSON or no problems, the agent creates a conservative fallback problem and marks it as uncertain. This prevents a broken model response from erasing the packet, but QA and Packet Checkup can still flag the result as needing review.

## How People Are Found

The People Agent uses the selected problem as the search lens. It searches public people signals, currently Hacker News authors and known public discussion surfaces, then ranks people by proximity to the problem, role relevance, public signal, and usefulness of conversation.

The agent is not allowed to fabricate profile URLs. If a LinkedIn, GitHub, or X profile is not available, the person should be treated as needing verification. QA and Packet Checkup both surface weak people mapping before outreach.

## Why This Matters

The point is not to send more messages. The point is to make each opportunity packet auditable:

```text
company -> problem -> people -> technical note -> outreach -> QA -> approval
```

If the packet is weak, the system should say why. If it is strong, the user should see the trace and know what is safe to approve.
