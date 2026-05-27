# M-01 — Token audit + prompt compression

> Measure your actual token spend, find the biggest waste, and compress it.

**Technique:** [Prompt Compression](../../managed/01-prompt-compression.md)  
**Time:** ~45 minutes  
**Cost:** < $0.50 in API calls

---

## Objective

By the end of this lab you will have:
- A Langfuse project tracing every API call with token counts and cost
- A before/after comparison of a real prompt compression exercise
- A reusable token budget checker function you can drop into any project

---

## Prerequisites

- Python 3.10+
- Anthropic or OpenAI API key
- Free [Langfuse Cloud](https://cloud.langfuse.com) account (or self-hosted)
- `pip` available

---

## Setup

```bash
# Create a virtual environment
python -m venv finops-lab
source finops-lab/bin/activate   # Windows: finops-lab\Scripts\activate

# Install dependencies
pip install anthropic langfuse tiktoken rich python-dotenv
```

Create a `.env` file:
```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key_here
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
EOF
```

---

## Step 1 — Instrument your API calls with Langfuse

Save this as `lab_m01.py`:

```python
import os
import anthropic
import tiktoken
from langfuse.decorators import observe, langfuse_context
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
console = Console()

def count_tokens(text: str) -> int:
    """Estimate token count using cl100k_base (close enough for Anthropic models)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def estimate_cost(input_tokens: int, output_tokens: int,
                  input_price: float = 0.003, output_price: float = 0.015) -> float:
    """Estimate cost in USD per 1K tokens."""
    return (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
```

---

## Step 2 — Build a bloated vs compressed prompt pair

```python
# --- BLOATED SYSTEM PROMPT (before compression) ---
BLOATED_SYSTEM_PROMPT = """
You are a very helpful AI assistant that is designed to help users with their
customer support questions. It is very important that you always respond in a
professional and courteous manner at all times. Please make sure to always be
helpful and to provide accurate and useful information to the user. Remember
that you should always follow the instructions provided by the user carefully
and attentively. You should make sure to format your responses in a clear and
readable way. It is also important that you keep your responses concise and
to the point while still being comprehensive and thorough. Always remember to
be empathetic and understanding of the user's situation. If you don't know
the answer to a question, you should say so clearly rather than making up
an answer. You should always prioritize the user's satisfaction and happiness.
Please respond in the same language as the user's message. Make sure to
double check your answers for accuracy before responding. Thank you for being
a helpful assistant!
"""

# --- COMPRESSED SYSTEM PROMPT (after compression) ---
COMPRESSED_SYSTEM_PROMPT = """
You are a customer support assistant. Respond professionally, accurately,
and concisely. Match the user's language. If unsure, say so clearly.
"""

TEST_USER_MESSAGE = "How do I reset my password?"
```

---

## Step 3 — Run both prompts and compare

```python
@observe(name="bloated-prompt")
def call_with_bloated_prompt(user_message: str) -> dict:
    langfuse_context.update_current_trace(
        tags=["lab-m01", "bloated"],
        metadata={"prompt_version": "bloated"}
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=BLOATED_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    return {
        "response": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

@observe(name="compressed-prompt")
def call_with_compressed_prompt(user_message: str) -> dict:
    langfuse_context.update_current_trace(
        tags=["lab-m01", "compressed"],
        metadata={"prompt_version": "compressed"}
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=COMPRESSED_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    return {
        "response": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

def run_comparison():
    console.print("\n[bold cyan]Running token audit...[/bold cyan]\n")

    bloated = call_with_bloated_prompt(TEST_USER_MESSAGE)
    compressed = call_with_compressed_prompt(TEST_USER_MESSAGE)

    # Calculate savings
    input_saved = bloated["input_tokens"] - compressed["input_tokens"]
    pct_saved = (input_saved / bloated["input_tokens"]) * 100
    cost_bloated = estimate_cost(bloated["input_tokens"], bloated["output_tokens"])
    cost_compressed = estimate_cost(compressed["input_tokens"], compressed["output_tokens"])
    cost_saved_per_call = cost_bloated - cost_compressed

    # Display results table
    table = Table(title="Prompt Compression — Token Audit", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Bloated", style="red")
    table.add_column("Compressed", style="green")
    table.add_column("Saved", style="bold yellow")

    table.add_row(
        "System prompt tokens",
        str(count_tokens(BLOATED_SYSTEM_PROMPT)),
        str(count_tokens(COMPRESSED_SYSTEM_PROMPT)),
        f"{count_tokens(BLOATED_SYSTEM_PROMPT) - count_tokens(COMPRESSED_SYSTEM_PROMPT)} tokens"
    )
    table.add_row(
        "API input tokens",
        str(bloated["input_tokens"]),
        str(compressed["input_tokens"]),
        f"{input_saved} ({pct_saved:.1f}%)"
    )
    table.add_row(
        "Cost per call",
        f"${cost_bloated:.6f}",
        f"${cost_compressed:.6f}",
        f"${cost_saved_per_call:.6f}"
    )
    table.add_row(
        "Projected @ 1M calls/month",
        f"${cost_bloated * 1_000_000:.2f}",
        f"${cost_compressed * 1_000_000:.2f}",
        f"${cost_saved_per_call * 1_000_000:.2f}"
    )

    console.print(table)

    console.print("\n[bold]Response quality check[/bold]")
    console.print(f"[red]Bloated:[/red]    {bloated['response'][:200]}")
    console.print(f"[green]Compressed:[/green] {compressed['response'][:200]}")
    console.print("\n[dim]Check your Langfuse dashboard for full trace details.[/dim]")

if __name__ == "__main__":
    run_comparison()
```

---

## Step 4 — Add a token budget enforcer

```python
def token_budget_check(
    system_prompt: str,
    messages: list[dict],
    budget: int = 2000
) -> dict:
    """
    Check if a prompt fits within the token budget.
    Returns a report with breakdown and warnings.
    """
    enc = tiktoken.get_encoding("cl100k_base")

    system_tokens = len(enc.encode(system_prompt))
    message_tokens = sum(
        len(enc.encode(m["content"])) for m in messages
    )
    total = system_tokens + message_tokens

    return {
        "system_tokens": system_tokens,
        "message_tokens": message_tokens,
        "total_tokens": total,
        "budget": budget,
        "within_budget": total <= budget,
        "overage": max(0, total - budget),
        "utilization_pct": (total / budget) * 100,
    }

# Example usage
report = token_budget_check(
    system_prompt=BLOATED_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": TEST_USER_MESSAGE}],
    budget=500,
)
console.print("\n[bold]Token budget check:[/bold]", report)
```

---

## Step 5 — Run it

```bash
python lab_m01.py
```

**Expected output:**
```
Running token audit...

┌─────────────────────────────────────────────────────────────────────────┐
│                 Prompt Compression — Token Audit                        │
├───────────────────────────┬───────────┬────────────┬───────────────────┤
│ Metric                    │ Bloated   │ Compressed │ Saved             │
├───────────────────────────┼───────────┼────────────┼───────────────────┤
│ System prompt tokens      │ 198       │ 32         │ 166 tokens        │
│ API input tokens          │ 212       │ 46         │ 166 (78.3%)       │
│ Cost per call             │ $0.000636 │ $0.000138  │ $0.000498         │
│ Projected @ 1M calls/month│ $636.00   │ $138.00    │ $498.00           │
└───────────────────────────┴───────────┴────────────┴───────────────────┘
```

---

## Validate

1. Open your Langfuse dashboard → you should see two traces: `bloated-prompt` and `compressed-prompt`
2. Both traces should show token counts, cost, and model
3. Filter by tag `lab-m01` to see only these traces
4. Verify the response quality is equivalent between both prompts

---

## Cost impact

At 1 million calls/month, a 78% input token reduction on the system prompt alone saves ~$498/month on Claude Haiku — with no quality regression. At higher tiers (Sonnet, Opus), savings scale proportionally.

---

## Teardown

```bash
# Deactivate virtual environment
deactivate

# Remove lab files if desired
rm -rf finops-lab/ lab_m01.py .env
```

---

## Next steps

- Apply this token budget checker to your production system prompts
- Set up Langfuse to track prompt versions across deployments
- Proceed to [M-02: Semantic Cache](m02-semantic-cache.md)
