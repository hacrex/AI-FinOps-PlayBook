# 04 — Context optimization

> Every token in the context window is a billable input token.

**Category:** Managed AI FinOps · Technique 04 of 06  
**Tags:** `context-window` `history-trimming` `summarization`

---

## What it is

Context optimization is the discipline of keeping your context window lean and purposeful — sending only the information the model actually needs for the current turn, rather than the full accumulated history or every available tool output.

In agentic workflows especially, context windows grow rapidly and are re-sent on every model call. Left unchecked, they become the single largest cost driver in the system.

---

## Why it matters

In a multi-turn agentic workflow:
- Every message in the conversation history is re-sent as input tokens on each new turn
- Tool outputs, reasoning traces, and intermediate results accumulate
- Context windows of 50,000–100,000 tokens are common in production agents

```
Turn 1: 500 tokens sent
Turn 2: 1,200 tokens sent (Turn 1 history + new message)
Turn 3: 2,100 tokens sent
...
Turn 20: 18,000 tokens sent

Total input tokens across 20 turns: ~190,000 tokens
```

An optimized agent keeps this under 50,000 total — a 74% reduction without quality loss.

---

## How it works

### 1. Summarize old conversation history

Instead of appending every past message verbatim, summarize older turns into a compact memory block:

```python
def compress_history(messages: list, keep_last_n: int = 5) -> list:
    if len(messages) <= keep_last_n:
        return messages
    
    old_messages = messages[:-keep_last_n]
    recent_messages = messages[-keep_last_n:]
    
    # Summarize old_messages into a single context block
    summary = summarize(old_messages)  # cheap model call
    
    return [{"role": "system", "content": f"Previous context: {summary}"}] + recent_messages
```

Use a micro-tier model (e.g. Claude Haiku) for summarization — the cost is negligible compared to the input token savings on subsequent turns.

### 2. Remove irrelevant tool outputs

In tool-use workflows, tool results can be verbose. Strip everything that isn't needed for subsequent steps:

```python
def trim_tool_output(result: str, max_tokens: int = 500) -> str:
    # For search results: keep only the top 3 snippets
    # For API responses: extract only the fields used downstream
    # For code execution: keep stdout summary, not full trace
    return truncate_to_budget(result, max_tokens)
```

### 3. Trim intermediate reasoning steps

Chain-of-thought reasoning is valuable for the current step but rarely needed in subsequent steps. After a reasoning step completes, include only its conclusion in the next turn's context — not the full reasoning trace.

```
Turn N context:
  [system prompt]
  [user query]
  [assistant reasoning: 2,000 tokens] ← include full
  [assistant conclusion: 100 tokens]

Turn N+1 context:
  [system prompt]
  [user query]
  [previous conclusion: 100 tokens]  ← only the conclusion carries forward
  [new user message]
```

### 4. Use sliding window with priority weighting

Not all history is equally important. Implement a priority-weighted sliding window:

- Always include: system prompt, current user message, last 2 assistant turns
- Include if relevant: tool outputs referenced in the current query
- Summarize: everything older than N turns
- Drop: intermediate reasoning, verbose tool outputs from closed tasks

### 5. Set explicit token budgets per context section

```python
CONTEXT_BUDGET = {
    "system_prompt": 800,      # hard cap — compress if over
    "conversation_history": 3_000,  # rolling window
    "retrieved_context": 2_000,     # per RAG chunk
    "tool_outputs": 1_000,     # per tool call
    "current_turn": 500,       # user + assistant
}
```

---

## Tools

| Tool | Use |
|------|-----|
| [LangChain memory](https://python.langchain.com/docs/modules/memory/) | ConversationSummaryMemory, ConversationBufferWindowMemory |
| [tiktoken](https://github.com/openai/tiktoken) | Count tokens before each API call |
| [Langfuse](https://langfuse.com) | Track context window size per session and per turn |
| Custom trimmer | Rule-based trimming tailored to your tool outputs |

---

## Example

**Scenario:** A DevOps AI agent runs automated incident investigations. Each investigation averages 15 turns, accumulating tool outputs (logs, metrics, kubectl output) in the context.

```
Baseline (no context optimization):
Average context at turn 15: 45,000 tokens
15 turns × avg 25,000 tokens = 375,000 input tokens per investigation
1,000 investigations/month × 375,000 tokens × $0.003/1K = $1,125/month

With context optimization (sliding window + tool output trimming):
Average context at turn 15: 8,000 tokens
15 turns × avg 5,000 tokens = 75,000 input tokens per investigation
1,000 × 75,000 × $0.003/1K = $225/month

Monthly saving: $900 (80% reduction)
Quality: agent accuracy unchanged — only irrelevant history was dropped
```

---

## Implementation checklist

- [ ] Instrument context window size per turn (Langfuse or custom logging)
- [ ] Identify the top 3 context bloat sources in your workload
- [ ] Implement a sliding window for conversation history
- [ ] Add tool output trimming for verbose results (logs, API responses)
- [ ] Set token budgets per context section and enforce them
- [ ] Test summarization quality on a held-out sample before production rollout

---

## Further reading

- [LangChain memory types](https://python.langchain.com/docs/modules/memory/)
- [Anthropic: Context window management](https://docs.anthropic.com/en/docs/build-with-claude/context-window)
- [Building agentic systems: context management patterns](https://www.anthropic.com/research/building-effective-agents)

---

**Previous:** [03 — Model Routing](03-model-routing.md)  
**Next:** [05 — Rate Limiting](05-rate-limiting.md)
