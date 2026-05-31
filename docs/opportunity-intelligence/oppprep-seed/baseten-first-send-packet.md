# Baseten first-send packet

Last updated: 2026-05-30

Status: first outreach sent. Bola Malek's LinkedIn connection request was sent with the approved note on 2026-05-30 and verified as Pending on LinkedIn.

## First-send recommendation

Start with LinkedIn connection requests, not email, because the strongest public contact URLs are LinkedIn profiles and Baseten author pages, not verified direct email addresses.

Send order:

1. Bola Malek
2. Raymond Cano
3. Joey Zwicker

Rationale: Bola is the closest match to the one-pager because she is both FDE and a co-author on Baseten's continual-learning inference post. Raymond is strong for the Loops and checkpoint-deploy angle. Joey is strong for FDE leadership and routing to the right team.

## One-pager to use

Attach or link only after approval:

`/Users/jonathanmuhire/Documents/Oppprep/one-pagers/baseten-one-pager.gdocs.docx`

Recommended first move: do not attach on the first connection request. Mention the one-pager only after the person accepts or if sending a full email.

## Target 1: Bola Malek

Role: Forward Deployed Engineer

Why this person: Bola co-authored Baseten's continual-learning inference post and also writes on Frontier Gateway. This makes her the strongest bridge between customer-facing AI infrastructure, routing, observability, and production inference.

Sources:

- Baseten author page: https://www.baseten.co/author/bola-malek/
- Continual-learning post: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Frontier Gateway post: https://www.baseten.co/blog/introducing-baseten-frontier-gateway/
- LinkedIn: https://www.linkedin.com/in/bolamalek/

Best channel: LinkedIn connection first. Email only if a verified address is available or you explicitly approve a guessed company-format email.

LinkedIn connection note:

```text
Hi Bola, I am a student studying inference systems for models that keep changing after deployment. Your Baseten post on continual learning made me write a short note on adapter-aware routing. Would love to connect and learn if I am framing the problem correctly.
```

Email subject:

```text
Question on adapter-aware routing for continual learning
```

Email body:

```text
Hi Bola,

I am a student exploring inference systems for models that keep changing after deployment. I read Baseten's Trajectory post and the part that stuck with me was the inversion from "new version replaces old version" to "new checkpoint is a hypothesis and old checkpoint is the control."

I wrote a one-page technical note on adapter-aware routing for continual-learning inference. The idea is a small serving loop where each request carries adapter/version metadata, traffic splits between control and candidate adapters, and validation records provenance plus quality and latency counters before promotion.

My closest adjacent project is PolyQuant, a supervised forecasting engine with revision history, calibration, and bounded agent coordination. It made me think about model updates as auditable hypotheses rather than silent replacements.

Would you be open to a quick 15 minute chat, or is there someone closer to Baseten's multi-LoRA or FDE work you would recommend I learn from?

Best,
Jonathan
```

Word count: 154

## Target 2: Raymond Cano

Role: Software Engineer

Why this person: Raymond authors Baseten's Loops and training posts. He is the best target for the training-to-inference part of the problem: how a checkpoint moves from training into production without turning deployment into an unsafe guess.

Sources:

- Baseten author page: https://www.baseten.co/author/raymond-cano/
- Baseten Loops SDK: https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/
- LinkedIn: https://www.linkedin.com/in/raymond-cano-57500986/

Best channel: LinkedIn connection first. Follow with email only after acceptance or if a verified address appears.

LinkedIn connection note:

```text
Hi Raymond, I am a student studying how training systems connect back into production inference. Your Baseten Loops post made me think about checkpoint deploys as routing and evaluation problems. Would love to connect and ask one technical question.
```

Email subject:

```text
Question on Loops and checkpoint deployment
```

Email body:

```text
Hi Raymond,

I am a student studying how training systems connect back into production inference. I read the Baseten Loops SDK post and was interested in the path from training to one-click deployment, especially when new checkpoints arrive often enough that deployment starts to look like an evaluation and routing problem.

I wrote a one-page technical note on adapter-aware routing for continual-learning inference. The project is a small service design: route requests between control and candidate LoRA adapters, validate compatibility before traffic, and log provenance so each response can be traced back to a checkpoint and training run.

My closest adjacent work is a leakage-safe biomedical evaluation repo with locked folds, train-only preprocessing, artifact tracking, calibration, and stability reports. It maps well to model promotion gates.

Would you be open to a quick 15 minute chat, or is there someone closer to training-to-inference workflows at Baseten I should ask?

Best,
Jonathan
```

Word count: 152

## Target 3: Joey Zwicker

Role: Head of Forward Deployed Engineering

Why this person: Joey leads Baseten's FDE function. He is a good target if the main ask is "who should read this" rather than a deep technical critique from him personally.

Sources:

- Baseten announcement: https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/
- Baseten FDE post: https://www.baseten.co/blog/forward-deployed-engineering/
- LinkedIn: not confirmed from an official source yet. Use LinkedIn search inside the browser before sending.

Best channel: LinkedIn connection first, after confirming the profile in LinkedIn search. Keep the ask routing-oriented.

LinkedIn connection note:

```text
Hi Joey, I am a student exploring FDE-style work around production AI infrastructure. I wrote a short Baseten-specific note on adapter-aware routing for continual-learning inference and would value a pointer to the right FDE or inference person to critique it.
```

Email subject:

```text
Baseten FDE and continual-learning inference
```

Email body:

```text
Hi Joey,

I am a student looking for teams where engineering, product judgment, and production AI infrastructure meet. Baseten's FDE role stood out because it is explicit about turning ambiguous customer goals into reliable, observable services with clear quality, latency, and cost outcomes.

I wrote a one-page technical note around Baseten's continual-learning post. The focus is adapter-aware routing for LoRA checkpoints that change often: validate candidates before traffic, split requests between control and candidate adapters, and keep enough provenance to understand why a checkpoint was promoted.

My closest adjacent project is PolyQuant, a Python/FastAPI forecasting engine with evidence ingestion, revision history, calibration, supervision, and health endpoints. It is not model serving, but the control-plane shape feels similar.

Would it be reasonable to send you the note for feedback, or is there someone on FDE or inference engineering who would be a better first reader?

Best,
Jonathan
```

Word count: 148

## Tracking table

| Company | Person | Medium | Status | First action | Follow-up rule |
| --- | --- | --- | --- | --- | --- |
| Baseten | Bola Malek | LinkedIn | Sent, Pending verified 2026-05-30 | Connection note sent | If accepted, send one-pager note within 24 hours |
| Baseten | Raymond Cano | LinkedIn | Ready for approval | Send connection note | Send only after Bola is sent or if we choose parallel outreach |
| Baseten | Joey Zwicker | LinkedIn | Needs profile confirmation | Confirm profile in LinkedIn search, then send connection note | Use as routing path if engineer response is slow |

## Approval gate

Before I do anything external, confirm this exact block:

```text
Approved first target:
Approved medium:
Approved message:
Include one-pager now: yes/no
Send now or only prepare draft:
```

My recommendation for the first external action:

```text
Approved first target: Bola Malek
Approved medium: LinkedIn connection request
Approved message: the Bola LinkedIn connection note above
Include one-pager now: no
Send now or only prepare draft: send now
```

## Verification checklist

- Bola and Raymond were verified through official Baseten author pages with LinkedIn URLs.
- Joey was verified through the official Baseten announcement, but his direct LinkedIn profile URL still needs confirmation before sending.
- Technical problem verified through Baseten's continual-learning inference post and Loops SDK post.
- No draft claims direct production multi-LoRA serving experience.
- No attachments or links are sent by default.
- Each email draft is under 200 words.
- LinkedIn notes are short enough for connection requests.
- No email address is guessed or used without explicit approval.
