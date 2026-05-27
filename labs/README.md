# Labs — Hands-on AI FinOps exercises

> Apply the techniques from the playbook in real environments. Each lab includes setup, commands, configs, and validation steps.

---

## Managed API labs

| Lab | Technique | What you build | Time |
|-----|-----------|---------------|------|
| [M-01: Token audit + prompt compression](managed/m01-token-audit.md) | Prompt Compression | Langfuse dashboard, before/after token comparison | 45 min |
| [M-02: Semantic cache with GPTCache + Redis](managed/m02-semantic-cache.md) | Caching | Semantic cache layer in front of any LLM API | 60 min |
| [M-03: Model router with LiteLLM](managed/m03-model-router.md) | Model Routing | Cost-aware router: cheap model first, escalate on failure | 60 min |

## Self-hosted GPU labs

| Lab | Technique | What you build | Time |
|-----|-----------|---------------|------|
| [S-01: vLLM deployment + GPU metrics](self-hosted/s01-vllm-prometheus.md) | vLLM + Observability | vLLM serving Llama with Prometheus + Grafana dashboard | 90 min |
| [S-02: Quantization benchmark](self-hosted/s02-quantization-bench.md) | Quantization | FP16 vs INT8 vs INT4 quality and throughput comparison | 60 min |
| [S-03: Karpenter GPU autoscaler on EKS](self-hosted/s03-karpenter-gpu.md) | Karpenter | GPU NodePool with spot-first + consolidation on EKS | 90 min |

---

## Prerequisites

### Managed labs
- Python 3.10+
- An API key for at least one provider (Anthropic, OpenAI, or Azure OpenAI)
- Docker (for Redis in M-02)
- A free [Langfuse Cloud](https://cloud.langfuse.com) account or self-hosted Langfuse

### Self-hosted labs
- A machine or cloud instance with at least one NVIDIA GPU
- CUDA 12.x drivers installed
- Docker + NVIDIA Container Toolkit
- kubectl + Helm (for S-01, S-03)
- AWS account with EKS access (for S-03)

---

## Lab conventions

Each lab follows this structure:

```
## Objective       — what you will have built by the end
## Prerequisites   — what you need before starting
## Setup           — environment and dependency installation
## Step-by-step    — numbered steps with commands and expected output
## Validate        — how to confirm it's working correctly
## Cost impact     — estimated savings from this technique
## Teardown        — how to clean up resources
## Next steps      — where to go from here
```

Expected output is shown after each command so you know what success looks like.

---

## Running costs

Labs are designed to minimize cloud spend:

- **Managed labs:** API costs are minimal (< $1 total per lab at typical token prices)
- **S-01 (vLLM):** Can run on a single T4 or A10G ($0.35–$1.01/hr on cloud, or free on your own GPU)
- **S-02 (Quantization):** Same single GPU as S-01
- **S-03 (Karpenter):** Requires EKS cluster. Estimated cost: $2–5 for the lab duration if torn down promptly

Always run `teardown` steps when done.
