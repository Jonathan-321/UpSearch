# Company target dossier: Baseten

Last updated: 2026-05-30

## Target thesis

Baseten is a strong first target because the company is publicly focused on production inference, model serving, GPU/runtime optimization, training-to-inference loops, and customer-facing AI infrastructure. The most useful outreach angle is not "I want a job." It is:

> I am studying the infra problem behind continually updated models and want feedback on a small, concrete technical note about adapter-aware routing, validation, and provenance for LoRA checkpoints that change often.

Do not send anything from this packet without explicit approval.

Primary first-send order:

1. Bola Malek: best technical/FDE match for the continual-learning inference note.
2. Raymond Cano: best training-to-deploy loop match.
3. Joey Zwicker: best FDE leadership/routing match.

## Source map

| Source | Why it matters | URL |
| --- | --- | --- |
| Baseten careers page | Company thesis: inference as the foundation for AI product performance, reliability, latency, economics, and quality. | https://www.baseten.co/resources/careers/ |
| Powering Inference for the Continual Learning Era | Primary technical anchor for the outreach angle. Names multi-LoRA serving, continually trained draft models, A/B routing, provenance, architecture-aware merge validation, and hourly checkpoint updates. | https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/ |
| Baseten Loops SDK | Shows Baseten connecting training, RL, checkpointing, and one-click production inference. | https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/ |
| Parsed + Baseten | Shows the broader strategy: training and inference feeding into each other through production data and specialized models. | https://www.baseten.co/blog/parsed-baseten/ |
| Frontier Gateway | Useful secondary angle for routing, auth, multi-tenancy, metering, and lab-facing inference APIs. | https://www.baseten.co/blog/introducing-baseten-frontier-gateway/ |
| Joey Zwicker joins Baseten as Head of FDE | Best public source for how Baseten describes Forward Deployed Engineering. | https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/ |
| Baseten H-1B signal | Third-party signal that Baseten Labs has recent LCA activity. Verify with USCIS/MyVisaJobs again before investing heavily. | https://www.myvisajobs.com/employer/baseten-labs/ |

## People

| Priority | Person | Public role/source | Why this person is relevant | Best first angle | Public source |
| --- | --- | --- | --- | --- | --- |
| 1 | Bola Malek | Forward Deployed Engineer | Co-author on the continual-learning post and author page lists FDE plus Frontier Gateway, custom servers, and Chains. Strong bridge between customer problems and inference product work. | Ask for feedback on the adapter-aware routing note or who owns multi-LoRA/FDE work. | https://www.baseten.co/author/bola-malek/ |
| 2 | Raymond Cano | Software Engineer | Author on Baseten Loops and Training GA. Relevant to training-to-deploy loops, checkpoint workflows, and infrastructure ergonomics. | Ask how Baseten thinks about one-click checkpoint deploys when models keep changing. | https://www.baseten.co/author/raymond-cano/ |
| 3 | Mudith Jayasekara | Post-Training Team | Author on Loops, Parsed acquisition, specialist-model training, and eval/research posts. Relevant to the training side of continual improvement. | Ask about closing the loop from production traces to training data to deployment. | https://www.baseten.co/author/mudith-jayasekara/ |
| 4 | Charles O'Neill | Post-Training Team | Author on Loops, evals, specialist models, and Baseten research. Relevant to evaluation, task-specific models, and post-training methodology. | Ask how to evaluate whether a continually updated adapter actually improved. | https://www.baseten.co/author/charles-o-neill/ |
| 5 | Joey Zwicker | Head of Forward Deployed Engineering | Publicly owns the FDE function and hiring/training for engineers who solve customer production inference problems. | Ask for the right FDE or inference engineer to review a short note. | https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/ |
| 6 | Phil Howes | Co-Founder | Writes on multi-node inference, MCM, global infra, and model serving. High-signal technical leadership, but likely harder to reach cold. | Use only after the note is strong, with a very specific infrastructure question. | https://www.baseten.co/author/phil-howes/ |
| 7 | Amir Haghighat | CTO, Co-Founder | Publicly explains Baseten's shift toward model/runtime optimizations, horizontal scale, regions, clouds, monitoring, and inference visibility. | Use after the note has substance. Ask a technical strategy question, not a referral request. | https://www.baseten.co/author/amir-haghighat/ |
| 8 | Marylise Tauzia | Head of Product Marketing | Co-author on continual-learning and Frontier Gateway posts. Less likely to be the core engineering target, but useful for narrative, product positioning, and routing to the right person. | Ask for the right technical owner only if engineer routes are cold. | https://www.baseten.co/author/marylise-tauzia/ |

Partner context, not first outreach targets: Michael Elabd and Arjun Karanam from Trajectory AI are co-authors on the continual-learning post. They are useful for understanding the customer/problem context, but the first motion should stay with Baseten engineers and FDE.

## Roles ranked by fit

| Rank | Role | Fit | Why | Source |
| --- | --- | --- | --- | --- |
| 1 | Applied AI Inference Engineer | Highest | Directly combines customer-facing production AI, inference architecture, performance engineering, and deployment. Best match for a student who can turn a technical note into customer-aware engineering judgment. | https://jobs.ashbyhq.com/baseten/90e9ff4e-1225-4b1b-b0b4-2362e36d9cfa/ |
| 2 | Forward Deployed Engineer | Very high | Hands-on coding plus product/customer work. Strong route if the goal is to learn real production inference problems while building trust with technical teams. | https://jobs.ashbyhq.com/baseten/84c1801c-1a65-49fb-aaaa-beeafd530e7e |
| 3 | Software Engineer - GPU Networking & Distributed Systems | High, more specialized | Strong systems fit if the technical note expands toward placement, routing, networking, scaling, and distributed GPU serving. | https://jobs.ashbyhq.com/baseten/1f7d7fda-5540-4205-890b-cdbf774f0814/ |

Secondary roles to monitor:

| Role | Why monitor | Source |
| --- | --- | --- |
| Software Engineer - GPU Inference | Strong thematic fit, but the saved URL now resolves to a generic Ashby jobs page instead of the job title. Do not cite as currently open unless it reappears. | https://jobs.ashbyhq.com/baseten/aef40249-e1fa-48d8-972d-c6d76fde0639 |
| Post-Training Research Scientist | Too senior for a direct job target unless you have deep research proof, but useful for understanding Baseten's research agenda. | https://jobs.ashbyhq.com/baseten/7c9d2bb0-ac03-4a3c-86c3-cf720cd314e8/ |
| Software Engineer - Model Developer Ecosystem | Good thematic fit, but the saved URL now resolves to a generic Ashby jobs page instead of the job title. Do not cite as currently open unless it reappears. | https://jobs.ashbyhq.com/baseten/c732f253-7046-4e49-8510-71de3e670686/ |
| Software Engineer - GPU Kernels | High-performance systems role. Only target if you can credibly talk CUDA/kernel optimization or are ready to learn it deeply. | https://jobs.ashbyhq.com/baseten/ddb5bc98-6116-49a2-802e-1c05398663f1/ |

Role status checked on 2026-05-30. Confirmed live by page title: Applied AI Inference Engineer, Forward Deployed Engineer, Software Engineer - GPU Networking & Distributed Systems, Post-Training Research Scientist, and Software Engineer - GPU Kernels.

## Open problem

Static serving assumes the model weights are stable. Baseten's continual-learning post makes the opposite assumption: checkpoints and LoRA adapters can arrive hourly, differ by customer or experiment, and need validation, routing, observability, and provenance before they should affect production users. The strongest open problem for outreach is multi-LoRA / continual-learning inference: how to serve many customer-specific or experiment-specific adapters from a shared base model without paying the cost of full merges and redeploys, while still preserving correctness checks, A/B evaluation, multi-tenant isolation, and traceability from request to training run.

Evidence:

- Baseten says modern serving optimizations assume stable weights, while continual learning compresses the deployment cadence and multiplies model variants: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Baseten names the next step as a base-resident architecture that selects an adapter per request: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Baseten's routing layer treats every new checkpoint as an experimental variant, logs model provenance, and promotes only when telemetry supports it: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Baseten Loops emphasizes training infrastructure with a path from training directly to production inference: https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/

## Technical note outline

Working title:

```text
Adapter-Aware Routing for Continual-Learning Inference
```

Problem:

Production inference stacks are usually optimized around a fixed model artifact. Continual learning turns the model into a moving target: new adapters/checkpoints arrive often, different customers may need different variants, and every promotion decision needs evidence.

Why it is hard:

- Adapter count grows faster than the number of base models.
- Naive merge-and-deploy workflows create latency, operational cost, and validation bottlenecks.
- A/B routing needs to preserve customer isolation and clean telemetry.
- Model provenance must connect inference responses back to adapter version, base model version, training run, deployment time, and evaluation result.
- Speculative decoding gets harder because a draft model/head can become stale as the target model changes.

Current landscape:

- vLLM supports LoRA adapters and OpenAI-compatible serving with LoRA modules: https://docs.vllm.ai/en/stable/features/lora/
- S-LoRA studies serving thousands of concurrent LoRA adapters through unified paging, heterogeneous batching, and custom kernels: https://arxiv.org/abs/2311.03285
- Punica studies multi-tenant LoRA serving with a shared base model and custom CUDA kernel design: https://arxiv.org/abs/2310.18547
- LoRAX is a production-oriented open-source multi-LoRA inference server with dynamic adapter loading, heterogeneous batching, adapter exchange scheduling, metrics, tracing, and OpenAI-compatible APIs: https://github.com/predibase/lorax
- Hacker News and Reddit discussions show this is not only an academic problem. Users keep asking for one-base-many-adapters serving, dynamic adapter routing, and practical throughput tradeoffs: https://news.ycombinator.com/item?id=38201318 and https://www.reddit.com/r/LocalLLaMA/comments/17xniii
- Baseten's EAGLE-3 post gives a secondary speculative decoding angle: draft heads help latency, but the continual-learning post points out that draft models can go stale when target models refresh often. Sources: https://www.baseten.co/blog/how-to-train-custom-eagle-3-heads-for-speculative-decoding/ and https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/

Small useful contribution:

Build an adapter-aware serving loop that does not try to replicate Baseten's internal system. The goal is to demonstrate rigorous product and systems thinking around the control plane:

1. Base model plus N LoRA adapters in an adapter registry.
2. Request schema includes customer_id, route_id, adapter_version, control_or_candidate, and experiment_id.
3. Router splits traffic between control and candidate adapters with deterministic bucketing.
4. Validator runs simple checks before a candidate can receive traffic: adapter metadata present, base model compatibility, expected rank/target modules, smoke prompt quality, latency budget.
5. Provenance logger records base model, adapter id, adapter version, training run id, route, request id, latency, status, and evaluation label.
6. Promotion rule compares candidate vs control on simple offline or replayed metrics.

What to build in 1 to 2 weeks:

- A small Python FastAPI service or notebook simulation.
- Use vLLM/LoRAX only if setup is easy; otherwise mock the model call and focus on the routing, validation, provenance, and promotion logic.
- Include a short README with diagrams, failure modes, and how this maps to real multi-LoRA serving systems.
- Optional stretch: run two tiny PEFT LoRA adapters locally and route between them.

How to measure whether it works:

- Provenance completeness: every response has adapter, base model, route, and experiment metadata.
- Traffic split accuracy: observed split stays near configured split over replayed requests.
- Validation catch rate: intentionally malformed adapter metadata is rejected before routing.
- Latency overhead: router/provenance overhead remains small in the mock service.
- Promotion auditability: a third person can explain why a candidate was or was not promoted by reading the logs.

## Adjacent proof

Use only claims that are true. Do not imply direct production LoRA-serving experience unless you actually have it.

Truth-safe positioning:

- "I have not served thousands of LoRA adapters in production, but I am trying to understand the control-plane problem around routing, validation, and provenance."
- "My PolyQuant project maps to this because it treats updates as auditable events with evidence, revision history, calibration, and bounded supervision."
- "My CFN biomedical evaluation work maps to this because it focuses on leakage-safe comparisons, locked protocols, artifact tracking, calibration, and stability checks before making claims."
- "My robotics/VLA work remains useful when the angle is multimodal data pipelines, feedback loops, distribution shift, and traceability from behavior back to data or training signals."
- "My AI infrastructure interest maps to this through deployment, observability, model serving, and reliable iteration rather than benchmark chasing."
- "The contribution I can make first is a clean technical note plus a small implementation that shows I understand the problem shape."

Proof options to use in outreach:

```text
PolyQuant: My closest adjacent project is PolyQuant, a supervised forecasting engine with revision history, calibration, and bounded agent coordination. It made me think about model updates as auditable hypotheses rather than silent replacements.

CFN eval: My closest adjacent work is a leakage-safe biomedical evaluation repo with locked folds, train-only preprocessing, artifact tracking, calibration, and stability reports. It maps well to model promotion gates.

Robotics/VLA: I have also worked around cloud pipelines for robot demonstration data, including validation, multimodal annotation, and dataset generation. I would use that proof where data pipelines or robotics are the right angle.
```

What transfers:

- Thinking in feedback loops: production traces become training signal, training emits new model variants, inference must evaluate and route those variants safely.
- Systems framing: separate the data plane from the control plane, then track routing, validation, logging, and promotion explicitly.
- Evaluation discipline: do not claim a new model is better without comparison to a control and enough provenance to debug failures.
- Agent/control-plane discipline: bounded updates, terminal states, escalation rules, and health/observability endpoints from PolyQuant map naturally to model-serving promotion workflows.

What to learn next:

- vLLM LoRA serving details and limitations.
- S-LoRA/Punica/LoRAX architecture tradeoffs.
- LoRA compatibility issues across target modules, ranks, quantization, MoE, and fused projections.
- Practical A/B testing and telemetry design for model-serving systems.
- Speculative decoding acceptance rates when target model weights or adapters change.

## Tailored outreach draft 1: Bola Malek

Subject:

```text
Question on adapter-aware routing for continual learning
```

Body:

```text
Hi Bola,

I am a student exploring inference systems for models that keep changing after deployment. I read Baseten's Trajectory post and the part that stuck with me was the inversion from "new version replaces old version" to "new checkpoint is a hypothesis and old checkpoint is the control."

I am writing a one-page technical note on adapter-aware routing for continual-learning inference. The project is a small serving loop where each request carries adapter/version metadata, traffic splits between control and candidate adapters, and validation records provenance plus quality and latency counters before promotion.

My closest adjacent project is PolyQuant, a supervised forecasting engine with revision history, calibration, and bounded agent coordination. It made me think about model updates as auditable hypotheses rather than silent replacements.

Would you be open to a quick 15 minute chat, or is there someone closer to Baseten's multi-LoRA or FDE work you would recommend I learn from?

Best,
Jonathan
```

Word count: 155

## Tailored outreach draft 2: Raymond Cano

Subject:

```text
Question on Loops and checkpoint deployment
```

Body:

```text
Hi Raymond,

I am a student studying how training systems connect back into production inference. I read the Baseten Loops SDK post and was interested in the path from training to one-click deployment, especially when new checkpoints arrive often enough that deployment starts to look like an evaluation and routing problem.

I am writing a one-page technical note on adapter-aware routing for continual-learning inference. The project is a small service design: route requests between control and candidate LoRA adapters, validate compatibility before traffic, and log provenance so each response can be traced back to a checkpoint and training run.

My closest adjacent work is a leakage-safe biomedical evaluation repo with locked folds, train-only preprocessing, artifact tracking, calibration, and stability reports. It maps well to model promotion gates.

Would you be open to a quick 15 minute chat, or is there someone closer to training-to-inference workflows at Baseten I should ask?

Best,
Jonathan
```

Word count: 152

## Tailored outreach draft 3: Joey Zwicker

Subject:

```text
Baseten FDE and continual-learning inference
```

Body:

```text
Hi Joey,

I am a student looking for teams where engineering, product judgment, and production AI infrastructure meet. Baseten's FDE role stood out because it is explicit about turning ambiguous customer goals into reliable, observable services with clear quality, latency, and cost outcomes.

I am preparing a one-page technical note around Baseten's continual-learning post. The focus is adapter-aware routing for LoRA checkpoints that change often: validate candidates before traffic, split requests between control and candidate adapters, and keep enough provenance to understand why a checkpoint was promoted.

My closest adjacent project is PolyQuant, a Python/FastAPI forecasting engine with evidence ingestion, revision history, calibration, supervision, and health endpoints. It is not model serving, but the control-plane shape feels similar.

Would it be reasonable to send you the note for feedback, or is there someone on FDE or inference engineering who would be a better first reader?

Best,
Jonathan
```

Word count: 148

## First action checklist

1. Primary person selected: Bola Malek. Raymond Cano and Joey Zwicker have tailored backup drafts.
2. One-page technical note created: `baseten-adapter-aware-routing-note.md`.
3. Truthful personal project sentence added to all three tailored drafts, with PolyQuant/CFN used before robotics where they fit better.
4. Role status checked on 2026-05-30.
5. Confirm sponsorship signal using USCIS/MyVisaJobs/Levels.fyi and ask HR directly if the conversation becomes concrete.
6. Send only after explicit approval.
7. Track sent date, medium, reply, follow-up date, and next step.

## Verification checklist

- Passed: every person listed has a public source URL.
- Passed: every ranked role has a public job URL.
- Passed: confirmed-live role titles by page title on 2026-05-30: Applied AI Inference Engineer, Forward Deployed Engineer, Software Engineer - GPU Networking & Distributed Systems, Post-Training Research Scientist, and Software Engineer - GPU Kernels.
- Watch item: Software Engineer - GPU Inference and Software Engineer - Model Developer Ecosystem URLs returned HTTP 200 but resolved to a generic Ashby "Jobs" page, so they should not be cited as currently open.
- Passed: Bola outreach draft is 155 words.
- Passed: Raymond outreach draft is 152 words.
- Passed: Joey outreach draft is 148 words.
- Passed: no draft claims direct experience serving LoRA adapters in production.
- Passed: no casual prototype language remains in the dossier or technical note.
- Passed: no em dashes or non-ASCII punctuation remain in the local files.
- Passed: the technical note has one buildable contribution: an adapter-aware routing, validation, provenance, and promotion loop.
- Passed: no email, LinkedIn message, or X message has been sent.
- Caveat: MyVisaJobs returned HTTP 403 to `curl`, likely bot blocking. Treat it as a sponsorship lead to verify manually or through USCIS before relying on it.
