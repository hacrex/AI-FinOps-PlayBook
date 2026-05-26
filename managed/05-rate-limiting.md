# 05 — Rate limiting

> Rate limiting is your circuit breaker against runaway AI spend.

**Category:** Managed AI FinOps · Technique 05 of 06  
**Tags:** `api-gateway` `quotas` `governance`

---

## What it is

Rate limiting applies quotas to AI API usage at the team, application, or individual user level — enforced at the API gateway layer — so that a single misconfigured workflow, buggy agent loop, or unexpected traffic spike cannot generate unbounded cost.

---

## Why it matters

Managed AI APIs have no built-in spend caps by default. A single engineering mistake can generate thousands of unexpected API calls within minutes:

- A misconfigured agent retry loop with no backoff
- A while loop that calls the API until a condition is met, but the condition never triggers
- A fan-out workflow that parallelizes 1,000 sub-tasks simultaneously
- A prompt injection attack that triggers repeated expensive calls

Without a circuit breaker, you discover these events on your monthly invoice.

In multi-tenant enterprise deployments, rate limiting also enforces fairness — one team's runaway workflow shouldn't consume the entire organization's quota and degrade service for everyone else.

---

## How it works

### Quota dimensions

Apply limits across multiple dimensions:

| Dimension | Example limit | Purpose |
|-----------|--------------|---------|
| Per user | 100K tokens/day | Prevent individual abuse |
| Per team | 5M tokens/day | Budget enforcement per department |
| Per application | 2M tokens/hour | Isolate services from each other |
| Per model tier | 500K premium tokens/day | Protect expensive model budget |
| Global | 50M tokens/day | Hard organizational ceiling |

### Enforcement via API gateway

Route all AI API calls through a centralized gateway that enforces quotas before the request reaches the provider:

```
Application → AI Gateway (quota check) → Provider API
                     ↓
              Over quota? → Return 429 with retry-after header
              Under quota? → Decrement counter, forward request
```

Gateways also provide:
- Real-time spend visibility across all consumers
- Centralized API key management (applications never hold provider keys directly)
- Automatic fallback to cheaper models when quotas are approached
- Alert thresholds (e.g. notify team lead at 80% of daily quota)

### Quota enforcement patterns

**Hard limits** — reject requests when quota is exceeded:
```python
if token_count_today[team_id] + estimated_tokens > daily_limit[team_id]:
    raise QuotaExceededException(f"Team {team_id} has reached daily token limit")
```

**Soft limits with degradation** — route to cheaper model when approaching limit:
```python
quota_used_pct = token_count_today[team_id] / daily_limit[team_id]
if quota_used_pct > 0.8:
    model = "claude-haiku-4-5"  # downgrade automatically
else:
    model = requested_model
```

**Budget-based limits** — cap by cost rather than tokens (handles model tier differences):
```python
spend_today[team_id] += estimated_cost(tokens, model)
if spend_today[team_id] > daily_budget[team_id]:
    raise BudgetExceededException()
```

### Agent loop protection

For agentic workloads specifically, add a per-session turn limit:

```python
MAX_AGENT_TURNS = 25  # hard stop — prevents infinite loops

if session.turn_count >= MAX_AGENT_TURNS:
    return {"status": "max_turns_reached", "summary": session.partial_result}
```

---

## Tools

| Tool | Use |
|------|-----|
| [Helicone](https://helicone.ai) | Gateway with per-user/per-app rate limiting, spend alerts |
| [Portkey](https://portkey.ai) | Multi-tenant quota management, budget-based limits |
| [AWS API Gateway](https://aws.amazon.com/api-gateway/) | Usage plans and quotas for Bedrock-routed traffic |
| [Azure API Management](https://azure.microsoft.com/en-us/products/api-management) | Rate limiting for Azure OpenAI deployments |
| [LiteLLM Proxy](https://docs.litellm.ai/docs/proxy/rate_limit) | Open-source proxy with budget management |
| [Langfuse](https://langfuse.com) | Usage tracking and alerting (pair with gateway enforcement) |

---

## Example

**Scenario:** A startup runs an AI-powered document analysis platform. One evening, a developer pushes a bug that causes the analysis pipeline to retry indefinitely on failed extractions. No rate limit is in place.

```
Without rate limiting:
Bug runs for 6 hours overnight
1 document → retries every 2 seconds → 10,800 calls
Each call: 4,000 tokens (input) + 500 tokens (output)
10,800 × 4,500 tokens × $0.003/1K = $145.80 from one bug

With per-application rate limit of 10,000 calls/hour:
Bug triggers rate limit after 10,000 calls in first hour
Maximum damage: $13.50
Alert fires at 80% threshold → on-call notified within minutes
```

A single rate limit saves $132 and prevents a customer-visible outage from cascading resource exhaustion.

---

## Implementation checklist

- [ ] Route all AI API traffic through a centralized gateway (never direct provider calls from applications)
- [ ] Define quotas per team, application, and model tier
- [ ] Set alert thresholds at 70% and 90% of each quota
- [ ] Add per-session turn limits to all agentic workflows
- [ ] Implement graceful degradation (model downgrade) as quota approaches
- [ ] Review and adjust quotas monthly based on usage patterns

---

## Further reading

- [Helicone rate limiting documentation](https://docs.helicone.ai/features/advanced-usage/custom-rate-limits)
- [LiteLLM budget management](https://docs.litellm.ai/docs/proxy/users)
- [Azure OpenAI quota management](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/quota)
- [AWS Bedrock service quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html)

---

**Previous:** [04 — Context Optimization](04-context-optimization.md)  
**Next:** [06 — Observability](06-observability.md)
