# Decision matrix — Managed vs Self-Hosted AI

> The right entry point matters for your trajectory and team capability.

---

## Quick decision guide

```
Start here → Do you have GPU infrastructure or a team to manage it?
             │
             ├── No  → Start with Managed APIs
             │         Revisit self-hosted when volume justifies the ops cost
             │
             └── Yes → Do you have sustained high request volume (>1M req/month)?
                       │
                       ├── No  → Managed APIs (lower TCO at low volume)
                       │
                       └── Yes → Do you need model customization or data sovereignty?
                                 │
                                 ├── Yes → Self-Hosted
                                 └── No  → Hybrid (managed for realtime, self-hosted for batch)
```

---

## Full decision matrix

Score each factor for your situation. Higher weight = more influence on decision.

| Factor | Weight | Managed APIs | Self-Hosted |
|--------|--------|-------------|-------------|
| Request volume | High | < 1M req/month | > 5M req/month |
| Traffic pattern | High | Variable / spiky | Sustained / predictable |
| GPU ops expertise | High | Not available | Available in-house |
| Latency SLA | Medium | < 500ms p99 | Flexible |
| Model customization | Medium | Off-the-shelf only | Fine-tuning required |
| Data sovereignty | Medium | Provider holds data | Must stay on-prem |
| Team size | Medium | Small (< 5 ML engineers) | Large (> 10 engineers) |
| Time to production | Medium | Days | Weeks to months |
| Budget certainty | Low | Variable (usage-based) | Fixed (capacity-based) |
| Compliance | Low | Provider certifications | Full control needed |

---

## Scenario examples

### Startup building a product feature
**Situation:** 3-person team, 50K requests/month, no GPU infra  
**Recommendation:** **Managed APIs**  
Reasoning: ops overhead of self-hosting would consume more engineering time than the cost savings justify. Start with managed, revisit at 500K+ requests/month.

### Enterprise internal AI platform
**Situation:** 20-person platform team, 10M requests/month, existing Kubernetes infrastructure  
**Recommendation:** **Hybrid**  
Reasoning: self-host high-volume batch workloads and fine-tuned models; use managed APIs for realtime user-facing features where burst capacity and SLA are critical.

### Regulated financial services
**Situation:** PII in prompts, can't send data to external APIs, compliance requirements  
**Recommendation:** **Self-Hosted** (on-premises or private cloud)  
Reasoning: data sovereignty requirements override cost considerations. Must self-host regardless of volume.

### AI-native SaaS product at scale
**Situation:** 100M requests/month, 70% are similar queries, large ops team  
**Recommendation:** **Self-Hosted + Managed fallback**  
Reasoning: at this volume, self-hosted cost per request is dramatically lower. Managed APIs kept as overflow and for model diversity.

### Research team exploring new models
**Situation:** irregular usage, want to test Llama, Mistral, and custom fine-tunes  
**Recommendation:** **Managed for baselines, Self-Hosted for experiments**  
Reasoning: use managed APIs for stable production experiments; self-host for custom model evaluation where you need full control.

---

## Migration triggers

If you start on managed APIs, these signals suggest it's time to evaluate self-hosting:

| Signal | Threshold |
|--------|-----------|
| Monthly API spend | > $10,000/month consistently |
| Request volume | > 5M requests/month |
| Model customization need | Fine-tuning required for quality |
| Latency complaints | Managed API p95 > acceptable SLA |
| Data residency requirement | New compliance mandate |
| Repeated rate limit hits | Sustained throttling affecting UX |

---

## Total cost of ownership (TCO) comparison

Self-hosted has hidden costs that managed APIs don't:

```
Self-Hosted TCO includes:
  GPU infrastructure cost
  + Engineering time (GPU ops, model serving, infra)
  + Observability tooling (Prometheus, Grafana, DCGM)
  + Reliability engineering (HA, failover, DR)
  + Model management (versioning, rollouts, rollbacks)
  + Security (GPU node hardening, network isolation)
  + Opportunity cost (eng time not spent on product)

Rule of thumb:
  Engineering cost of self-hosting = 2–3× the raw GPU cost
  (a $10K/month GPU bill typically requires $20–30K/month in eng time)

Managed APIs TCO:
  API cost
  + Gateway and observability tooling
  + Engineering time (prompt engineering, caching, routing)
  
  Much lower engineering overhead at small-to-medium scale
```

---

## The hybrid architecture

For teams that have outgrown pure managed but aren't ready for full self-hosting:

```
                    ┌─────────────────────────────┐
                    │     API Gateway / Router     │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌─────────────────┐  ┌──────────┐  ┌──────────────────┐
    │  Managed API    │  │  Cache   │  │  Self-Hosted     │
    │  (realtime,     │  │  Layer   │  │  (batch, fine-   │
    │   bursty)       │  │          │  │   tuned models)  │
    └─────────────────┘  └──────────┘  └──────────────────┘
    Azure OpenAI          Redis/        vLLM on GPU cluster
    Vertex AI             GPTCache      Llama / Mistral
    Amazon Bedrock
```

Route by:
- **Latency requirement** → realtime to managed, batch to self-hosted
- **Data sensitivity** → PII to self-hosted, public data to managed
- **Model availability** → frontier models via managed, custom/fine-tuned via self-hosted
- **Cost** → route high-volume repetitive tasks to self-hosted after cache

---

## Further reading

- [Cost Model Comparison](cost-model.md)
- [Managed Cost Drivers](../cost-drivers/managed-cost-drivers.md)
- [Self-Hosted Cost Drivers](../cost-drivers/self-hosted-cost-drivers.md)
- [FinOps Foundation: AI/ML FinOps](https://www.finops.org/wg/ai-ml/)
