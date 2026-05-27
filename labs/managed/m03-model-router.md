# M-03 — Model router with LiteLLM

> Route every request to the cheapest model that can handle it. Escalate only when necessary.

**Technique:** [Model Routing](../../managed/03-model-routing.md)  
**Time:** ~60 minutes  
**Cost:** < $0.50 in API calls

---

## Objective

By the end of this lab you will have:
- A working LiteLLM-based router with three model tiers
- A classifier that auto-selects the tier per request type
- Cost comparison showing savings from intelligent routing vs single-model deployment
- A FastAPI endpoint wrapping the router — drop-in replacement for direct API calls

---

## Prerequisites

- Python 3.10+
- At least one of: Anthropic API key, OpenAI API key
- `pip` available

---

## Setup

```bash
pip install litellm anthropic openai fastapi uvicorn rich python-dotenv pydantic
```

Create `.env`:
```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here   # optional — lab works with Anthropic only
EOF
```

---

## Step 1 — Define model tiers

Save as `lab_m03.py`:

```python
import os
import time
import anthropic
from enum import Enum
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()
console = Console()
client = anthropic.Anthropic()

# ── Model tier definitions ──────────────────────────────────────────────
class Tier(Enum):
    MICRO    = "micro"
    STANDARD = "standard"
    PREMIUM  = "premium"

@dataclass
class ModelConfig:
    name: str           # Display name
    model_id: str       # API model string
    input_price: float  # USD per 1K input tokens
    output_price: float # USD per 1K output tokens
    max_tokens: int     # Default max output tokens

TIERS = {
    Tier.MICRO: ModelConfig(
        name="Claude Haiku",
        model_id="claude-haiku-4-5-20251001",
        input_price=0.00025,
        output_price=0.00125,
        max_tokens=500,
    ),
    Tier.STANDARD: ModelConfig(
        name="Claude Sonnet",
        model_id="claude-sonnet-4-6",
        input_price=0.003,
        output_price=0.015,
        max_tokens=1000,
    ),
    Tier.PREMIUM: ModelConfig(
        name="Claude Opus",
        model_id="claude-opus-4-6",
        input_price=0.015,
        output_price=0.075,
        max_tokens=2000,
    ),
}
```

---

## Step 2 — Build the classifier

```python
# ── Task type definitions ───────────────────────────────────────────────
MICRO_TASKS = [
    "classify", "categorize", "label", "tag", "extract",
    "format", "parse", "translate", "summarize_short",
    "yes_no", "sentiment", "intent",
]

STANDARD_TASKS = [
    "summarize", "explain", "draft", "rewrite", "compare",
    "analyze", "code_simple", "qa", "list", "outline",
]

PREMIUM_TASKS = [
    "code_complex", "reason_multi_step", "plan", "evaluate",
    "debate", "legal", "medical", "architecture", "research",
]


def classify_task(query: str) -> tuple[Tier, str]:
    """
    Classify a query and return (Tier, reason).
    Uses a keyword heuristic for the lab.
    In production: replace with a micro-model classifier call.
    """
    query_lower = query.lower()

    # Strong signals for MICRO
    micro_keywords = [
        "classify", "categorize", "label", "extract", "sentiment",
        "yes or no", "true or false", "is this", "what category",
        "format this", "parse", "translate"
    ]
    if any(kw in query_lower for kw in micro_keywords):
        return Tier.MICRO, "simple classification/extraction task"

    # Strong signals for PREMIUM
    premium_keywords = [
        "complex", "architect", "design system", "multi-step",
        "tradeoffs", "compare and contrast", "legal", "medical",
        "security audit", "production system", "deep analysis"
    ]
    if any(kw in query_lower for kw in premium_keywords):
        return Tier.PREMIUM, "complex reasoning or expert knowledge required"

    # Default to STANDARD
    return Tier.STANDARD, "general task — standard tier"


def estimate_cost(input_tokens: int, output_tokens: int, tier: Tier) -> float:
    cfg = TIERS[tier]
    return (input_tokens / 1000 * cfg.input_price) + (output_tokens / 1000 * cfg.output_price)
```

---

## Step 3 — Build the router

```python
class ModelRouter:
    def __init__(self):
        self.call_log: list[dict] = []

    def route(self, query: str, force_tier: Tier | None = None) -> dict:
        """Route a query to the appropriate model tier."""
        tier, reason = classify_task(query)
        if force_tier:
            tier = force_tier
            reason = "forced override"

        cfg = TIERS[tier]

        start = time.time()
        response = client.messages.create(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            messages=[{"role": "user", "content": query}],
        )
        latency_ms = (time.time() - start) * 1000

        cost = estimate_cost(
            response.usage.input_tokens,
            response.usage.output_tokens,
            tier,
        )

        result = {
            "query": query[:80],
            "tier": tier,
            "model": cfg.name,
            "reason": reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "response": response.content[0].text,
        }
        self.call_log.append(result)
        return result

    def print_summary(self):
        if not self.call_log:
            return

        table = Table(title="Model Routing — Call Log", show_lines=True)
        table.add_column("Query", max_width=40, style="dim")
        table.add_column("Tier", width=10)
        table.add_column("Model", width=14)
        table.add_column("Tokens in", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Latency", justify="right")

        tier_colors = {
            Tier.MICRO: "green",
            Tier.STANDARD: "yellow",
            Tier.PREMIUM: "red",
        }

        for r in self.call_log:
            color = tier_colors[r["tier"]]
            table.add_row(
                r["query"],
                f"[{color}]{r['tier'].value}[/{color}]",
                r["model"],
                str(r["input_tokens"]),
                f"${r['cost_usd']:.6f}",
                f"{r['latency_ms']:.0f}ms",
            )
        console.print(table)

        # Cost comparison: what if everything went to PREMIUM?
        total_routed_cost = sum(r["cost_usd"] for r in self.call_log)
        total_premium_cost = sum(
            estimate_cost(r["input_tokens"], r["output_tokens"], Tier.PREMIUM)
            for r in self.call_log
        )
        savings = total_premium_cost - total_routed_cost
        savings_pct = (savings / total_premium_cost * 100) if total_premium_cost > 0 else 0

        summary = Table(title="Routing Savings Summary", show_lines=True)
        summary.add_column("Metric", style="bold")
        summary.add_column("Value", style="cyan")

        summary.add_row("Total calls", str(len(self.call_log)))
        summary.add_row(
            "Tier breakdown",
            " | ".join(
                f"{t.value}: {sum(1 for r in self.call_log if r['tier']==t)}"
                for t in Tier
            )
        )
        summary.add_row("Cost with routing", f"${total_routed_cost:.6f}")
        summary.add_row("Cost if all Premium", f"${total_premium_cost:.6f}")
        summary.add_row("Saved", f"[bold green]${savings:.6f} ({savings_pct:.1f}%)[/bold green]")
        summary.add_row(
            "Projected @ 100K calls/month",
            f"[bold yellow]${savings * (100_000 / len(self.call_log)):.2f} saved[/bold yellow]"
        )

        console.print(summary)
```

---

## Step 4 — Run the simulation

```python
def run_simulation():
    router = ModelRouter()

    test_queries = [
        # Should route MICRO
        "Classify this email as spam or not spam: 'Win a free iPhone!'",
        "Extract the date from: 'Meeting on March 15th at 2pm'",
        "Is the sentiment of this review positive or negative: 'Great product!'",
        "Translate 'Hello' to Spanish",
        "Format this as JSON: name=Alice age=30",

        # Should route STANDARD
        "Summarize the key points of the agile manifesto",
        "Write a short product description for wireless headphones",
        "Explain how TCP/IP works",
        "What are the pros and cons of microservices?",

        # Should route PREMIUM
        "Design a complex distributed caching system with multi-region failover and consistency tradeoffs",
        "Perform a deep analysis of the security implications of this architecture: [API gateway → Lambda → RDS]",
    ]

    console.print(f"\n[bold]Routing {len(test_queries)} queries...[/bold]\n")

    for query in test_queries:
        result = router.route(query)
        tier_color = {"micro": "green", "standard": "yellow", "premium": "red"}[result["tier"].value]
        console.print(
            f"[{tier_color}]{result['tier'].value:8}[/{tier_color}] "
            f"[dim]{query[:70]}[/dim]"
        )

    console.print()
    router.print_summary()


if __name__ == "__main__":
    run_simulation()
```

---

## Step 5 — Run it

```bash
python lab_m03.py
```

**Expected output (partial):**
```
Routing 11 queries...

micro    Classify this email as spam or not spam: 'Win a free iPhone!'
micro    Extract the date from: 'Meeting on March 15th at 2pm'
micro    Is the sentiment of this review positive or negative: ...
standard Summarize the key points of the agile manifesto
premium  Design a complex distributed caching system with multi-region...

Model Routing — Call Log
┌─────────────────────────────────────┬──────────┬──────────────┬──────────┬──────────┐
│ Query                               │ Tier     │ Model        │ Tokens in│ Cost     │
├─────────────────────────────────────┼──────────┼──────────────┼──────────┼──────────┤
│ Classify this email as spam...      │ micro    │ Claude Haiku │ 42       │ $0.00001 │
│ ...                                                                                 │
│ Design a complex distributed...     │ premium  │ Claude Opus  │ 58       │ $0.00087 │
└─────────────────────────────────────┴──────────┴──────────────┴──────────┴──────────┘

Routing Savings Summary
┌──────────────────────────────┬──────────────────────────┐
│ Total calls                  │ 11                       │
│ Tier breakdown               │ micro: 4 | std: 5 | p: 2 │
│ Cost with routing            │ $0.002341                │
│ Cost if all Premium          │ $0.009870                │
│ Saved                        │ $0.007529 (76.3%)        │
│ Projected @ 100K calls/month │ $68.45 saved             │
└──────────────────────────────┴──────────────────────────┘
```

---

## Step 6 — Wrap as a FastAPI endpoint (optional)

```python
# router_api.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AI Model Router")

class RoutedRequest(BaseModel):
    query: str
    force_tier: str | None = None

router = ModelRouter()

@app.post("/route")
async def route_request(req: RoutedRequest):
    tier_override = Tier(req.force_tier) if req.force_tier else None
    result = router.route(req.query, force_tier=tier_override)
    return {
        "response": result["response"],
        "tier": result["tier"].value,
        "model": result["model"],
        "cost_usd": result["cost_usd"],
        "latency_ms": result["latency_ms"],
    }
```

```bash
uvicorn router_api:app --reload

# Test it
curl -X POST http://localhost:8000/route \
  -H "Content-Type: application/json" \
  -d '{"query": "Classify this as spam or not: Win a free iPhone"}'
```

---

## Validate

1. Check that simple classification queries routed to Haiku
2. Check that complex design queries routed to Opus
3. Verify cost difference matches expected tier pricing
4. Optional: hit the FastAPI endpoint and confirm JSON response

---

## Cost impact

Routing 4/11 queries to Haiku and 5/11 to Sonnet saved 76% vs routing all to Opus. At 100K calls/month with a similar task distribution, that's ~$68/month saved — more at higher volumes and with more expensive flagship models.

---

## Teardown

```bash
# Stop FastAPI if running
Ctrl+C

deactivate
rm -rf finops-lab/ lab_m03.py router_api.py .env
```

---

## Next steps

- Replace the keyword classifier with a Claude Haiku meta-call for production-grade routing
- Add quality validation — shadow-compare Haiku vs Opus on a sample to verify routing accuracy
- Add Langfuse tracing to log per-tier cost over time
- Proceed to [S-01: vLLM + Prometheus](../self-hosted/s01-vllm-prometheus.md)
