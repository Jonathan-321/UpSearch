# Cold Start Latency in ML Model Serving — Baseten

**Company:** Baseten  
**Problem focus:** Cold start latency in GPU-backed model serving  
**Date:** 2026-05-31  

---

## Problem

When a model has received no traffic for a period, its container and GPU memory are released.
The first request after this idle period pays the full cost of container startup, model weight
loading from storage, and CUDA kernel compilation. For large models this can exceed 30 seconds —
unacceptable for interactive applications.

Baseten's Truss-based serving layer abstracts model packaging, but cold start behavior is
ultimately driven by the interaction between container orchestration, weight loading I/O, and
GPU driver initialization. Reducing this latency without keeping idle GPUs warm (expensive) is
an open systems problem.

## Current Landscape

Standard mitigations include pre-warming (proactive keep-alive), weight caching on fast local
storage (NVMe), and lazy weight loading (loading weights in the background while serving early
requests with reduced capacity). Serverless inference platforms like Modal and Fireworks have
published some approaches, but no open benchmark exists that measures cold start across providers
and model sizes under realistic traffic patterns.

CUDA graph capture (used in vLLM and TensorRT-LLM) reduces kernel compilation time on
subsequent requests but does not solve the initial weight loading cost. Speculative pre-loading
based on traffic forecasts is promising but requires platform-level integration.

## Contribution Idea

A student-scale contribution: build a reproducible cold start benchmark using open-source
serving frameworks (vLLM, Ollama, TGI) across different model sizes (7B, 13B, 34B) and measure
the time breakdown by stage: container startup, weight load, first-token latency. Publish the
methodology and results as a blog post or GitHub repo. This is immediately useful to practitioners
choosing serving stacks and is a legitimate engineering artifact to reference in outreach.

Secondary: prototype a lightweight weight-prefetch scheduler that monitors request patterns and
triggers model pre-loading N seconds before expected traffic. A simple time-series heuristic
(e.g. working-hours model for internal tooling) is enough to demonstrate the concept.

## Evaluation

- Time-to-first-token (TTFT) from cold state across five serving frameworks
- Breakdown by stage using perf counters and container logs
- Comparison of NVMe cache vs. no cache for weight loading
- Statistical confidence intervals across 10 cold-start samples per configuration

---

*Note: This note is based on public documentation and known industry patterns.
Baseten's internal architecture may differ from what is described here.*
