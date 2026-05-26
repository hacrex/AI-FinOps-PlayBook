# Managed AI FinOps — Tools stack

> The managed API observability stack focuses on token-level visibility: tracing requests, attributing cost, and enforcing governance at the API boundary.

---

## Stack overview

```
┌─────────────────────────────────────────────────────┐
│                  Your Applications                  │
└──────────────────────────┬──────────────────────────┘
                           │ all AI API calls routed through
                           ▼
┌─────────────────────────────────────────────────────┐
│              API Gateway (Helicone / Portkey)        │
│  rate limiting · caching · routing · key management │
└──────────────────────────┬──────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌─────────────────────┐     ┌─────────────────────────┐
│   Managed AI APIs   │     │  Observability Platform  │
│                     │     │  (Langfuse)              │
│  Azure OpenAI       │     │                          │
│  Vertex AI          │     │  traces · costs · evals  │
│  Amazon Bedrock     │     └────────────┬────────────┘
│  Anthropic API      │                  │
└─────────────────────┘                  ▼
                           ┌─────────────────────────┐
                           │  Cost Analytics          │
                           │  (BigQuery / FinOps)     │
                           │                          │
                           │  chargeback · forecasts  │
                           └─────────────────────────┘
```

---

## Tool reference

### Langfuse — LLM-native observability

**Role:** Trace every AI API request with token counts, cost, latency, model, user, and session metadata.

**Why it's the foundation:** Most other tools see requests as HTTP calls. Langfuse understands LLM concepts — prompts, completions, token budgets, evaluation scores, and prompt versions.

**Key features:**
- Token and cost tracking per request, user, and session
- Prompt version management — compare cost and quality across versions
- Evaluation framework — score outputs for quality monitoring
- Dashboard for chargeback and showback
- Open-source and self-hostable (or cloud-hosted)

**Quick integration:**
```python
pip install langfuse

from langfuse.decorators import observe

@observe()
def call_llm(prompt: str, user_id: str) -> str:
    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

**Links:**
- [langfuse.com](https://langfuse.com)
- [GitHub](https://github.com/langfuse/langfuse)
- [Documentation](https://langfuse.com/docs)

---

### OpenTelemetry — Infrastructure tracing

**Role:** Standard observability protocol for distributed tracing across services. Pairs with Langfuse to give full-stack tracing from user request to LLM response.

**Why you need it:** Langfuse covers LLM-layer traces. OpenTelemetry covers the application and infrastructure layers — latency between services, queue times, database calls that precede or follow LLM calls.

**Key features:**
- Vendor-neutral standard (works with Jaeger, Tempo, Honeycomb, Datadog)
- Auto-instrumentation for Python, Node.js, Go, Java
- Connects LLM traces to broader application traces

**Integration with Langfuse:**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from langfuse.opentelemetry import LangfuseSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    SimpleSpanProcessor(LangfuseSpanExporter())
)
trace.set_tracer_provider(provider)
```

**Links:**
- [opentelemetry.io](https://opentelemetry.io)
- [Python instrumentation](https://opentelemetry.io/docs/instrumentation/python/)

---

### Helicone — Gateway-level analytics

**Role:** Zero-code proxy gateway that sits between your application and the AI provider. Captures every request without code changes.

**Why it's useful:** Fastest path to observability — change one line (your API base URL) and immediately get dashboards, rate limiting, and caching.

**Key features:**
- Proxy-based: `base_url="https://oai.helicone.ai/v1"` — no SDK changes
- Per-user and per-app rate limiting
- Response caching with cache hit analytics
- Cost attribution by custom properties
- Supports OpenAI, Anthropic, Azure, and others

**Quick setup:**
```python
from openai import OpenAI

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://oai.helicone.ai/v1",
    default_headers={
        "Helicone-Auth": f"Bearer {HELICONE_API_KEY}",
        "Helicone-User-Id": user_id,
        "Helicone-Property-Team": team_name,
    }
)
```

**Links:**
- [helicone.ai](https://helicone.ai)
- [Documentation](https://docs.helicone.ai)

---

### BigQuery — Cost analytics at scale

**Role:** Data warehouse for AI spend analytics. Export Langfuse trace data to BigQuery for joins with business metrics, finance reporting, and long-term trend analysis.

**Why you need it:** Langfuse dashboards are great for engineering. Finance teams need BigQuery (or equivalent) where AI cost can be joined with revenue, user counts, and other business data.

**Common queries:**
```sql
-- Cost per team per day
SELECT
  DATE(created_at) as date,
  JSON_VALUE(metadata, '$.team') as team,
  SUM(total_cost_usd) as daily_cost_usd,
  SUM(prompt_tokens + completion_tokens) as total_tokens
FROM langfuse_traces
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;

-- Most expensive prompt versions
SELECT
  prompt_name,
  prompt_version,
  COUNT(*) as calls,
  AVG(total_cost_usd) as avg_cost_per_call,
  SUM(total_cost_usd) as total_cost_usd
FROM langfuse_traces
WHERE created_at > CURRENT_DATE - 30
GROUP BY 1, 2
ORDER BY 5 DESC;
```

**Links:**
- [Google BigQuery](https://cloud.google.com/bigquery)
- [Langfuse → BigQuery export](https://langfuse.com/docs/analytics)

---

### LiteLLM — Unified API + routing

**Role:** Open-source LLM proxy that normalizes API calls across providers (OpenAI, Anthropic, Vertex, Bedrock, Azure) and adds routing, fallbacks, and budget management.

**Why it's useful:** If you use multiple providers, LiteLLM gives a single API surface and handles provider-specific differences. Also enables model routing rules and per-user budget enforcement.

**Key features:**
- One API format for 100+ models across all major providers
- Model routing rules (route by cost, latency, or custom logic)
- Budget management per user and team
- Fallback chains (if GPT-4o fails, try Claude Sonnet)
- Built-in Langfuse integration

**Links:**
- [litellm.ai](https://litellm.ai)
- [GitHub](https://github.com/BerriAI/litellm)
- [Routing documentation](https://docs.litellm.ai/docs/routing)

---

## Tool selection guide

| Need | Primary tool | Alternative |
|------|-------------|------------|
| Per-request cost tracking | Langfuse | Helicone |
| Zero-code observability | Helicone | Portkey |
| Distributed tracing | OpenTelemetry | Datadog APM |
| Finance reporting | BigQuery | Snowflake, Redshift |
| Multi-provider routing | LiteLLM | Portkey |
| Rate limiting + quotas | Helicone / LiteLLM | AWS API Gateway |
| Prompt management | Langfuse | PromptLayer |

---

## Further reading

- [Managed AI FinOps — 6 techniques](../managed/)
- [Self-Hosted tools stack](self-hosted-stack.md)
- [Langfuse vs Helicone comparison](https://langfuse.com/blog/2024-04-langfuse-vs-helicone)
