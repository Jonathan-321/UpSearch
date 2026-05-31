# UpSearch Pitch Notes

Target length: 3 minutes.

## Slide 1 - Hook (0:00-0:25)

Students often send generic cold messages because they do not know where to
start. UpSearch changes the order: first find a real technical signal, then
build a credible reason to reach out.

## Slide 2 - Utility (0:25-0:55)

The workflow is research, match, draft, approve. It helps a student move from a
broad interest such as ML inference to one specific and reviewable outreach
message. It is designed for targeted conversations, not mass outreach.

## Slide 3 - Agent Orchestration (0:55-1:30)

There are two paths. Quick Search is the fast workflow for public signals.
Opportunity OS is the deeper workflow for a company packet. Each agent has a
focused responsibility and passes structured output forward. Personal data
comes from profile.txt. LinkedIn profiles are not fetched automatically.

## Slide 4 - Live Product (1:30-2:00)

Show the actual app. Quick Search is useful when I want one credible lead.
Opportunity OS is useful when I want a deeper company dossier, CRM record, and
human approval queue. This is the point to switch briefly to the live demo if
time allows.

## Slide 5 - Technical Execution (2:00-2:30)

The frontend is React. FastAPI serves both workflows. Opportunity OS streams
stage updates through SSE. SQLite stores packet and approval records locally.
The system keeps a human in control and QA checks the generated outreach before
approval.

## Slide 6 - Sponsor Usage and Close (2:30-3:00)

W&B is meaningful because every logged Quick Search run becomes an experiment:
lead quality, word count, sent status, supervisor scores, and the draft artifact
are tracked together. The goal is not merely to generate messages. The goal is
to learn which credible outreach actually gets replies.

Close with:

> UpSearch turns cold outreach into a research workflow: better evidence,
> better messages, and a human decision at the final step.
