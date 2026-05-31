# Adjacent proof bank

Last updated: 2026-05-30

Use this as a menu of truthful proof points for outreach. Pick one proof per message based on the person and problem. Do not overload a cold email with multiple projects.

## Best proof points for Baseten

| Rank | Proof point | Why it fits Baseten | Best use |
| --- | --- | --- | --- |
| 1 | PolyQuant Forecast Engine | Strongest match for provenance, revision history, bounded agent coordination, supervision, calibration, and auditable updates. It maps directly to "new checkpoint as hypothesis, old checkpoint as control." | Baseten continual-learning inference, adapter routing, FDE, Applied AI Inference |
| 2 | CFN Biomedical Eval | Strong match for leakage-safe evaluation, locked protocols, identical folds, equal tuning budgets, artifact tracking, calibration, and stability reporting. It shows evaluation discipline without claiming production model-serving experience. | Baseten post-training, evals, model quality, promotion gates |
| 3 | SFN scRNA Study | Strong match for honest benchmark framing, donor-aware cross-validation, robustness checks, structural diagnostics, and careful claims. | Research-adjacent outreach, technical notes, eval-heavy roles |
| 4 | UMI Annotation / Modal Pipeline | Strong match for data pipelines, GPU/cloud execution, VLM-generated annotations, object detection, validation, and HuggingFace dataset output. Use only when robotics/data pipeline evidence is the best fit. | Robotics AI, data infra, Modal/cloud pipeline, multimodal data |
| 5 | Evident / Flint language projects | Good proof of compiler/interpreter fundamentals, parsing, evaluation, and technical communication. Lower priority for Baseten unless targeting developer tooling. | Developer tools, language tooling, systems foundations |

## Project details

### PolyQuant Forecast Engine

Source:

- Local repo: `/Users/jonathanmuhire/poly`
- Public repo: https://github.com/Jonathan-321/polyquant-live.git

What it demonstrates:

- Evidence collection and signal extraction from FOMC, CPI, payrolls, and custom sources.
- Bayesian probability updates with a particle filter in logit space.
- Forecast revision history and rationale generation.
- Supervisor validation for freshness, drift, confidence, and escalation.
- Bounded agent coordination with terminal ACK semantics.
- Calibration tracking with Brier score and accuracy buckets.
- FastAPI service, SQLite persistence, health endpoints, and observability endpoints.

Baseten translation:

```text
My closest adjacent work is PolyQuant, a supervised forecasting engine where every update preserves evidence, revision history, calibration, and an audit trail. The model-serving problem feels similar: a new adapter is a hypothesis, not a silent replacement, so routing and promotion need provenance.
```

Short version for email:

```text
My closest adjacent project is PolyQuant, a supervised forecasting engine with revision history, calibration, and bounded agent coordination. It made me think about model updates as auditable hypotheses rather than silent replacements.
```

### CFN Biomedical Eval

Source:

- Local repo: `/Users/jonathanmuhire/CFN/cfn-biomed-eval`
- Public repo: https://github.com/Jonathan-321/cfn-biomed-eval.git

What it demonstrates:

- Protocol-locked comparison of CFN vs XGBoost, MLP, and logistic regression.
- Identical folds, train-only preprocessing, equal tuning budgets, and artifact tracking.
- Guardrail checks before experiments.
- Calibration, threshold, bootstrap, and structural stability reports.
- Reproducibility-first benchmark workflow.

Baseten translation:

```text
My closest adjacent work is a leakage-safe biomedical evaluation repo where folds, preprocessing, tuning budgets, manifests, calibration, and stability reports are locked before claims are made. That maps well to promotion gates for changing model variants.
```

Short version for email:

```text
My closest adjacent work is a leakage-safe biomedical evaluation repo with locked folds, train-only preprocessing, artifact tracking, calibration, and stability reports. It maps well to model promotion gates.
```

### SFN scRNA Study

Source:

- Local repo: `/Users/jonathanmuhire/CFN/sfn-scrna-study`
- Public repo: https://github.com/Jonathan-321/sfn-scrna-study.git

What it demonstrates:

- Donor-aware single-cell RNA benchmarking.
- Repeated 5-fold donor cross-validation and leave-one-donor-out robustness checks.
- Representation comparison across donor-global and compartment-aware views.
- Structural diagnostics, biological annotation, and honest claim boundaries.

Best outreach sentence:

```text
I also have evaluation work in donor-aware single-cell benchmarking, where the hard part was not only getting a model to work but making the claim honest under robustness and stability checks.
```

### UMI Annotation / Modal Pipeline

Source:

- Local repo: `/Users/jonathanmuhire/umi-annotation`
- Public repo: https://github.com/Neotix-Robotics/umi-annotation.git

What it demonstrates:

- Modal serverless pipeline for robot demonstration data.
- Zarr loading, VLM scene descriptions, object vocabulary extraction, GroundingDINO boxes, 3D-to-camera gripper projection, motion primitives, chain-of-thought annotations, HuggingFace dataset output, validation, and analysis videos.
- Parallel cloud processing with GPU and CPU containers.

Use carefully:

- This is still useful, but it should not be the default Baseten proof unless the target is robotics, multimodal data, or cloud data pipelines.

Best outreach sentence:

```text
I have also worked around cloud pipelines for robot demonstration data, including validation, multimodal annotation, and dataset generation. I would use that proof only where data pipelines or robotics are the right angle.
```

## How to choose proof for an outreach draft

| Target type | Use this proof first |
| --- | --- |
| Inference systems / model serving | PolyQuant |
| Post-training / evals / model promotion | CFN Biomedical Eval |
| Research or benchmarking | SFN scRNA Study |
| Robotics / embodied AI / VLA | UMI Annotation or robotics/VLA |
| Developer tooling / languages | Evident, Flint, or OpenCode Swarm only if your contribution is confirmed |

## Guardrails

- Do not claim production LoRA serving experience.
- Do not claim ownership of repos where your contribution is unclear.
- Prefer "my closest adjacent project" over "I built the same thing."
- Use one proof point per email.
- Keep the proof sentence under two lines in the outreach body.
