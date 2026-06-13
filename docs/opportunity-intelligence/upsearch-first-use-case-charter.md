# UpSearch First Use Case Charter

Last updated: 2026-06-03

## Purpose

UpSearch is the first concrete use case for testing whether an agent system can produce useful progress without turning into a generic automation toy.

The broader ambition is persistent project loops: a user defines a goal, constraints, approval boundaries, and definition of done, then agents continue making progress while the user monitors and resolves only meaningful blockers.

UpSearch should not start by trying to solve every project domain. It should prove the loop in one domain where the stakes, ambiguity, and evidence requirements are real:

```text
Help an early-career technical person move from broad interest to a high-quality, company-specific technical conversation.
```

## The Human Problem

Early-career technical people often know the broad area they care about, but they do not know how to turn that interest into credible conversations with the right people.

The usual paths are weak:

1. Cold applying feels high-volume and low-signal.
2. Generic LinkedIn outreach sounds interchangeable.
3. Job boards describe roles but not the technical problems behind them.
4. The user may have adjacent proof, but not the exact experience requested.
5. It is hard to know who to contact, what to say, or what artifact would make the outreach credible.

The important insight is that the user does not only need "jobs." The user needs a path into a technical conversation where they can show taste, curiosity, and execution potential.

## Product Thesis

Given limited user input, UpSearch should build a company-specific opportunity packet that answers:

1. Why this company?
2. What real problem should the user discuss?
3. Who is close enough to that problem to contact?
4. What can the user credibly say or show?
5. What adjacent experience maps to the problem?
6. What outreach should be sent, and through which channel?
7. What evidence supports every claim?
8. What external action is waiting for human approval?

The product should optimize for high-quality technical conversations started, not number of messages sent.

## First Domain Boundary

The first lane is:

```text
AI infrastructure and inference systems
```

This lane is a good proving ground because:

1. We already validated the manual loop with Baseten.
2. Companies publish enough public technical signal through blogs, docs, jobs, papers, GitHub, HN, and LinkedIn.
3. The user can create concrete artifacts without needing insider access.
4. The problem space has real technical depth: model serving, inference latency, GPU scheduling, evals, routing, reliability, cost, and observability.
5. The same workflow can later transfer to other technical lanes.

Phase 1 companies should stay narrow:

1. Baseten.
2. Modal.
3. Fireworks AI.
4. Together AI.
5. A small number of comparable AI infrastructure companies only after the first four packets are reliable.

## What "Done" Means For UpSearch

UpSearch is not done when the UI looks good or when agents can generate text.

UpSearch is done for the first use case when a user can provide a rough profile and target lane, then receive a trustworthy packet that could reasonably be used for real outreach.

Minimum done state:

1. The system ingests the user profile and public proof sources.
2. The system identifies a target company in the selected lane.
3. The system extracts source-backed technical problems.
4. The system identifies relevant people and explains why each person matters.
5. The system maps the user's adjacent proof to the selected problem without fabricating experience.
6. The system writes a one-page technical note or artifact brief.
7. The system drafts outreach under the channel constraints.
8. The system verifies sources, claims, word count, tone, and approval safety.
9. The system shows a trace of what ran, what failed, and what evidence was used.
10. The system blocks external action until the human approves the exact target, channel, body, attachment, and timing.
11. The system records the outcome and next follow-up state.

The first stable demo should complete this loop for Baseten and at least one second company.

## What Success Looks Like

The right success metrics are not message volume or number of companies scraped.

Better metrics:

1. The packet contains real source-backed problems, not generic company summaries.
2. The people map includes verifiable people close to the selected problem.
3. The technical note is specific enough that an engineer could critique it.
4. The outreach sounds human, concise, and technically grounded.
5. The QA layer catches unsupported claims and weak sourcing.
6. The user can understand why the system recommended the action.
7. The approval gate makes the user confident, not confused.
8. A user could start a real technical conversation from the packet.

Longer-term success:

1. Connection acceptance.
2. Replies.
3. Technical conversations.
4. Referrals.
5. Interviews.
6. Better company targeting over time.

## What UpSearch Should Not Become

UpSearch should not become:

1. A job board clone.
2. A bulk application tool.
3. A LinkedIn spam machine.
4. A resume keyword matcher.
5. A generic AI writing assistant.
6. A dashboard full of unverifiable agent activity.
7. A system that sends or schedules without exact approval.

The core product is opportunity intelligence and credible action preparation, not automation volume.

## Core User Journey

The intended user flow:

1. User provides a rough profile, GitHub, website, resume, LinkedIn, target lane, and constraints.
2. UpSearch builds a proof bank and flags missing or unverifiable claims.
3. UpSearch recommends a small company set.
4. User selects or accepts a company.
5. UpSearch extracts open problems from public sources.
6. UpSearch ranks people by relevance to the problem.
7. UpSearch writes a technical note and maps adjacent proof.
8. UpSearch drafts email and LinkedIn outreach.
9. QA verifies the packet.
10. User reviews the exact action.
11. UpSearch opens the right platform or creates a draft, but only within the approved boundary.
12. UpSearch logs status and follow-up timing.

The user should not have to choose every micro-step. The system should recommend defaults and reserve user attention for high-risk decisions.

## Biggest Constraints

### Source Grounding

The system must know why it believes something. Every company problem, person recommendation, and technical note claim should have a citation or an explicit uncertainty label.

Weak source grounding is the fastest way to lose user trust.

### Profile Truth

The system must distinguish:

1. Verified project evidence.
2. Coursework.
3. Interest.
4. Research reading.
5. Speculative ideas.
6. Claims that should not be made.

This is especially important for early-career users. The system should help them sound credible without pretending they have experience they do not have.

### People Verification

People sourcing is fragile. The system must avoid mixing up people with the same name or recommending people whose relevance is unclear.

Every person should have a reason and a source.

### Technical Quality

The one-pager cannot be filler. It needs to show:

1. The problem.
2. Why it matters.
3. Why it is hard.
4. Current landscape.
5. A plausible contribution.
6. Evaluation criteria.
7. Adjacent proof.

The note should invite critique from a technical person.

### Approval Safety

External actions require exact approval:

1. Email send.
2. Email scheduling.
3. LinkedIn connection request.
4. LinkedIn message.
5. X/Twitter message.
6. Google Doc creation or sharing when public/cloud state changes.
7. Attachments.

The system can prepare and open the path, but the human remains responsible for final action approval.

### Cost And Model Routing

Broad source reading can be cheap. Final synthesis and QA may need stronger reasoning.

The system should not depend on one expensive model doing everything.

### Connector Reliability

Browser automation, APIs, OAuth scopes, and logged-in sessions fail. UpSearch should preserve the packet and approval record even when a connector fails.

Manual handoff is acceptable if it is clean, logged, and easy.

## Resources Not Fully Tapped Yet

The current project has not fully explored:

1. GitHub profile extraction beyond shallow repository summaries.
2. Resume parsing and project evidence extraction.
3. LinkedIn ingestion with user authorization.
4. Company author pages and engineering blogs as first-class sources.
5. Hacker News discussion mining by company/problem.
6. Reddit discussion mining by problem lane.
7. Paper and arXiv retrieval for technical landscape grounding.
8. Job descriptions as problem evidence.
9. Sponsorship and visa evidence sources.
10. Alumni, school, and conference network signals.
11. Outcome tracking by message type and problem framing.
12. W&B as a real run ledger rather than a planned integration.
13. Hermes as a daily status surface reading from actual run state.

These are not all Phase 1 requirements. They are future leverage points.

## First Use Case Evaluation

The Baseten packet should be judged against this checklist:

1. Are the open problems specific and source-backed?
2. Are the sources current and relevant?
3. Are the people actually connected to the problem?
4. Does the technical note contain a buildable contribution?
5. Does the proof mapping avoid exaggerated experience?
6. Are the outreach drafts under channel limits?
7. Does QA catch tone, sourcing, and claim issues?
8. Does the UI show why the packet exists?
9. Does the action gate make the exact next action obvious?
10. Is the run trace useful enough to debug failure?

If the answer is no, the solution is not "add more agents." The solution is to tighten the harness, state, validators, or evidence flow.

## Relationship To Persistent Loops

The persistent loop idea should come after UpSearch proves the single-domain loop.

UpSearch gives us the testbed for:

1. Goal definition.
2. Structured state.
3. Agent task decomposition.
4. Source retrieval.
5. Artifact generation.
6. Verification.
7. Approval gates.
8. Action logging.
9. Follow-up scheduling.
10. Progress monitoring.

Once this works for opportunity packets, the same loop can generalize to other domains.

The generalized loop should not be designed in the abstract first. It should be extracted from a working UpSearch loop.

## Current Highest-Value Questions

Before building more, the project should answer:

1. Can UpSearch reliably produce one source-grounded packet for Baseten without manual rescue?
2. Can it produce a second packet for Modal or Fireworks with the same quality?
3. Does the checkup view expose real weaknesses instead of only showing success?
4. Can a new user edit their profile and understand what the system needs next?
5. Can the system explain how open problems and people were found?
6. Can the action handoff be simple without becoming unsafe?
7. Can we measure cost, model route, and output quality per agent run?
8. Can Hermes summarize actual run state instead of regenerating vague updates?

These questions matter more than adding more companies, more agents, or more UI sections.

## Phase 1 Definition Of Done

Phase 1 is done when:

1. A new user can enter a profile with GitHub or website links.
2. Profile Source Fetch extracts public proof and flags missing private sources.
3. The user can choose AI infrastructure / inference as a lane.
4. The system builds packets for Baseten and one second company.
5. Each packet includes company fit, source-backed problems, people map, one-page note, outreach drafts, QA, and approval record.
6. Harness Checkup shows profile, source, problem, people, note, outreach, action, and trace health.
7. The action queue opens the right platform or draft path without sending automatically.
8. The run ledger records model route, cost estimate, sources, artifacts, QA status, and approval status.
9. The UI is coherent enough that a user understands what happened and what needs their decision.
10. The product can be demoed as a trustworthy opportunity intelligence loop, not a static agent demo.

## Strategic Principle

UpSearch should make the user more prepared, not merely more automated.

The user should leave the system with better understanding of the company, the problem, the people, and their own credible angle.

That is the standard for deciding what to build next.
