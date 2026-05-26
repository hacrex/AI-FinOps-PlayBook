# 06 — Observability

> You cannot optimize what you cannot see.

**Category:** Managed AI FinOps · Technique 06 of 06  
**Tags:** `langfuse` `opentelemetry` `helicone` `bigquery`

---

## What it is

AI observability for managed APIs is the practice of tracing every request end-to-end — measuring cost per call, tokens in, tokens out, latency, model used, and which application or user triggered it — then making that data available for analysis, alerting, and chargeback.

Observability is not one technique among equals: it is the prerequisite for every other optimization in this playbook. Without visibility into where tokens are being spent, all other techniques are guesswork.

---

## Why it matters

Without observability you cannot answer:
- Which team or application is responsible for 40% of our token spend?
- Which prompt version is more expensive — v2 or v3?
- What is the average cost per user session in our chatbot?
- Did our context optimization change last week actually reduce spend?
- Which agent workflows are generating the longest context windows?

With observability, these questions answer themselves through dashboards.

---

## How it works

### The four layers of managed AI observability

```
Layer 1 — Request tracing     (Langfuse / OpenTelemetry)
          Track every API call: tokens, model, latency, cost, user/session ID

Layer 2 — Gateway analytics   (Helicone / Portkey)
          Aggregate traffic patterns, rate limit events, cache hit rates

Layer 3 — Cost analytics      (BigQuery / FinOps tooling)
          Join AI spend with business metrics: cost per user, cost per feature

Layer 4 — Alerting            (PagerDuty / Grafana alerts)
          Fire when spend rate, error rate, or latency crosses thresholds
```

### What to instrument on every request

At minimum, attach these attributes to every AI API call:

```python
langfuse.trace(
    name="document-analysis",
    user_id=user.id,
    session_id=session.id,
    metadata={
        "team": team.name,
        "feature": "contract-review",
        "document_type": doc.type,
        "model": model_name,
    }
)
```

This enables slicing cost by user, team, feature, model, and document type simultaneously.

### Chargeback and showback

**Showback:** Show each team their AI spend without billing them internally. Creates awareness without friction.

**Chargeback:** Allocate AI costs back to cost centers based on actual consumption. Requires tagging every request with a cost center ID.

```python
# Tag every request with cost allocation metadata
headers = {
    "X-Cost-Center": team.cost_center_id,
    "X-Feature": feature_name,
    "X-Environment": env,  # prod / staging / dev
}
```

Export to BigQuery or your FinOps platform weekly for finance reconciliation.

### Key metrics to track

| Metric | Why it matters |
|--------|---------------|
| Tokens in per request | Input cost driver |
| Tokens out per request | Output cost driver |
| Cost per session | Business-level unit economics |
| Cost per user | Per-seat economics |
| Cache hit rate | Effectiveness of caching |
| Model distribution | Are expensive models used appropriately? |
| p50/p95/p99 latency | User experience |
| Error rate | Retries drive unexpected cost |
| Context window size trend | Early warning for context bloat |

### Dashboard structure

Build three dashboards:

1. **Engineering dashboard** — real-time: request rate, error rate, latency, top spenders by team
2. **FinOps dashboard** — daily/weekly: cost trends, model distribution, cost per feature, forecast vs actual
3. **Leadership dashboard** — monthly: total AI spend, cost per active user, ROI by feature

---

## Tools

| Tool | Role | Notes |
|------|------|-------|
| [Langfuse](https://langfuse.com) | LLM-native observability | Open-source, self-hostable; traces requests with token-level detail |
| [OpenTelemetry](https://opentelemetry.io) | Infrastructure tracing | Standard protocol; pair with Langfuse for full-stack tracing |
| [Helicone](https://helicone.ai) | Gateway-level analytics | Zero-code integration; proxy-based; dashboard included |
| [BigQuery](https://cloud.google.com/bigquery) | Cost analytics at scale | Export Langfuse data; join with other business metrics |
| [Grafana](https://grafana.com) | Dashboards and alerting | Query Prometheus or BigQuery; set spend rate alerts |

### Langfuse quickstart

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def analyze_document(doc_text: str, user_id: str) -> str:
    langfuse_context.update_current_trace(
        user_id=user_id,
        tags=["contract-review", "prod"],
    )
    
    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": doc_text}]
    )
    return response.content[0].text
```

Langfuse automatically captures token counts, cost, and latency from the API response.

---

## Example

**Scenario:** A team enables Langfuse across their AI platform and runs a two-week analysis.

Findings:
- Feature A (document summarization) accounts for 58% of total token spend but only 20% of user sessions — prompts are 5x longer than Feature B
- 12% of calls are retries on transient errors — each retry doubles token spend for that request
- The staging environment is making 15% as many API calls as production — not guarded by environment checks

Actions taken:
- Applied prompt compression to Feature A → 35% token reduction → $2,100/month saving
- Added exponential backoff on retries → 60% retry reduction → $900/month saving
- Added `if env != "prod": use_mock_response()` guard → $600/month saving

Total monthly saving from two weeks of observability: $3,600 — with no changes to model quality.

---

## Implementation checklist

- [ ] Deploy Langfuse (cloud or self-hosted) and instrument all AI API calls
- [ ] Attach user_id, team, feature, and environment metadata to every trace
- [ ] Set up cost alerts for daily spend rate (Grafana or Langfuse built-in)
- [ ] Build a weekly FinOps report exported to BigQuery or equivalent
- [ ] Enable chargeback tagging for multi-team environments
- [ ] Review top-10 spenders weekly — at least one optimization action per week

---

## Further reading

- [Langfuse documentation](https://langfuse.com/docs)
- [OpenTelemetry for LLM applications](https://opentelemetry.io/docs/instrumentation/python/)
- [Helicone observability guide](https://docs.helicone.ai)
- [FinOps Foundation: AI/ML cost management](https://www.finops.org/wg/ai-ml/)

---

**Previous:** [05 — Rate Limiting](05-rate-limiting.md)  
**Back to:** [README](../README.md)
