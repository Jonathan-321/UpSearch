# Adapter-Aware Routing for Continual-Learning Inference

Last updated: 2026-05-30

## Context

Baseten's continual-learning post describes a shift from static model serving to systems where new checkpoints and LoRA adapters can arrive frequently. In that setting, a new model variant is not simply "the next version." It is a candidate hypothesis that has to be routed, evaluated, compared to a control, and traced back to the training run that produced it.

This note focuses on the control-plane problem around that workflow: how to route traffic between LoRA adapters, validate candidate adapters before they receive traffic, and preserve enough provenance to debug or promote a model variant responsibly.

Sources:

- Baseten, "Powering Inference for the Continual Learning Era": https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/
- Baseten, "Introducing the Baseten Loops SDK": https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/
- vLLM LoRA documentation: https://docs.vllm.ai/en/stable/features/lora/
- LoRAX: https://github.com/predibase/lorax
- S-LoRA: https://arxiv.org/abs/2311.03285
- Punica: https://arxiv.org/abs/2310.18547

## Problem

Production inference stacks are often optimized around stable model artifacts. Continual learning changes the operational assumption. A system may have one base model, many adapters, customer-specific variants, experiment-specific variants, and frequent updates from training or post-training pipelines.

The difficult part is not only loading adapters. The serving system also needs to answer:

- Which adapter should this request use?
- Is the candidate adapter compatible with the current base model and serving runtime?
- Is the candidate receiving a controlled amount of traffic?
- Can every response be traced back to the base model, adapter version, training run, and experiment?
- What evidence is required before promotion?

## Proposed project

Build a small but rigorous adapter-aware routing service that models the control plane for continual-learning inference.

The service would include:

1. An adapter registry with base_model_id, adapter_id, adapter_version, training_run_id, rank, target_modules, status, and created_at.
2. A request router that selects control or candidate adapters using deterministic bucketing by customer_id, route_id, and experiment_id.
3. A validation gate that checks adapter metadata, base model compatibility, expected target modules, configured traffic cap, and a smoke evaluation before traffic.
4. A provenance logger that records request_id, customer_id, base_model_id, adapter_id, adapter_version, training_run_id, experiment_id, latency_ms, output_status, and evaluation_label.
5. A promotion report that compares candidate and control traffic on latency, error rate, smoke evaluation pass rate, and any available quality labels.

The first implementation can mock the model call so the project stays focused on routing, validation, provenance, and promotion logic. A second version could plug in vLLM or LoRAX with two small PEFT adapters to test the same control-plane design against real adapter loading.

## Expected output

The deliverable is a short repository or notebook with:

- A minimal FastAPI or CLI interface for registering adapters and routing requests.
- A replay script that sends requests through a configured control/candidate split.
- Structured JSON logs for provenance.
- A promotion report that explains whether a candidate adapter should receive more traffic.
- A README mapping the project to production systems such as vLLM, S-LoRA, Punica, LoRAX, and Baseten's continual-learning framing.

## Success criteria

- Every response contains complete provenance metadata.
- Candidate traffic stays within the configured traffic cap.
- Invalid adapter metadata is rejected before traffic.
- Promotion decisions are reproducible from logs.
- The design is clear enough that an inference engineer can critique the tradeoffs without needing to run a large model locally.

## Why this is a useful first contribution

This project does not claim to reproduce a production inference platform. It isolates a real systems question that shows up when models keep changing: how to manage routing, validation, telemetry, and promotion without losing traceability. That makes it a practical entry point for deeper work on multi-LoRA serving, training-to-inference loops, and customer-facing AI infrastructure.
