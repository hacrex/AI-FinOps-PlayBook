# Cost drivers — Managed AI APIs

> Understanding what drives your token bill is the first step to reducing it.

---

## How managed API billing works

Managed AI APIs charge per token. A token is approximately 4 characters or 0.75 words in English.

```
Every API call bill = (input_tokens × input_price) + (output_tokens × output_price)

Output tokens are typically 3–5× more expensive than input tokens.
```

Most teams focus on output tokens initially — but input tokens are often the larger driver in production because they include system prompts and conversation history re-sent on every turn.

---

## The seven cost drivers

### 1. Verbose system prompts

**What it is:** System prompts that repeat instructions, over-explain constraints, or use heavy markdown formatting.

**Impact:** A 2,000-token system prompt re-sent on every request adds up fast. At 1M requests/month, that's 2 billion input tokens in system prompt alone.

**Fix:** [Prompt Compression](../managed/01-prompt-compression.md)

---

### 2. Full conversation history

**What it is:** Passing the entire message history on every turn in a multi-turn conversation.

**Impact:** In a 20-turn conversation, by turn 20 you're re-sending 19 previous turns as input. Token cost per conversation grows quadratically with turn count without truncation.

**Fix:** [Context Optimization](../managed/04-context-optimization.md)

---

### 3. Repeated identical or near-identical requests

**What it is:** The same query (or semantically equivalent query) hitting the API multiple times.

**Impact:** FAQ chatbots, repetitive agent subtasks, and template-based workflows often re-process the same content. Each is a full billable call.

**Fix:** [Caching](../managed/02-caching.md)

---

### 4. Premium model for simple tasks

**What it is:** Routing every request to the most capable (most expensive) model, regardless of task complexity.

**Impact:** Using a frontier model ($0.015/1K output) for a task a micro model ($0.0006/1K output) handles equally well is a 25× cost difference per token.

**Fix:** [Model Routing](../managed/03-model-routing.md)

---

### 5. Verbose tool outputs in agentic workflows

**What it is:** Injecting the full output of tool calls (API responses, search results, code execution output) into the context without trimming.

**Impact:** Tool outputs can be thousands of tokens each. In a 10-step agent workflow with verbose tool results, tool output alone can exceed 50,000 input tokens per session.

**Fix:** [Context Optimization](../managed/04-context-optimization.md)

---

### 6. Retry storms and misconfigured loops

**What it is:** Agent loops with no exit condition, retry logic with no backoff, or fan-out workflows that multiply API calls unexpectedly.

**Impact:** A single misconfigured agent can generate thousands of API calls in minutes. These events are invisible without rate limiting and observability.

**Fix:** [Rate Limiting](../managed/05-rate-limiting.md)

---

### 7. No visibility into spend

**What it is:** No per-request cost tracking, no team attribution, no alerting on spend anomalies.

**Impact:** Without observability you can't see which teams, features, or prompt versions are driving cost. You optimize blindly or not at all.

**Fix:** [Observability](../managed/06-observability.md)

---

## Cost driver summary

| Driver | Typical impact | Primary fix |
|--------|---------------|-------------|
| Verbose system prompts | 30–60% of input tokens | Prompt compression |
| Full conversation history | Grows 2× per turn | Context optimization |
| Repeated requests | 20–60% of calls redundant | Caching |
| Wrong model tier | 5–25× overspend per token | Model routing |
| Verbose tool outputs | 50–80% of agentic input tokens | Context optimization |
| Retry storms | Unbounded cost events | Rate limiting |
| No visibility | Can't improve what you can't see | Observability |

---

## Where to start

If you're new to managed AI FinOps, this order maximizes early impact:

1. **Observability first** — deploy Langfuse and get visibility before anything else
2. **Identify your top cost driver** — usually system prompts or conversation history
3. **Quick win: caching** — implement exact-match caching on your highest-traffic routes
4. **Structural: model routing** — route simple tasks to cheaper models
5. **Ongoing: context optimization** — trim agentic context windows
6. **Governance: rate limiting** — add quotas before you scale

---

## Further reading

- [Managed AI FinOps — 6 techniques](../managed/)
- [Cost model comparison](../comparison/cost-model.md)
- [Self-hosted cost drivers](self-hosted-cost-drivers.md)
