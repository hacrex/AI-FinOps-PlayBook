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

- [Prompt Compression]({{ '/managed/01-prompt-compression/' | relative_url }})
- [Caching]({{ '/managed/02-caching/' | relative_url }})
- [Model Routing]({{ '/managed/03-model-routing/' | relative_url }})
- [Context Optimization]({{ '/managed/04-context-optimization/' | relative_url }})
- [Rate Limiting]({{ '/managed/05-rate-limiting/' | relative_url }})
- [Observability]({{ '/managed/06-observability/' | relative_url }})

## Self-Hosted AI FinOps (GPU Economics)

- [Quantization]({{ '/self-hosted/01-quantization/' | relative_url }})
- [vLLM]({{ '/self-hosted/02-vllm/' | relative_url }})
- [Karpenter]({{ '/self-hosted/03-karpenter/' | relative_url }})
- [MIG Partitioning]({{ '/self-hosted/04-mig-partitioning/' | relative_url }})
- [Ray / Kubernetes]({{ '/self-hosted/05-ray-kubernetes/' | relative_url }})
- [Spot GPU Optimization]({{ '/self-hosted/06-spot-gpu/' | relative_url }})

## Core References

- [Cost Drivers]({{ '/cost-drivers/' | relative_url }})
- [Tools]({{ '/tools/' | relative_url }})
- [Security]({{ '/security/' | relative_url }})
- [Labs]({{ '/labs/' | relative_url }})
- [Case Studies]({{ '/case-studies/' | relative_url }})
- [Documentation]({{ '/docs/' | relative_url }})
- [README (full playbook)]({{ '/README.md' | relative_url }})

---
