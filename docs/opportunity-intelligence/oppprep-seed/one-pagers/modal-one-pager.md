# Cold-Start Budget Profiler for Serverless GPU Inference

Company: Modal
Prepared by: Jonathan Muhire
Date: 2026-05-30

## Technical Thesis

Modal's serverless GPU work highlights a practical truth about AI infrastructure: inference traffic is bursty, user-facing, and hard to forecast. A platform may need new GPU replicas in seconds, but startup time can be dominated by container image loading, Python imports, model weight loading, CUDA context setup, runtime warmup, health checks, and first-token latency. The first serious step toward improving cold starts is measuring where the time actually goes.

I would build a cold-start budget profiler for GPU inference services. The goal is not to reproduce Modal's internal checkpoint/restore system. The goal is to create a precise measurement harness that makes startup claims falsifiable. If a service is slow to scale up, the profiler should make the dominant bottleneck obvious and produce a report a systems engineer can use to decide which optimization to attack first.

## Problem

Cold-start discussions can become vague because "startup time" compresses several different phases into one number. A model-serving replica may be delayed by image fetch, filesystem hydration, Python interpreter startup, dependency import, model file discovery, weight loading, GPU memory allocation, CUDA context initialization, runtime compilation, engine warmup, or the first real request. Without phase-level instrumentation, it is hard to know whether a platform should optimize storage, scheduling, checkpointing, image construction, runtime initialization, or model server behavior.

This matters most for inference systems because idle capacity is expensive, but slow scale-up degrades user experience. A useful measurement tool should separate infrastructure overhead from application overhead and make the startup budget visible across repeated runs.

## Proposed Build

I would build a profiler that wraps a minimal inference service startup path and emits structured timing data.

Core components:

1. Phase tracker: records process start, environment setup, dependency imports, model discovery, weight loading, CUDA setup, runtime warmup, health check, and first token.
2. Structured trace: writes one JSON object per run with phase durations, status, failure label, and environment metadata.
3. Summary report: aggregates repeated runs into p50, p95, max, and dominant bottleneck by phase.
4. Failure classifier: labels missing weights, slow imports, CUDA errors, warmup timeouts, health-check failures, and first-token regressions.
5. Comparison mode: compares a baseline startup path against an optimized or snapshot-inspired path.

The first version would work without local GPU access by mocking the model call and simulating GPU phases. A later version could run against a small local model or hosted GPU environment, preserving the same instrumentation interface.

## Execution Plan

Week 1 would implement the CLI or FastAPI harness, phase timers, JSON traces, and a single-run budget report. The service would include configurable artificial delays so bottlenecks can be tested deterministically. Week 2 would add repeated-run summaries, failure labels, p50/p95 reporting, and a README mapping each measured phase to Modal's public architecture: serverless GPU scaling, custom filesystem, memory snapshots, cloud buffers, and CUDA checkpoint/restore.

The final artifact would include runnable examples, saved traces, comparison reports, and a short design note explaining what the profiler can and cannot infer. The design would be intentionally modest: strong measurement first, optimization claims second.

## Success Criteria

The profiler should separate startup phases cleanly. Repeated runs should produce stable summaries. A single report should identify the largest bottleneck without manual log inspection. Measurement overhead should be visible. Failure labels should make broken startup paths easier to debug. A systems engineer should be able to inspect the output and say whether the next optimization belongs in image construction, filesystem hydration, Python import, model loading, CUDA setup, or runtime warmup.

## Relevant Background

PolyQuant gives me adjacent proof around backend services, health endpoints, structured outputs, and revision discipline. The connection to Modal is not that I have implemented GPU checkpoint/restore. The connection is that I can build service instrumentation, separate control-plane state from data-path execution, and produce reports that make operational behavior easier to reason about.

## Outreach Ask

I would ask what a serious cold-start budget should measure before any optimization claim is meaningful, and whether this profiler structure misses an important phase that Modal engineers would care about.

Sources: https://modal.com/blog/truly-serverless-gpus ; https://modal.com/blog/gpu-mem-snapshots ; https://modal.com/blog/gpu-health ; https://modal.com/products/inference
