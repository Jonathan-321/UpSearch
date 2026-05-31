# Trace-Driven Simulator for Speculative Decoding Under Shifting Traffic

Company: Together AI
Prepared by: Jonathan Muhire
Date: 2026-05-30

## Technical Thesis

Together AI frames production inference as a systems problem across latency, throughput, cost, concurrency, and workload shape. Agentic systems make this harder because one user-facing action can require several model calls. Small latency inefficiencies compound across a workflow, so optimization has to be evaluated at both the request level and the multi-call workflow level.

I would build a trace-driven simulator for speculative decoding under shifting traffic. The goal is not to implement a production speculative decoding engine or claim kernel expertise. The goal is to build a rigorous measurement artifact that shows when a draft path helps, when it regresses, and what telemetry is needed before a production team should trust it.

## Problem

Speculative decoding can reduce latency when a faster draft path agrees often enough with the target model. But the benefit depends on workload shape. Acceptance rates can shift across prompt length, output length, domain, traffic segment, or model update. A global average can hide segment-level regressions: speculative decoding may improve aggregate latency while hurting a specific class of requests or multi-step agent workflows.

The practical question is how to reason about acceptance rate, latency impact, and rollback criteria before changing production serving behavior. A trace-based simulator can make that question concrete. It can show what happens when traffic buckets change, when a draft model becomes stale, or when agentic workflows multiply a small per-call regression.

## Proposed Build

I would build a simulator that takes synthetic or replayed request traces and compares baseline decoding against speculative decoding assumptions.

Core components:

1. Request schema with prompt length, expected output length, route, workflow step, traffic bucket, and latency target.
2. Configurable target/draft agreement rate by bucket.
3. Acceptance-rate drift over time.
4. Latency model for baseline decoding and speculative decoding.
5. Multi-call workflow model for agentic tasks.
6. Segment-level regression detector.
7. Promotion or rollback rule based on observed trace outcomes.

The simulator would make assumptions explicit. It would not need real production traces to be useful initially. Synthetic traces can still show the structure of the evaluation problem and identify which measurements would matter most in a real serving system.

## Execution Plan

Week 1 would implement synthetic request traces, configurable acceptance rates, baseline vs speculative latency estimates, and summary reports across traffic buckets. Week 2 would add drift scenarios, multi-call agent workflows, segment-level regression detection, and promotion rules. The final report would compare three cases: baseline decoding, speculative decoding under stable acceptance, and speculative decoding under shifting acceptance.

Stretch work would replay a small public or generated trace and connect the simulator to an open benchmark format. A README would document assumptions, limitations, and which parts would need real platform data.

## Success Criteria

The simulator should show when speculative decoding improves latency and when it becomes harmful. It should separate aggregate wins from segment-level regressions. It should show the compounding effect of per-call latency in agentic workflows. It should produce a reproducible promotion or rollback decision from logged traces. A Together AI engineer should be able to critique the assumptions and identify what real serving telemetry would make the simulator more accurate.

## Relevant Background

CFN evaluation work maps to controlled comparisons, artifact tracking, and stability analysis. PolyQuant maps to traceability, revision history, and decision reports. The honest position is that I am learning inference optimization by building a rigorous measurement artifact first, then using it to ask better technical questions.

## Outreach Ask

I would ask whether a trace-driven simulator is a credible way to learn inference optimization before going deeper into kernels, and which assumptions about speculative decoding evaluation are most likely to be wrong.

Sources: https://www.together.ai/blog/foundational-research-powering-efficient-inference-at-scale ; https://www.together.ai/inference ; https://www.together.ai/about-us ; https://www.together.ai/careers
