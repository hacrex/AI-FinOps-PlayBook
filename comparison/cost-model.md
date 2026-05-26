# Cost model comparison — Managed vs Self-Hosted

> Token vs GPU·hr. Two fundamentally different billing realities.

---

## The core difference

| Dimension | Managed APIs | Self-Hosted |
|-----------|-------------|-------------|
| **Cost unit** | Tokens (input + output) | GPU · hour |
| **Billing model** | Pay per use | Pay for capacity |
| **Idle cost** | Zero | Full GPU cost |
| **Peak cost** | Scales linearly | Capped at provisioned capacity |
| **Optimization target** | Reduce tokens | Maximize GPU utilization |
| **Infra owner** | Provider | Your team |
| **Complexity** | Lower | Very high |
| **Ops team size** | Small | Large |
| **Control** | Limited | Full |
| **Scaling** | Provider handles | You handle |
| **Reliability** | Provider SLA | Your SLA |
| **Customization** | Moderate | Very high |
| **FinOps focus** | API economics | Infra economics |

---

## Token pricing (managed)

Managed API pricing is per 1,000 tokens. Costs vary by model tier:

```
Input tokens:  cost when you send context to the model
Output tokens: cost when the model generates a response
Output tokens are typically 3–5× more expensive per token than input
```

### Example: Claude Sonnet (approximate)
```
Input:  $0.003 / 1K tokens
Output: $0.015 / 1K tokens

A typical request:
  1,000 input tokens + 500 output tokens
  = (1 × $0.003) + (0.5 × $0.015)
  = $0.003 + $0.0075
  = $0.0105 per request

At 1M requests/month: $10,500/month
```

### Token cost drivers
- Prompt length (system prompt + conversation history + retrieved context)
- Output length (generation verbosity)
- Model tier selected
- Number of requests (agentic loops multiply calls)

---

## GPU·hour pricing (self-hosted)

Self-hosted cost is fixed per GPU per hour, regardless of utilization:

```
On-demand GPU pricing (approximate, varies by provider/region):

NVIDIA A10G (24GB):   ~$1.01/hr  (AWS g5.xlarge)
NVIDIA L4 (24GB):     ~$0.80/hr  (GCP)
NVIDIA A100 40GB:     ~$4.00/hr  (cloud)
NVIDIA A100 80GB:     ~$6.00/hr  (cloud)
NVIDIA H100 80GB:     ~$12.00/hr (cloud)

Bare metal (owned):
NVIDIA A100 80GB:     ~$0.80–1.20/hr  (amortized over 3 years)
NVIDIA H100 80GB:     ~$1.50–2.00/hr  (amortized over 3 years)
```

### GPU cost drivers
- Idle GPUs (utilization below 70% is waste)
- Wrong GPU type for workload size
- Poor batching (low throughput = high cost per request)
- VRAM fragmentation (wasted memory = unused capacity)
- No autoscaling (always-on cluster for variable load)
- Non-quantized models (oversized memory footprint)
- Scheduling inefficiency (fragmented workloads)

---

## Break-even analysis

At what scale does self-hosted become cheaper than managed APIs?

```
Assumptions:
  Model: 7B parameter, equivalent to a mid-tier managed model
  Managed: $0.003/1K input + $0.015/1K output tokens
  Self-hosted: 1× A100 80GB on-demand ($6/hr) running vLLM
  Average request: 1,000 input + 500 output tokens = 0.0105/request managed

vLLM throughput on A100: ~50 requests/second = 4,320,000 requests/day

Cost per request (self-hosted):
  $6/hr ÷ 3,600 sec × (1/50 req) = $0.000033/request

Break-even utilization:
  Self-hosted monthly cost at 100% utilization: $6 × 24 × 30 = $4,320/month
  Managed cost for same volume: 4,320,000 × 30 × $0.0105 = $1,360,800/month

Even at 10% GPU utilization:
  Self-hosted: $4,320/month
  Managed: $136,080/month (10% of max volume)

→ Self-hosted wins on throughput-heavy workloads
→ Managed wins on low-volume, variable, or governance-first workloads
```

### When managed is cheaper

- Low volume (< ~100K requests/month)
- Highly variable load with long idle periods
- Team lacks GPU ops expertise
- Rapid prototyping phase
- Regulatory requirements prevent self-hosting

### When self-hosted is cheaper

- High, sustained request volume
- Predictable traffic patterns
- Need for model customization (fine-tuning)
- Data sovereignty requirements
- Existing GPU infrastructure

---

## Hybrid model

Many mature teams run both:

```
Managed APIs     → user-facing realtime features (low latency SLA, variable load)
Self-Hosted      → batch processing, fine-tuned models, high-volume internal pipelines
```

The split is driven by:
- Latency requirements (managed APIs often have higher p99 latency at scale)
- Data sensitivity (self-hosted for PII-heavy workloads)
- Cost at volume (self-hosted for sustained high throughput)
- Customization needs (fine-tuned models require self-hosting)

---

## Further reading

- [Decision Matrix — which model to choose](decision-matrix.md)
- [Managed cost drivers](../cost-drivers/managed-cost-drivers.md)
- [Self-hosted cost drivers](../cost-drivers/self-hosted-cost-drivers.md)
- [FinOps Foundation: Cloud Unit Economics](https://www.finops.org/framework/unit-economics/)
