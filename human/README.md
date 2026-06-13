# Human Layer

This folder holds the judgment that should not be silently optimized away by
an implementation agent.

## Product Thesis

Given limited user input, UpSearch should help an early-career technical person
start a credible company-specific conversation by producing:

1. a verified company target;
2. a source-backed technical problem;
3. relevant, verifiable people;
4. a concrete technical artifact;
5. honest adjacent-proof mapping;
6. concise outreach;
7. an exact approval gate.

The canonical product charter is
`docs/opportunity-intelligence/upsearch-first-use-case-charter.md`.

## Human Decisions

The human retains control over:

- which lane and companies matter;
- whether an uncertain source is acceptable;
- claims about personal experience;
- the final technical angle;
- the target person and channel;
- every send, schedule, connection, share, or public action.

Implementation agents may recommend defaults. They may not cross these gates.

## Current Priority

Reach the V2 trustworthy state for AI infrastructure and inference:

- company identity is verified;
- problem claims trace to retrieved evidence;
- people have fetched evidence;
- weak runs are blocked rather than polished;
- the scheduler can continue rediscovery for a requested duration;
- the reviewer can understand the trace and exact approval.
