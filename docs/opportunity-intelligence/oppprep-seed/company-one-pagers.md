# AI infrastructure company one-pagers

Last updated: 2026-05-30

Use: technical outreach proposal pack. Each page is meant to show that I understand a real company-specific systems problem, can scope a credible contribution, and can ask for feedback without pretending I already have the exact production experience.

## Baseten: Adapter-aware routing for continual-learning inference

### Problem

Baseten's continual-learning post reframes model deployment: a new checkpoint is not automatically "the next version." It is a candidate hypothesis, while the previous checkpoint remains the control. That changes inference from static serving into a control-plane problem. New LoRA adapters or checkpoints can arrive frequently, differ by customer or experiment, and require validation before they affect users.

The serving layer needs to decide which adapter each request should use, whether the candidate adapter is compatible with the base model and runtime, how much traffic it should receive, and whether every response can be traced back to adapter version, base model version, route, experiment, and training run.

### Buildable contribution

I would build an adapter-aware routing and validation service for continual-learning inference. The first version would focus on control-plane rigor, not full production serving.

Core pieces:

1. Adapter registry with base_model_id, adapter_id, version, training_run_id, rank, target_modules, compatibility notes, and status.
2. Deterministic router that splits traffic between control and candidate adapters using customer_id, route_id, and experiment_id.
3. Validation gate for base-model compatibility, adapter shape, target modules, traffic cap, smoke prompts, and latency budget.
4. Provenance logger that records request_id, route, experiment, base model, adapter version, training run, latency, status, and evaluation label.
5. Promotion report comparing candidate and control on latency, error rate, smoke pass rate, and quality labels.

### Execution plan

Week 1: implement the registry, route policy, request schema, structured logs, and replay script with mocked model calls. Week 2: add validation gates, failure cases, promotion reports, and a README mapping the design to vLLM, LoRAX, S-LoRA, and Punica. Stretch: run two small PEFT adapters through vLLM or LoRAX and reuse the same control-plane logic.

### Why I can contribute

My adjacent proof is PolyQuant: a Python/FastAPI forecasting system with evidence ingestion, revision history, calibration, bounded agent coordination, and health endpoints. The transfer is control-plane discipline: treat updates as auditable hypotheses, preserve provenance, and avoid silent promotion without evidence.

### Outreach hook

Ask for feedback on whether this captures the right multi-LoRA/FDE problem shape, or who at Baseten is closest to adapter routing, validation, and continual-learning inference.

Sources: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/ ; https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/ ; https://docs.vllm.ai/en/stable/features/lora/ ; https://github.com/predibase/lorax ; https://arxiv.org/abs/2311.03285 ; https://arxiv.org/abs/2310.18547

## Modal: Cold-start budget profiler for serverless GPU inference

### Problem

Modal's serverless GPU work is centered on the reality that inference traffic is bursty and external. A platform may need new GPU replicas in seconds, but startup can be dominated by container image loading, Python imports, model weight loading, CUDA context setup, runtime warmup, health checks, and first-token latency.

The core problem I would study is measurement. Before claiming a GPU inference service starts quickly, a team needs to know where startup time goes. Otherwise cold-start work becomes vague, and it is unclear whether the bottleneck is image distribution, dependency import, weights, CUDA setup, scheduler placement, or the model server.

### Buildable contribution

I would build a cold-start budget profiler for GPU inference services.

Core pieces:

1. Instrumented startup phases: process start, imports, model discovery, weight load, CUDA setup, warmup, health check, and first token.
2. Structured JSON trace for each startup run.
3. Human-readable budget report with phase timings and dominant bottleneck.
4. Repeated-run summary with p50 and p95 startup timing.
5. Failure labels for missing weights, slow imports, CUDA errors, warmup timeout, and health-check failures.

### Execution plan

Week 1: build a FastAPI or CLI harness that simulates an inference server startup path and records phase timings. Start with a mocked model path so the profiler design is not blocked by local GPU access. Week 2: add repeated runs, summary reports, failure modes, and a README mapping each phase to Modal's public architecture: cloud buffers, custom filesystem, checkpoint/restore, and CUDA checkpoint/restore. Stretch: compare a normal startup path with a snapshot-inspired path where CPU-side setup is precomputed.

### Why I can contribute

PolyQuant gives me adjacent proof around backend services, health endpoints, structured outputs, and revision discipline. The connection to Modal is service reliability and visibility into the startup path, not a claim that I have implemented GPU checkpoint/restore.

### Outreach hook

Ask a Modal engineer what a serious cold-start budget should measure before any optimization claim is meaningful.

Sources: https://modal.com/blog/truly-serverless-gpus ; https://modal.com/blog/gpu-mem-snapshots ; https://modal.com/blog/gpu-health ; https://modal.com/products/inference

## Fireworks AI: LoRA deployment decision and validation layer

### Problem

Fireworks' LoRA deployment docs make a useful tradeoff explicit. Live merge is strongest when one fine-tuned model needs maximum latency and throughput. Multi-LoRA is stronger when many variants share a base deployment, especially for experiments, customer-specific adapters, and A/B testing, but dynamic adapter application adds overhead and compatibility constraints.

That creates a practical user question: given adapter count, traffic shape, latency target, concurrency, precision constraints, and evaluation needs, which deployment path should a team choose? A weak choice can waste GPU resources, add avoidable latency, or make model iteration harder to interpret.

### Buildable contribution

I would build a LoRA deployment decision and validation layer.

Inputs:

1. Adapter count and expected traffic per adapter.
2. Latency, throughput, and concurrency requirements.
3. A/B testing or rapid-iteration needs.
4. Base-model precision and addon compatibility.
5. Evaluation and promotion requirements.

Outputs:

1. Recommendation: live merge, multi-LoRA, or defer until constraints are clearer.
2. Reasoning in terms of latency, throughput, cost, and iteration speed.
3. Compatibility checks before deployment.
4. Evaluation checklist before promotion.
5. Observability fields to log during rollout.

### Execution plan

Week 1: implement a CLI or notebook that encodes the decision logic from public Fireworks docs. Include four examples: one production adapter, many customer adapters, high-concurrency experiment, and base-model compatibility issue. Week 2: add validation outputs, rollout metrics, and a README explaining what the tool does not know, including Fireworks-internal scheduling details and exact throughput curves. Stretch: connect it to a mock traffic simulator.

### Why I can contribute

My CFN evaluation work maps to this through locked protocols, artifact tracking, calibration, and stability checks before making claims. PolyQuant maps through revision history and controlled promotion logic.

### Outreach hook

Ask whether this decision layer maps to real customer confusion around live merge vs multi-LoRA, and who is closest to inference, performance optimization, or post-training product.

Sources: https://docs.fireworks.ai/fine-tuning/deploying-loras ; https://fireworks.ai/blog/fine-tuning-bottlenecks ; https://docs.fireworks.ai/serverless/overview ; https://fireworks.ai/team ; https://fireworks.ai/careers

## Together AI: Trace-driven simulator for speculative decoding under shifting traffic

### Problem

Together AI frames production inference as a systems problem across latency, throughput, cost, concurrency, and workload shape. Agentic systems sharpen the issue because one user action can require several model calls. Small latency inefficiencies compound across the workflow.

Speculative decoding can reduce latency, but it depends on agreement between a faster draft path and the target model. If traffic shifts, context lengths vary, or specialized workloads emerge, static assumptions about draft acceptance can degrade. The question is how to reason about acceptance rate, latency impact, and rollback criteria from traces before making production changes.

### Buildable contribution

I would build a trace-driven speculative decoding simulator.

Core pieces:

1. Request classes with prompt length, output length, workflow step, and latency target.
2. Configurable target/draft agreement and acceptance rate.
3. Traffic buckets that can shift over time.
4. Latency comparison for baseline decoding vs speculative decoding.
5. Segment-level regression detection so aggregate wins do not hide specific failures.
6. Promotion or rollback rule based on logged traces.

### Execution plan

Week 1: implement a simulator with synthetic traces and configurable acceptance rates. Output latency, throughput, and cost proxies across traffic buckets. Week 2: add drift scenarios, multi-call agent workflows, and promotion rules. Produce a report comparing baseline decoding, stable speculative decoding, and speculative decoding under shifting acceptance. Stretch: replay a small public or generated trace and connect the simulator to an open-source benchmark format.

### Why I can contribute

CFN evaluation work maps to controlled comparisons, artifact tracking, and stability analysis. PolyQuant maps to traceability, revision history, and decision reports. The honest position is that I am learning inference optimization by first building a rigorous measurement artifact.

### Outreach hook

Ask whether a trace-driven simulator is a credible way to learn inference optimization before going deeper into kernels.

Sources: https://www.together.ai/blog/foundational-research-powering-efficient-inference-at-scale ; https://www.together.ai/inference ; https://www.together.ai/about-us ; https://www.together.ai/careers
