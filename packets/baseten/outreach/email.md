Subject: Cold start benchmark for ML serving frameworks

Hi [Name],

I've been reading through Baseten's engineering blog and the Truss architecture and noticed you haven't published a systematic breakdown of cold start latency across different model sizes and serving stacks.

I'm a CS student at UConn with coursework in operating systems and ML inference. I'm working through a benchmark comparing cold start TTFT across vLLM, Ollama, and TGI for 7B to 34B parameter models, with stage-level timing broken down by container startup, weight load, and first-token generation.

The goal is a reproducible methodology and a public dataset that practitioners can reference when choosing a stack. I think it would be directly useful to the kind of teams using Baseten.

Would you be open to a 15-minute call? I mostly want to understand what you see in production that a benchmark running on consumer hardware would miss.

Luis
UConn CS
