# AI infra outreach notebook

Last updated: 2026-05-30

Purpose: source people, open problems, project ideas, and outreach drafts for AI infrastructure roles. This is an execution notebook, not a public resume. No email, LinkedIn message, connection request, or scheduled send should go out without explicit approval of the recipient, medium, subject, body, timing, and any link or attachment.

## Tab 1: Baseten

### Target thesis

Baseten is the first target because its public work maps directly to production inference, model serving, GPU/runtime optimization, Forward Deployed Engineering, and training-to-inference loops. The best first artifact is a short technical note on adapter-aware routing for continual-learning inference.

### Open problem

Static serving assumes model weights are stable. Baseten's continual-learning post argues that checkpoints and LoRA adapters can arrive frequently and should be treated as candidate hypotheses, not silent replacements. The operational problem is to route requests across control and candidate adapters, validate compatibility before traffic, preserve provenance, and promote only when telemetry supports it.

Technical note title:

```text
Adapter-Aware Routing for Continual-Learning Inference
```

Buildable contribution:

```text
Implement an adapter-aware serving control plane with an adapter registry, deterministic traffic splits, compatibility validation, provenance logs, and a promotion report comparing candidate and control adapters.
```

### People to source first

1. Bola Malek, Forward Deployed Engineer. Best first outreach target because Bola co-authored Baseten's continual-learning post and bridges customer problems with inference product work.
2. Raymond Cano, Software Engineer. Strong fit for training-to-deploy and checkpoint workflow questions through Baseten Loops.
3. Joey Zwicker, Head of Forward Deployed Engineering. Useful for FDE routing and customer-facing production inference work.
4. Mudith Jayasekara, Post-Training Team. Relevant for evals, specialist models, and closing the production-data-to-training loop.
5. Charles O'Neill, Post-Training Team. Relevant for evaluation, post-training, and model improvement loops.

### Roles to watch

1. Applied AI Inference Engineer.
2. Forward Deployed Engineer.
3. Software Engineer - GPU Networking and Distributed Systems.

### Adjacent proof

Use PolyQuant first. It is a Python/FastAPI forecasting engine with evidence ingestion, revision history, calibration, bounded agent coordination, and observability endpoints. The transfer is not "I have served thousands of LoRA adapters." The transfer is "I think about updates as auditable hypotheses with validation, provenance, and promotion rules."

### First outreach draft: Bola

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

Word count: 155.

### Sources

- Baseten continual-learning post: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Baseten Loops SDK: https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/
- Baseten author page, Bola Malek: https://www.baseten.co/author/bola-malek/
- Baseten FDE post: https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/
- vLLM LoRA documentation: https://docs.vllm.ai/en/stable/features/lora/
- S-LoRA paper: https://arxiv.org/abs/2311.03285
- Punica paper: https://arxiv.org/abs/2310.18547
- LoRAX repository: https://github.com/predibase/lorax

## Tab 2: Modal

### Target thesis

Modal is a strong second target because its public work is about making AI infrastructure feel serverless while still handling real GPU constraints: cold starts, lazy image loading, process checkpoint/restore, CUDA state, GPU health, autoscaling, and inference workloads with bursty demand.

### Open problem

Fast inference is not only model optimization. Modal's serverless GPU work frames the bottleneck as replica startup and capacity utilization. New inference replicas need to come online within seconds, but model loading, Python imports, container images, CUDA contexts, and cloud GPU availability can turn this into minutes. The open problem is a cold-start budget and snapshot validation layer for GPU inference workloads.

Project idea:

```text
Build a cold-start budget profiler for GPU inference services that separates image load, Python import, model weight load, CUDA context setup, engine warmup, and first-token latency. Use it to compare a normal startup path against a checkpoint/snapshot-inspired path.
```

### People to source first

1. Charles Frye, Member of Technical Staff. Co-author on the May 2026 "truly serverless GPUs" post.
2. Jonathan Belotti, Member of Technical Staff. Co-author on "truly serverless GPUs" and "Keeping 20,000 GPUs healthy."
3. Erik Bernhardsson, CEO and Founder. Co-author on the serverless GPU post and useful for company-level technical thesis.
4. Akshat Bubna, CTO and Founder. Co-author on the serverless GPU post and technical leadership target.
5. Luis Capelo or Colin Weld. Authors on GPU memory snapshots and cold-start reduction.

### Roles to watch

1. Core infrastructure or runtime engineering roles.
2. GPU infrastructure, reliability, and autoscaling roles.
3. Compute strategy roles only as context, because they reveal the infrastructure constraints engineering has to design around.

### Adjacent proof

Use PolyQuant plus any backend/platform work. The transfer is service reliability, startup path discipline, health checks, structured logs, and control-plane thinking. Robotics work is useful only if the angle is bursty GPU/VLM workloads or multimodal pipelines.

### Outreach angle

Ask for feedback on a cold-start profiling note, not a job. The question should be: "What would a serious engineer measure before claiming GPU startup improvement?"

### Sources

- Modal, "How to achieve truly serverless GPUs": https://modal.com/blog/truly-serverless-gpus
- Modal, "GPU Memory Snapshots": https://modal.com/blog/gpu-mem-snapshots
- Modal, "Keeping 20,000 GPUs healthy": https://modal.com/blog/gpu-health
- Modal inference product page: https://modal.com/products/inference
- Modal compute strategy role context: https://careers.redpoint.com/companies/modal-labs-2/jobs/74795147-compute-strategy-operations-lead

## Tab 3: Fireworks AI

### Target thesis

Fireworks is a strong target because it sits on the same inference-training loop as Baseten, but with a clearer public surface around fine-tuning, LoRA deployment, evals, post-training product, performance optimization, serverless tiers, and on-demand custom deployments.

### Open problem

Fireworks' fine-tuning bottleneck post says the hard part is often the surrounding system: integration, data sovereignty, iteration velocity, evals, training configuration, and deployment. Its LoRA deployment docs make the serving tradeoff explicit: live merge gives maximum performance for one adapter, while multi-LoRA shares a base deployment across many variants but adds dynamic adapter overhead and throughput tradeoffs.

Project idea:

```text
Build a LoRA deployment decision tool that takes adapter count, traffic shape, latency budget, concurrency, model precision, and A/B testing needs, then recommends live merge vs multi-LoRA and emits an evaluation checklist before promotion.
```

### People to source first

1. Lin Qiao, Co-Founder and CEO. Fireworks founding team page lists her as previously Head of PyTorch at Meta.
2. Chenyu Zhao, Co-Founder. Fireworks founding team page lists prior Google Vertex AI lead experience.
3. Dmytro Dzhulgakov, Co-Founder. Founding team page lists prior PyTorch core maintainer experience.
4. James Reed, Co-Founder. Founding team page lists prior PyTorch compiler experience.
5. Hiring/recruiting or performance team contacts through LinkedIn after the technical note is ready.

### Roles to watch

1. Software Engineer, AI Infrastructure.
2. Member of Technical Staff, Performance Optimization.
3. Member of Technical Staff, Evals and Post-Training Product.

### Adjacent proof

Use CFN evaluation work for eval discipline and PolyQuant for control-plane thinking. If targeting Performance Optimization, do not overclaim CUDA or kernel depth. Instead say the first contribution is a decision and validation layer around LoRA deployment choices, then learn the low-level path from the team.

### Outreach angle

Lead with the live-merge vs multi-LoRA tradeoff and the question of how teams avoid sloppy iteration loops. Ask for feedback on the decision tool or the right infra/performance person.

### Sources

- Fireworks fine-tuning bottleneck post: https://fireworks.ai/blog/fine-tuning-bottlenecks
- Fireworks LoRA deployment docs: https://docs.fireworks.ai/fine-tuning/deploying-loras
- Fireworks serverless overview: https://docs.fireworks.ai/serverless/overview
- Fireworks careers: https://fireworks.ai/careers
- Fireworks founding team: https://fireworks.ai/team
- Fireworks AI Infrastructure role: https://job-boards.greenhouse.io/fireworksai/jobs/4056271009
- Fireworks Performance Optimization role: https://job-boards.greenhouse.io/fireworksai/jobs/4001152009
- Fireworks Evals and Post-Training Product role: https://job-boards.greenhouse.io/fireworksai/jobs/4053672009

## Tab 4: Together AI

### Target thesis

Together AI is a strong target if the angle is inference research that ships: kernels, adaptive speculative decoding, request scheduling, hardware-aware optimization, long-context inference, and open-source systems work. The company is public about co-designing software, hardware, algorithms, and models.

### Open problem

Together's inference writing frames production inference as a multi-dimensional optimization problem across latency, throughput, cost, quality, and workload shape. The most interesting outreach angle is adaptive speculative decoding and runtime-learning acceleration: static draft models degrade as traffic shifts, so the serving system needs feedback from live traces without interrupting production.

Project idea:

```text
Build a trace-driven speculative decoding simulator that models target/draft agreement, acceptance rate, request latency, and promotion rules across changing traffic buckets.
```

### People to source first

1. Ce Zhang, Founder and CTO. Public team page lists him as Founder and CTO, and Together content anchors him to inference research at GTC.
2. Tri Dao, Founder and Chief Scientist. Strong kernel and FlashAttention signal.
3. Dan Fu, VP of Kernels. Strong target for kernel/research systems direction.
4. Mahadev Konar, SVP of Engineering Infrastructure. Relevant for infrastructure engineering routing.
5. Albert Meixner, SVP of Engineering. Relevant for broad engineering routing.

### Roles to watch

1. Inference frameworks and optimization roles.
2. ML engineer, inference roles.
3. Infrastructure engineering roles around data platform, GPU clusters, and production serving.

### Adjacent proof

Use CFN eval work if discussing acceptance/promotion rules. Use PolyQuant if discussing traceability and controlled updates. Use GitHub/open-source evidence if discussing implementation discipline.

### Outreach angle

Ask for feedback on the trace-driven simulator idea and whether it is a meaningful way to learn inference optimization without claiming low-level kernel experience upfront.

### Sources

- Together AI inference research post: https://www.together.ai/blog/foundational-research-powering-efficient-inference-at-scale
- Together AI blog index: https://www.together.ai/blog
- Together AI serverless inference page: https://www.together.ai/inference
- Together AI careers page: https://www.together.ai/careers
- Together AI about/team page: https://www.together.ai/about-us
- Together AI inference frameworks role context: https://jobs.generalcatalyst.com/companies/together-ai-2/jobs/69482648-llm-inference-frameworks-and-optimization-engineer

## Verification checklist

Before first send:

1. Every person has a source URL or a LinkedIn profile verified in Tandem.
2. Every role is checked as live on the company career page on the day of send.
3. Outreach stays below 200 words.
4. No message implies experience that is not true.
5. No hype language, no em dashes, no "toy" phrasing.
6. Each message asks for feedback or routing, not a job first.
7. The one-page technical note has one concrete buildable contribution.
8. The medium is confirmed: school email, Gmail, LinkedIn, or conference follow-up.
9. The send action is explicitly approved with recipient, subject, body, time, and any attached link.

## First action queue

1. Baseten: review the Bola draft, then send first if approved.
2. Baseten: prepare Raymond and Joey variants in the same voice.
3. Modal: draft a cold-start profiler note and one outreach message to Charles Frye or Jonathan Belotti.
4. Fireworks: draft a LoRA deployment decision-tool note and one outreach message.
5. Together AI: draft a trace-driven speculative decoding simulator note and one outreach message.
