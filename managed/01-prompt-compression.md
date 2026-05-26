# 01 — Prompt compression

> Smaller prompts directly reduce input token costs.

**Category:** Managed AI FinOps · Technique 01 of 06  
**Tags:** `input-tokens` `prompt-design` `context-window`

---

## What it is

Prompt compression is the practice of reducing the byte size of every prompt you send to a managed AI API before the request leaves your system. Because managed APIs bill per input token, every token trimmed is money saved — with zero infrastructure changes required.

---

## Why it matters

Input tokens are often underestimated as a cost driver. In agentic and RAG workflows, system prompts can grow to thousands of tokens and are re-sent on every turn. A single verbose system prompt with 2,000 tokens, called 1 million times per month, adds up fast:

```
2,000 tokens × 1,000,000 calls × $0.003 / 1K tokens = $6,000 / month
compress to 1,600 tokens → saves $1,200 / month (20% reduction)
```

At scale, a 20% reduction in average prompt length compounds into significant savings.

---

## How it works

### 1. Trim verbose system prompts

Most system prompts contain:
- Redundant instructions ("Always remember to...", "It is important that you...")
- Repeated constraints stated multiple ways
- Formatting instructions that could be implicit
- Long preambles before the actual instruction

Write system prompts like code: every token must earn its place.

**Before:**
```
You are a helpful AI assistant. It is very important that you always respond 
in a professional and courteous manner. Please make sure to always be helpful 
and provide accurate information. Remember to always follow the user's 
instructions carefully. You should always format your responses clearly.
```

**After:**
```
Respond professionally, accurately, and follow instructions precisely.
```

Token reduction: ~60 tokens → ~10 tokens (83% reduction on this block).

### 2. Abbreviate repeated patterns

In multi-turn or tool-use workflows, the same context often appears repeatedly. Instead of re-sending the full object, send a reference or summary:

```
# Instead of resending the full 500-token user profile every turn:
User: [see profile ID usr_123 in context]
```

### 3. Strip formatting that adds tokens without meaning

Markdown formatting in system prompts (bold, bullet points, headers) consumes tokens. In many cases the model doesn't need them to follow the instruction — plain prose works just as well.

### 4. Use structured compression for RAG context

When injecting retrieved documents, compress before injection:
- Truncate to the relevant passage, not the whole document
- Use extractive summarization for background context
- Set a strict token budget per retrieved chunk

---

## Tools

| Tool | Use |
|------|-----|
| [LLMLingua](https://github.com/microsoft/LLMLingua) | Automated prompt compression using a smaller LLM to identify removable tokens |
| [tiktoken](https://github.com/openai/tiktoken) | Count tokens before sending — measure before optimizing |
| [Langfuse](https://langfuse.com) | Token tracking per prompt version — compare before/after |
| Custom preprocessor | Regex + rule-based stripping for known patterns in your stack |

---

## Example

**Scenario:** A customer support chatbot re-sends a 1,800-token system prompt on every user turn. The system runs 500,000 conversations per month, averaging 4 turns each.

```
Baseline:
1,800 tokens × 4 turns × 500,000 conversations = 3,600,000,000 input tokens/month
At $0.003/1K tokens = $10,800/month in system prompt tokens alone

After compression to 900 tokens:
900 tokens × 4 × 500,000 = 1,800,000,000 tokens
= $5,400/month

Monthly saving: $5,400
Annual saving: $64,800
```

No model quality regression was observed in A/B testing — the instructions were identical, just more concise.

---

## Further reading

- [LLMLingua: Compressing Prompts for Accelerated Inference](https://arxiv.org/abs/2310.05736) — Microsoft Research
- [OpenAI tokenizer](https://platform.openai.com/tokenizer) — count tokens interactively
- [Anthropic: Long context tips](https://docs.anthropic.com/en/docs/build-with-claude/long-context-tips)
- [tiktoken on GitHub](https://github.com/openai/tiktoken)

---

**Next:** [02 — Caching](02-caching.md)
