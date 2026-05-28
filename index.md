---
layout: default
title: AI FinOps Playbook
---

# AI FinOps Playbook

> Two operating models. Two cost structures. Two engineering worlds.

A practical, open-source reference for engineering teams managing AI infrastructure costs — whether you use managed AI APIs or run self-hosted models on GPU clusters.

## Start Here: Which model are you?

```text
Do you manage GPUs, CUDA, or inference servers?
│
├── No  → Managed AI FinOps
│         Cost unit: Tokens
│         Start here: /managed/
│
└── Yes → Self-Hosted AI FinOps
          Cost unit: GPU · hour
          Start here: /self-hosted/
```

## Managed AI FinOps (Token Spend)

- [Prompt Compression](/managed/01-prompt-compression.md)
- [Caching](/managed/02-caching.md)
- [Model Routing](/managed/03-model-routing.md)
- [Context Optimization](/managed/04-context-optimization.md)
- [Rate Limiting](/managed/05-rate-limiting.md)
- [Observability](/managed/06-observability.md)

## Self-Hosted AI FinOps (GPU Economics)

- [Quantization](/self-hosted/01-quantization.md)
- [vLLM](/self-hosted/02-vllm.md)
- [Karpenter](/self-hosted/03-karpenter.md)
- [MIG Partitioning](/self-hosted/04-mig-partitioning.md)
- [Ray / Kubernetes](/self-hosted/05-ray-kubernetes.md)
- [Spot GPU Optimization](/self-hosted/06-spot-gpu.md)

## Core References

- [Cost Drivers](/cost-drivers/)
- [Tools](/tools/)
- [Security](/security/)
- [Labs](/labs/)
- [Case Studies](/case-studies/)
- [Documentation](/docs/)
