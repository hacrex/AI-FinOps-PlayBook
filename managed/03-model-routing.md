# 03 — Model routing

> Not every request needs your most expensive model.

**Category:** Managed AI FinOps · Technique 03 of 06  
**Tags:** `model-selection` `tiering` `cost-quality-tradeoff`

---

## What it is

Model routing is the practice of dynamically selecting the right AI model for each request based on task complexity — routing simple tasks to cheaper, faster models and reserving expensive frontier models only for tasks that genuinely need them.

---

## Why it matters

Most enterprise workloads are not uniformly complex. A typical production system contains:
- **Simple tasks** (60–70%): classification, extraction, formatting, summarization, FAQ — handleable by small models at a fraction of the cost
- **Medium tasks** (20–30%): multi-step reasoning, code generation, structured analysis
- **Complex tasks** (5–15%): nuanced judgment, long-form generation, complex planning

If you route all of these to a frontier model (e.g. GPT-4o, Claude Opus), you're paying premium prices for commodity work. A 10x price difference between tiers is common.

---

## How it works

### Tier structure

Define model tiers based on your provider's offerings. Example:

| Tier | Model (example) | Cost (input) | Use for |
|------|----------------|--------------|---------|
| Micro | GPT-4o mini / Claude Haiku | ~$0.00015/1K | Classification, extraction, simple QA |
| Standard | GPT-4o / Claude Sonnet | ~$0.003/1K | Reasoning, code, analysis |
| Premium | o1 / Claude Opus | ~$0.015/1K | Complex planning, expert judgment |

### Routing strategies

**1. Rule-based routing** — simple, deterministic, fast:

```python
def route_model(task_type: str, context_length: int) -> str:
    if task_type in ["classify", "extract", "format"]:
        return "claude-haiku-4-5"
    elif context_length > 50_000 or task_type == "complex_reasoning":
        return "claude-opus-4-6"
    else:
        return "claude-sonnet-4-6"
```

**2. Classifier-based routing** — a small, cheap model decides which tier to use:

```
Incoming request → lightweight classifier (Haiku / GPT-4o mini)
                 → "simple" → route to micro tier
                 → "medium" → route to standard tier  
                 → "complex" → route to premium tier
```

The classifier call costs ~$0.0001; it can save $0.015 on a complex model call that wasn't needed.

**3. Cascading (try-cheap-first)** — attempt with micro model, escalate if confidence is low:

```
Request → Micro model → confidence > 0.9? → return response
                      → confidence < 0.9? → retry with Standard
                                          → still low? → Premium
```

Works well for extraction and classification tasks where the model can self-report uncertainty.

### Quality validation

When routing to cheaper models, add a lightweight quality gate:
- For structured outputs: validate JSON schema
- For classification: check confidence scores
- For critical paths: shadow-test a sample against the premium model and alert on divergence

---

## Tools

| Tool | Use |
|------|-----|
| [LiteLLM](https://github.com/BerriAI/litellm) | Unified API across providers with built-in routing and fallback |
| [RouteLLM](https://github.com/lm-sys/RouteLLM) | Open-source router trained on quality-cost tradeoffs |
| [Portkey](https://portkey.ai) | Gateway with routing rules, fallbacks, and cost tracking |
| [Langfuse](https://langfuse.com) | Track cost-per-model and quality metrics to validate routing decisions |

---

## Example

**Scenario:** A legal tech platform runs 300,000 API calls per month. Current setup sends everything to GPT-4o ($0.005/1K input).

Analysis of call types:
- 180,000 calls (60%) are document classification and metadata extraction → routable to GPT-4o mini
- 90,000 calls (30%) are clause analysis and summarization → keep on GPT-4o
- 30,000 calls (10%) are contract risk assessment → keep on GPT-4o (or upgrade to o1)

Average prompt: 1,500 tokens.

```
Before routing:
300,000 × 1,500 tokens × $0.005/1K = $2,250/month

After routing:
180,000 × 1,500 × $0.00015/1K  =   $40.50  (micro)
 90,000 × 1,500 × $0.005/1K    =  $675.00  (standard)
 30,000 × 1,500 × $0.015/1K    =  $675.00  (premium)
Total = $1,390.50/month

Monthly saving: $859.50 (38% reduction)
Quality: unchanged — premium tasks still use premium models
```

---

## Implementation checklist

- [ ] Audit existing calls — categorize by task type and complexity
- [ ] Define model tiers for your provider(s)
- [ ] Start with rule-based routing on the clearest task types
- [ ] Instrument with Langfuse to track cost per tier and quality metrics
- [ ] Validate quality on a shadow sample before full rollout
- [ ] Iterate — add more task types to cheaper tiers as confidence grows

---

## Further reading

- [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665)
- [LiteLLM routing documentation](https://docs.litellm.ai/docs/routing)
- [Portkey model routing guide](https://portkey.ai/docs/product/ai-gateway/routing)
- [Anthropic model overview](https://docs.anthropic.com/en/docs/about-claude/models)

---

**Previous:** [02 — Caching](02-caching.md)  
**Next:** [04 — Context Optimization](04-context-optimization.md)
