# M-04: Context optimization for agentic workflows

> Build a sliding window context manager that reduces token spend by 70%+ in multi-turn agents.

**Time:** 60 min  
**Difficulty:** Intermediate  
**Prerequisites:** Python 3.10+, Langfuse account, Anthropic or OpenAI API key

---

## Objective

By the end of this lab you will have:

1. A working agent with unbounded context growth (baseline)
2. A context optimizer implementing sliding window + summarization
3. Side-by-side token usage comparison showing cost reduction
4. A Langfuse dashboard visualizing context window size per turn

---

## Prerequisites

- Python 3.10+ installed
- An API key for Anthropic Claude or OpenAI GPT-4
- A free [Langfuse Cloud](https://cloud.langfuse.com) account
- Basic familiarity with conversational AI patterns

Estimated API cost for this lab: <$0.50

---

## Setup

### 1. Create project directory

```bash
mkdir -p m04-context-opt && cd m04-context-opt
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install langfuse anthropic tiktoken
```

### 2. Set environment variables

Create a `.env` file:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
export LANGFUSE_PUBLIC_KEY="your-langfuse-public-key"
export LANGFUSE_SECRET_KEY="your-langfuse-secret-key"
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

### 3. Initialize Langfuse client

Create `langfuse_client.py`:

```python
from langfuse import Langfuse
import os

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)

print("Langfuse initialized successfully!")
```

Run it:

```bash
python langfuse_client.py
```

Expected output:
```
Langfuse initialized successfully!
```

---

## Step-by-step

### Step 1: Build baseline agent (unbounded context)

Create `baseline_agent.py`:

```python
from anthropic import Anthropic
from langfuse.decorators import observe, langfuse_context
import tiktoken
import os

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
encoder = tiktoken.get_encoding("cl100k_base")

@observe()
def count_tokens(text: str) -> int:
    return len(encoder.encode(text))

@observe()
class BaselineAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history = []
        
    @observe()
    def chat(self, user_message: str) -> str:
        # Add user message to history
        self.history.append({"role": "user", "content": user_message})
        
        # Count total context tokens
        full_context = "\n".join([msg["content"] for msg in self.history])
        token_count = count_tokens(full_context)
        
        langfuse_context.update_current_trace(
            metadata={
                "context_tokens": token_count,
                "message_count": len(self.history),
                "agent_type": "baseline"
            }
        )
        
        # Call Claude with full history
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=self.history
        )
        
        assistant_message = response.content[0].text
        self.history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message

# Test the baseline agent
if __name__ == "__main__":
    agent = BaselineAgent(session_id="test-session-001")
    
    # Simulate 10-turn conversation
    queries = [
        "What is machine learning?",
        "Can you explain neural networks?",
        "What about deep learning specifically?",
        "How do transformers work?",
        "What is attention mechanism?",
        "Explain self-attention in simple terms",
        "What are the benefits of transformers over RNNs?",
        "Give me an example use case",
        "How would I implement this in Python?",
        "What libraries should I use?"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n=== Turn {i} ===")
        print(f"User: {query}")
        response = agent.chat(query)
        print(f"Assistant: {response[:100]}...")
        
    print(f"\nTotal messages in history: {len(agent.history)}")
```

Run the baseline:

```bash
python baseline_agent.py
```

Expected output:
```
=== Turn 1 ===
User: What is machine learning?
Assistant: Machine learning is a subset of artificial intelligence...

=== Turn 2 ===
User: Can you explain neural networks?
Assistant: Neural networks are computing systems inspired by biological neural networks...

...

Total messages in history: 20
```

### Step 2: View baseline metrics in Langfuse

1. Go to your Langfuse dashboard
2. Find the trace for `test-session-001`
3. Observe:
   - Context tokens growing with each turn
   - Total token count at turn 10

Note the final context token count — this is your baseline.

### Step 3: Build optimized agent with sliding window

Create `optimized_agent.py`:

```python
from anthropic import Anthropic
from langfuse.decorators import observe, langfuse_context
import tiktoken
import os

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
encoder = tiktoken.get_encoding("cl100k_base")

@observe()
def count_tokens(text: str) -> int:
    return len(encoder.encode(text))

@observe()
def summarize_history(old_messages: list) -> str:
    """Summarize old conversation history using a cheap model call."""
    if not old_messages:
        return ""
    
    # Format old messages for summarization
    conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in old_messages])
    
    summary_prompt = f"""Summarize the following conversation in 3-4 sentences, capturing only the key topics and conclusions:

{conversation}

Summary:"""
    
    response = anthropic_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": summary_prompt}]
    )
    
    return response.content[0].text

@observe()
class OptimizedAgent:
    def __init__(self, session_id: str, keep_last_n: int = 5, max_context_tokens: int = 3000):
        self.session_id = session_id
        self.keep_last_n = keep_last_n
        self.max_context_tokens = max_context_tokens
        self.history = []
        self.summary = ""
        
    @observe()
    def _build_optimized_context(self) -> list:
        """Build context with sliding window + summarization."""
        if len(self.history) <= self.keep_last_n:
            return self.history
        
        # Split into old and recent
        old_messages = self.history[:-self.keep_last_n]
        recent_messages = self.history[-self.keep_last_n:]
        
        # Summarize old messages (or reuse existing summary)
        if len(old_messages) > 2:  # Only re-summarize if enough new content
            self.summary = summarize_history(old_messages)
        
        # Build optimized context
        optimized_context = []
        
        if self.summary:
            optimized_context.append({
                "role": "system",
                "content": f"Previous conversation summary: {self.summary}"
            })
        
        optimized_context.extend(recent_messages)
        
        return optimized_context
    
    @observe()
    def chat(self, user_message: str) -> str:
        # Add user message to history
        self.history.append({"role": "user", "content": user_message})
        
        # Build optimized context
        optimized_context = self._build_optimized_context()
        
        # Count optimized context tokens
        full_context = "\n".join([msg["content"] for msg in optimized_context])
        token_count = count_tokens(full_context)
        
        langfuse_context.update_current_trace(
            metadata={
                "context_tokens": token_count,
                "message_count": len(self.history),
                "agent_type": "optimized",
                "compression_ratio": round((1 - token_count / sum(len(encoder.encode(m["content"])) for m in self.history)) * 100, 1)
            }
        )
        
        # Call Claude with optimized context
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=optimized_context
        )
        
        assistant_message = response.content[0].text
        self.history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message

# Test the optimized agent
if __name__ == "__main__":
    agent = OptimizedAgent(
        session_id="test-session-002",
        keep_last_n=5,
        max_context_tokens=3000
    )
    
    # Use same queries as baseline
    queries = [
        "What is machine learning?",
        "Can you explain neural networks?",
        "What about deep learning specifically?",
        "How do transformers work?",
        "What is attention mechanism?",
        "Explain self-attention in simple terms",
        "What are the benefits of transformers over RNNs?",
        "Give me an example use case",
        "How would I implement this in Python?",
        "What libraries should I use?"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n=== Turn {i} ===")
        print(f"User: {query}")
        response = agent.chat(query)
        print(f"Assistant: {response[:100]}...")
        
    print(f"\nTotal messages in history: {len(agent.history)}")
    print(f"Context uses sliding window of last {agent.keep_last_n} messages + summary")
```

Run the optimized agent:

```bash
python optimized_agent.py
```

Expected output:
```
=== Turn 1 ===
User: What is machine learning?
Assistant: Machine learning is a subset of artificial intelligence...

=== Turn 2 ===
User: Can you explain neural networks?
Assistant: Neural networks are computing systems inspired by biological neural networks...

...

Total messages in history: 20
Context uses sliding window of last 5 messages + summary
```

### Step 4: Compare metrics side-by-side

Create `compare_agents.py`:

```python
from baseline_agent import BaselineAgent
from optimized_agent import OptimizedAgent
from langfuse import Langfuse
import os

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)

queries = [
    "What is machine learning?",
    "Can you explain neural networks?",
    "What about deep learning specifically?",
    "How do transformers work?",
    "What is attention mechanism?",
    "Explain self-attention in simple terms",
    "What are the benefits of transformers over RNNs?",
    "Give me an example use case",
    "How would I implement this in Python?",
    "What libraries should I use?"
]

print("=" * 60)
print("BASELINE AGENT")
print("=" * 60)

baseline = BaselineAgent(session_id="compare-baseline")
for query in queries:
    baseline.chat(query)

baseline_final_tokens = sum(
    len(baseline.history[i]["content"].split()) * 1.3  # Rough token estimate
    for i in range(len(baseline.history))
)
print(f"Final context size: ~{int(baseline_final_tokens)} tokens")
print(f"Total messages: {len(baseline.history)}")

print("\n" + "=" * 60)
print("OPTIMIZED AGENT")
print("=" * 60)

optimized = OptimizedAgent(session_id="compare-optimized", keep_last_n=5)
for query in queries:
    optimized.chat(query)

optimized_final_tokens = sum(
    len(msg["content"].split()) * 1.3
    for msg in optimized.history[-5:]  # Only last 5 messages
) + len(optimized.summary.split()) * 1.3
print(f"Final context size: ~{int(optimized_final_tokens)} tokens")
print(f"Total messages: {len(optimized.history)}")
print(f"Summary length: ~{len(optimized.summary.split()) * 1.3:.0f} tokens")

print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
reduction = (1 - optimized_final_tokens / baseline_final_tokens) * 100
print(f"Token reduction: {reduction:.1f}%")
print(f"Baseline context: ~{int(baseline_final_tokens)} tokens")
print(f"Optimized context: ~{int(optimized_final_tokens)} tokens")
print(f"Saved: ~{int(baseline_final_tokens - optimized_final_tokens)} tokens per session")
```

Run the comparison:

```bash
python compare_agents.py
```

Expected output:
```
============================================================
BASELINE AGENT
============================================================
Final context size: ~4500 tokens
Total messages: 20

============================================================
OPTIMIZED AGENT
============================================================
Final context size: ~1200 tokens
Total messages: 20
Summary length: ~150 tokens

============================================================
COMPARISON
============================================================
Token reduction: 73.3%
Baseline context: ~4500 tokens
Optimized context: ~1200 tokens
Saved: ~3300 tokens per session
```

### Step 5: Build Langfuse dashboard

1. Go to Langfuse dashboard
2. Navigate to "Sessions" view
3. Filter by session IDs: `compare-baseline` and `compare-optimized`
4. Create a chart comparing `context_tokens` metadata field across turns
5. Export the chart or take a screenshot

You should see:
- Baseline: steadily increasing token count
- Optimized: flat token count after turn 5

---

## Validate

Checklist to confirm success:

- [ ] Both agents complete 10-turn conversations without errors
- [ ] Langfuse traces show `context_tokens` metadata for each turn
- [ ] Optimized agent shows 60-80% token reduction vs baseline
- [ ] Summary is coherent and preserves key conversation topics
- [ ] Quality of responses is comparable between both agents

---

## Cost impact

Using the numbers from this lab:

```
Baseline agent (10-turn session):
4,500 tokens average context × 10 turns = 45,000 input tokens
At $0.003/1K tokens: $0.135 per session

Optimized agent (10-turn session):
1,200 tokens average context × 10 turns = 12,000 input tokens
At $0.003/1K tokens: $0.036 per session

Savings: $0.099 per session (73% reduction)

At 10,000 sessions/month:
Baseline: $1,350/month
Optimized: $360/month
Monthly savings: $990
```

Additional cost: One summarization call per 5 turns (~$0.002) — negligible compared to savings.

---

## Teardown

Clean up resources:

```bash
# Deactivate virtual environment
deactivate

# Optional: remove project directory
cd ..
rm -rf m04-context-opt
```

Keep your Langfuse project for future labs — no cleanup needed there.

---

## Next steps

1. **Tune the sliding window**: Experiment with `keep_last_n` values (3, 5, 7) to find the sweet spot for your use case
2. **Add tool output trimming**: Extend the optimizer to trim verbose tool results
3. **Implement token budgets**: Add hard caps per context section (system prompt, history, tool outputs)
4. **Try hierarchical summarization**: For very long conversations, summarize summaries recursively
5. **Read the technique doc**: [04 — Context Optimization](../../managed/04-context-optimization.md)

---

## Troubleshooting

**Issue:** Langfuse traces not appearing  
**Fix:** Verify environment variables are set correctly. Check Langfuse dashboard for any error messages.

**Issue:** Summary quality is poor  
**Fix:** Improve the summarization prompt. Consider using a stronger model (Claude Sonnet) for summarization if Haiku struggles.

**Issue:** Token counts don't match expectations  
**Fix:** Remember that `tiktoken` estimates may differ slightly from actual API token counts. Use Langfuse's captured token counts for accurate measurements.

**Issue:** Agent loses important context  
**Fix:** Increase `keep_last_n` or improve the summarization logic to preserve critical information.
