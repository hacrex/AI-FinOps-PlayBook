# 02 — Caching

> Every cache hit is a billable API call eliminated.

**Category:** Managed AI FinOps · Technique 02 of 06  
**Tags:** `semantic-cache` `latency` `cost-reduction`

---

## What it is

Caching stores the responses to AI API requests so that identical or similar future requests are served from the cache instead of making a new billable call. The simplest form is exact-match caching; the more powerful form is semantic caching, which matches near-duplicate queries even when phrased differently.

---

## Why it matters

In most production AI workloads, a significant fraction of requests are repetitive:
- FAQ-style chatbots receive the same questions daily
- Agent workflows re-process the same context on each step
- Retrieval-augmented pipelines retrieve and summarize the same documents repeatedly

Each of these is a billable call that could be a cache hit. Depending on workload type, cache hit rates of 20–60% are achievable, translating directly to cost reduction plus latency improvement.

---

## How it works

### Exact-match caching

The simplest approach: hash the full prompt string and store the response. If the same hash arrives again, return the cached response.

```python
import hashlib
import json

def cache_key(messages: list, model: str) -> str:
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

Works well for:
- Templated queries with fixed structures
- Repeated system-level operations (classification, extraction)
- High-traffic FAQ responses

### Semantic caching

Semantic caching goes further: embed the incoming query and find the nearest stored query in vector space. If the similarity score exceeds a threshold, return the cached response without hitting the API.

```
User query → embed → vector search → similarity > 0.95? → return cached
                                    → similarity < 0.95? → call API, store result
```

This handles phrasing variations:
- "What are your business hours?" ≈ "When are you open?"
- "How do I reset my password?" ≈ "I forgot my password, what do I do?"

### Prompt caching (provider-side)

Some providers offer native prompt caching where a fixed prefix (like a long system prompt) is cached server-side and not re-billed on subsequent calls:

| Provider | Feature | Discount |
|----------|---------|----------|
| Anthropic | Prompt caching | ~90% off cached input tokens |
| OpenAI | Prompt caching | ~50% off cached input tokens |
| Google | Context caching | Variable |

This is the highest-ROI caching technique when you have long, stable system prompts.

---

## Tools

| Tool | Use |
|------|-----|
| [GPTCache](https://github.com/zilliztech/GPTCache) | Open-source semantic cache for LLM APIs |
| [Redis](https://redis.io) | Exact-match cache backend; also supports vector search via Redis Stack |
| [Langfuse](https://langfuse.com) | Track cache hit rates and cost savings per prompt |
| [Helicone](https://helicone.ai) | Gateway-level caching with built-in analytics |
| Provider-native | Anthropic prompt caching, OpenAI prompt caching — zero infrastructure needed |

---

## Example

**Scenario:** A B2B SaaS assistant handles 200,000 API calls per day. Analysis shows 35% of queries are semantically near-duplicate (phrasing of the same intent). Average prompt is 800 tokens, average response is 400 tokens.

```
Without caching:
200,000 calls/day × (800 + 400) tokens = 240,000,000 tokens/day
At $0.003/1K tokens = $720/day = $21,600/month

With 35% semantic cache hit rate:
130,000 calls reach the API
130,000 × 1,200 tokens = 156,000,000 tokens/day
= $468/day = $14,040/month

Monthly saving: $7,560
Plus latency improvement: cached responses serve in <5ms vs 800ms average API latency
```

---

## Implementation checklist

- [ ] Identify which request types are most repetitive (use Langfuse or logs)
- [ ] Implement exact-match caching first — fast wins, zero ML overhead
- [ ] Set appropriate TTLs (time-to-live) — don't cache time-sensitive responses
- [ ] Add semantic caching for FAQ and conversational workloads
- [ ] Enable provider-side prompt caching for long static system prompts
- [ ] Monitor hit rate and adjust similarity threshold to balance quality vs savings

---

## Further reading

- [GPTCache documentation](https://gptcache.readthedocs.io)
- [Anthropic prompt caching guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI prompt caching](https://platform.openai.com/docs/guides/prompt-caching)
- [Semantic caching for LLMs — Zilliz blog](https://zilliz.com/blog/semantic-cache)

---

**Previous:** [01 — Prompt Compression](01-prompt-compression.md)  
**Next:** [03 — Model Routing](03-model-routing.md)
