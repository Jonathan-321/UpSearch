# Adapter-Aware Routing for Continual-Learning Inference

Company: Baseten
Prepared by: Jonathan Muhire
Date: 2026-05-30

## Technical Thesis

Baseten's continual-learning framing points to a concrete inference systems problem: a new checkpoint is not simply the next version of a model. It is a candidate hypothesis, and the previous checkpoint remains the control. Once model updates become frequent, static serving assumptions break. The hard problem is not only how to load many LoRA adapters. It is how to route, validate, observe, and promote those adapters without losing provenance or customer isolation.

I would approach this as a control-plane project for continual-learning inference: build an adapter-aware routing service that keeps model updates explicit, testable, and auditable. The system would not try to reproduce Baseten's internal platform. It would isolate the part of the problem that is easiest to reason about externally and most useful for outreach: adapter registry, deterministic routing, compatibility validation, structured telemetry, and promotion reports.

## Problem

In a production setting, new LoRA adapters or checkpoints may be produced by post-training loops, customer-specific tuning, or experiments. Those variants can differ by base model, adapter rank, target modules, quantization assumptions, traffic policy, and evaluation status. A naive merge-and-deploy workflow makes every update operationally expensive and can hide what actually changed. A naive dynamic-adapter workflow can create the opposite issue: too many variants moving through the system without clear validation or promotion rules.

The serving layer needs to answer five questions on every rollout:

1. Which adapter should this request use?
2. Is the candidate adapter compatible with the current base model and serving runtime?
3. Is the candidate receiving the intended share of traffic?
4. Can every response be traced back to adapter version, route, experiment, and training run?
5. What evidence is required before the candidate is promoted or rolled back?

## Proposed Build

I would build a small adapter-aware routing and validation service with the following components:

1. Adapter registry: tracks base_model_id, adapter_id, adapter_version, training_run_id, rank, target_modules, compatibility notes, rollout status, and created_at.
2. Deterministic router: splits traffic between control and candidate adapters using customer_id, route_id, experiment_id, and a configured traffic cap.
3. Validation gate: checks base-model compatibility, adapter shape, target modules, quantization assumptions, smoke prompts, and latency budget before candidate traffic is allowed.
4. Provenance logger: records request_id, customer_id, route, experiment, base model, adapter version, training run, latency, status, and evaluation label.
5. Promotion report: compares candidate and control on latency, error rate, smoke pass rate, and available quality labels.

The first version would mock model calls so that the control plane is crisp. A second version would connect the same routing and validation logic to vLLM or LoRAX with two small PEFT adapters. That keeps the scope realistic while still showing how the design maps onto multi-LoRA serving systems.

## Execution Plan

Week 1 would focus on the core service: adapter registry schema, request schema, deterministic routing, structured JSON logs, replay script, and basic traffic split checks. Week 2 would add validation failures, promotion reports, compatibility scenarios, and a README that maps the design to vLLM LoRA serving, LoRAX dynamic adapter loading, S-LoRA batching, and Punica-style multi-tenant adapter serving.

The final artifact would include a runnable service or notebook, replayable request traces, logs, promotion examples, failure cases, and a short design note explaining tradeoffs. The point is not to claim production completeness. The point is to demonstrate disciplined systems thinking around routing, validation, and promotion under continuous model change.

## Success Criteria

Every response should include complete provenance metadata. Candidate traffic should stay within the configured traffic cap. Invalid adapter metadata should be rejected before traffic. Promotion decisions should be reproducible from logs. A third-party inference engineer should be able to inspect the repository and understand what would need to change before the design could be used with real model-serving infrastructure.

## Relevant Background

My adjacent proof is PolyQuant, a Python/FastAPI forecasting system with evidence ingestion, revision history, calibration, bounded agent coordination, and health endpoints. The relevant transfer is control-plane discipline: treat updates as auditable hypotheses, preserve provenance, expose health and revision state, and avoid silent promotion without evidence. I would position this honestly as adjacent systems experience, not prior production multi-LoRA serving.

## Outreach Ask

I would ask whether this captures the right problem shape for Baseten's continual-learning and multi-LoRA work, and whether there is someone closer to adapter routing, validation, or FDE-owned inference workflows who would be willing to critique the design.

Sources: https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/ ; https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/ ; https://docs.vllm.ai/en/stable/features/lora/ ; https://github.com/predibase/lorax ; https://arxiv.org/abs/2311.03285 ; https://arxiv.org/abs/2310.18547
