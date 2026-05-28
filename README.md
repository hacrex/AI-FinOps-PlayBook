# AI FinOps Playbook

> Two operating models. Two cost structures. Two engineering worlds.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Markdownlint](https://img.shields.io/badge/markdown-linted-blue.svg)](.github/workflows/lint.yml)

A practical, open-source reference for engineering teams managing AI infrastructure costs — whether you're consuming managed APIs (Azure OpenAI, Vertex AI, Amazon Bedrock) or running self-hosted models on GPU clusters (Llama, Mistral, custom fine-tuned).

---

## Which model am I?

```
Do you manage GPUs, CUDA, or inference servers?
│
├── No  → You are in Managed AI FinOps
│         Cost unit: Tokens
│         Your question: "How do we reduce token spend?"
│         Start here: managed/
│
└── Yes → You are in Self-Hosted AI FinOps
          Cost unit: GPU · hour
          Your question: "How do we maximize GPU economics?"
          Start here: self-hosted/
```

---

## Table of contents

### Managed AI FinOps — 6 techniques to reduce token spend

| # | Technique | Core idea |
|---|-----------|-----------|
| 01 | [Prompt Compression](managed/01-prompt-compression.md) | Smaller prompts = lower input token cost |
| 02 | [Caching](managed/02-caching.md) | Cache hits eliminate billable API calls |
| 03 | [Model Routing](managed/03-model-routing.md) | Route simple tasks to cheaper models |
| 04 | [Context Optimization](managed/04-context-optimization.md) | Lean context windows in agentic workflows |
| 05 | [Rate Limiting](managed/05-rate-limiting.md) | Quotas prevent runaway cost spikes |
| 06 | [Observability](managed/06-observability.md) | Visibility is the prerequisite for everything |

### Self-Hosted AI FinOps — 6 techniques to maximize GPU economics

| # | Technique | Core idea |
|---|-----------|-----------|
| 01 | [Quantization](self-hosted/01-quantization.md) | INT8/INT4 shrinks VRAM, increases throughput |
| 02 | [vLLM](self-hosted/02-vllm.md) | PagedAttention maximizes requests per GPU |
| 03 | [Karpenter](self-hosted/03-karpenter.md) | Scale down idle GPU nodes automatically |
| 04 | [MIG Partitioning](self-hosted/04-mig-partitioning.md) | Split one GPU into up to 7 isolated slices |
| 05 | [Ray / Kubernetes](self-hosted/05-ray-kubernetes.md) | Efficient distributed workload orchestration |
| 06 | [Spot GPU Optimization](self-hosted/06-spot-gpu.md) | 60–80% compute savings on interruptible workloads |

### Cross-cutting reference

| Section | Description |
|---------|-------------|
| [Cost Drivers — Managed](cost-drivers/managed-cost-drivers.md) | What drives token spend |
| [Cost Drivers — Self-Hosted](cost-drivers/self-hosted-cost-drivers.md) | What drives GPU spend |
| [Cost Model Comparison](comparison/cost-model.md) | Token vs GPU·hr side by side |
| [Decision Matrix](comparison/decision-matrix.md) | Choosing your operating model |
| [Managed Tools Stack](tools/managed-stack.md) | Langfuse, OpenTelemetry, Helicone, BigQuery |
| [Self-Hosted Tools Stack](tools/self-hosted-stack.md) | DCGM, Prometheus, Grafana, vLLM, Karpenter, Kubecost |
| [Security & Compliance](security/README.md) | HIPAA, GDPR, PII redaction, audit logging |

---

## Who this is for

- **Cloud & DevOps Engineers** managing AI workloads in production
- **Platform Engineers** building internal AI infrastructure
- **FinOps practitioners** extending traditional cloud cost practices to AI
- **Engineering leads** evaluating managed vs self-hosted AI strategy

---

## How to use this playbook

Each technique doc follows the same structure:

1. **What it is** — plain-language explanation
2. **Why it matters** — the cost problem it solves
3. **How it works** — mechanics and key concepts
4. **Tools** — specific tools and configs
5. **Example** — a worked scenario with numbers
6. **Further reading** — official docs and deep dives

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All experience levels welcome — the `good-first-issue` label is a good starting point.

---

## License

MIT — use freely, attribution appreciated.
