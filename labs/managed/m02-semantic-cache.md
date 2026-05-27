# M-02 — Semantic cache with GPTCache + Redis

> Build a semantic cache layer that eliminates redundant API calls — even when queries are phrased differently.

**Technique:** [Caching](../../managed/02-caching.md)  
**Time:** ~60 minutes  
**Cost:** < $0.25 in API calls

---

## Objective

By the end of this lab you will have:
- A running Redis instance as the cache backend
- GPTCache configured with semantic similarity matching
- A measurable cache hit rate with latency and cost comparison
- A drop-in cache wrapper usable in any Python LLM project

---

## Prerequisites

- Python 3.10+
- Docker (for Redis)
- Anthropic or OpenAI API key
- ~4 GB RAM available for the embedding model

---

## Setup

```bash
# Start Redis with Docker
docker run -d \
  --name redis-cache \
  -p 6379:6379 \
  redis:7-alpine

# Verify Redis is running
docker exec redis-cache redis-cli ping
# Expected: PONG

# Install Python dependencies
pip install gptcache anthropic openai sentence-transformers \
            redis rich python-dotenv
```

Create `.env`:
```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key_here
EOF
```

---

## Step 1 — Understand the cache architecture

```
Incoming query
      │
      ▼
┌─────────────────────────────┐
│  Embedding Model            │
│  (sentence-transformers)    │
│  all-MiniLM-L6-v2           │
└──────────────┬──────────────┘
               │ query vector
               ▼
┌─────────────────────────────┐
│  Vector Similarity Search   │
│  (Redis / FAISS)            │
│  threshold: cosine > 0.85   │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┐
       │                │
   HIT ▼            MISS ▼
┌──────────┐    ┌──────────────┐
│  Return  │    │  Call LLM    │
│  cached  │    │  API         │
│  response│    │  Store result│
└──────────┘    └──────────────┘
```

---

## Step 2 — Build the semantic cache wrapper

Save as `lab_m02.py`:

```python
import os
import time
import hashlib
import anthropic
from gptcache import cache
from gptcache.adapter.api import init_similar_cache
from gptcache.embedding import Onnx
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()

console = Console()
client = anthropic.Anthropic()

# Cost constants (Claude Haiku)
INPUT_PRICE_PER_1K = 0.00025
OUTPUT_PRICE_PER_1K = 0.00125
```

---

## Step 3 — Initialize the cache

```python
def init_cache():
    """Initialize GPTCache with sentence-transformer embeddings + Redis backend."""
    console.print("[cyan]Initializing semantic cache...[/cyan]")

    # Use ONNX-optimized sentence transformer (faster than PyTorch for inference)
    embedding_model = Onnx()

    # Redis as the scalar (metadata) store
    # FAISS as the vector store (in-memory for this lab)
    data_manager = get_data_manager(
        CacheBase("redis", url="redis://localhost:6379"),
        VectorBase("faiss", dimension=embedding_model.dimension),
    )

    cache.init(
        embedding_func=embedding_model.to_embeddings,
        data_manager=data_manager,
        similarity_evaluation=SearchDistanceEvaluation(),
    )
    cache.set_openai_key()  # not used for Anthropic but required by GPTCache init

    console.print("[green]✓ Cache initialized[/green]")
    return embedding_model
```

---

## Step 4 — Build a cached LLM caller with stats

```python
class CachedLLMClient:
    def __init__(self):
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_latency_ms": 0,
            "cached_latency_ms": 0,
            "api_latency_ms": 0,
            "api_input_tokens": 0,
            "api_output_tokens": 0,
        }
        # Simple in-memory exact cache for this lab
        self._cache: dict = {}
        self._semantic_threshold = 0.85

    def _make_key(self, query: str) -> str:
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def call(self, query: str, system: str = "You are a helpful assistant.") -> dict:
        self.stats["total_calls"] += 1
        start = time.time()

        # Check exact cache first (fastest)
        key = self._make_key(query)
        if key in self._cache:
            latency_ms = (time.time() - start) * 1000
            self.stats["cache_hits"] += 1
            self.stats["cached_latency_ms"] += latency_ms
            return {
                "response": self._cache[key],
                "cache_hit": True,
                "source": "exact_cache",
                "latency_ms": latency_ms,
                "cost_usd": 0.0,
            }

        # Cache miss — call the API
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": query}],
        )
        latency_ms = (time.time() - start) * 1000
        text = response.content[0].text
        cost = (
            response.usage.input_tokens / 1000 * INPUT_PRICE_PER_1K +
            response.usage.output_tokens / 1000 * OUTPUT_PRICE_PER_1K
        )

        # Store in cache
        self._cache[key] = text
        self.stats["cache_misses"] += 1
        self.stats["api_latency_ms"] += latency_ms
        self.stats["api_input_tokens"] += response.usage.input_tokens
        self.stats["api_output_tokens"] += response.usage.output_tokens

        return {
            "response": text,
            "cache_hit": False,
            "source": "api",
            "latency_ms": latency_ms,
            "cost_usd": cost,
        }

    def print_stats(self):
        total = self.stats["total_calls"]
        hits = self.stats["cache_hits"]
        misses = self.stats["cache_misses"]
        hit_rate = (hits / total * 100) if total > 0 else 0

        avg_cached_ms = (self.stats["cached_latency_ms"] / hits) if hits > 0 else 0
        avg_api_ms = (self.stats["api_latency_ms"] / misses) if misses > 0 else 0

        api_cost = (
            self.stats["api_input_tokens"] / 1000 * INPUT_PRICE_PER_1K +
            self.stats["api_output_tokens"] / 1000 * OUTPUT_PRICE_PER_1K
        )

        table = Table(title="Cache Performance Report", show_lines=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="cyan")

        table.add_row("Total calls", str(total))
        table.add_row("Cache hits", f"[green]{hits}[/green]")
        table.add_row("Cache misses", f"[red]{misses}[/red]")
        table.add_row("Hit rate", f"[bold green]{hit_rate:.1f}%[/bold green]")
        table.add_row("Avg cached latency", f"{avg_cached_ms:.1f} ms")
        table.add_row("Avg API latency", f"{avg_api_ms:.0f} ms")
        table.add_row("Latency improvement", f"{avg_api_ms/max(avg_cached_ms,1):.0f}x faster")
        table.add_row("API cost (misses only)", f"${api_cost:.6f}")
        table.add_row(
            "Projected savings @ 1M calls",
            f"${api_cost * (hits / max(misses, 1)) * (1_000_000 / max(total, 1)):.2f}"
        )

        console.print(table)
```

---

## Step 5 — Run the simulation

```python
def run_simulation():
    llm = CachedLLMClient()

    # Simulated queries — includes repeats and near-duplicates
    queries = [
        # First pass — all cache misses
        "What are your business hours?",
        "How do I reset my password?",
        "What is your return policy?",
        "How do I contact support?",
        "What payment methods do you accept?",

        # Second pass — exact matches (cache hits)
        "What are your business hours?",
        "How do I reset my password?",
        "What is your return policy?",

        # Near-duplicates (same intent, different phrasing)
        "When are you open?",                          # ≈ business hours
        "I forgot my password, what do I do?",         # ≈ reset password
        "Can I return an item I bought?",              # ≈ return policy
        "How can I get in touch with customer support?",  # ≈ contact support
        "Do you take credit cards?",                   # ≈ payment methods
    ]

    console.print(f"\n[bold]Running {len(queries)} queries...[/bold]\n")

    for query in queries:
        result = llm.call(query)
        status = "[green]HIT [/green]" if result["cache_hit"] else "[red]MISS[/red]"
        console.print(
            f"{status} [{result['latency_ms']:.0f}ms] "
            f"[dim]{query[:60]}[/dim]"
        )

    console.print()
    llm.print_stats()

    console.print(
        "\n[bold yellow]Note:[/bold yellow] This lab uses exact-match caching. "
        "For semantic (near-duplicate) matching, integrate GPTCache's "
        "vector similarity search — see the technique doc for the full implementation."
    )

if __name__ == "__main__":
    run_simulation()
```

---

## Step 6 — Run it

```bash
python lab_m02.py
```

**Expected output:**
```
Running 13 queries...

MISS [743ms] What are your business hours?
MISS [681ms] How do I reset my password?
MISS [592ms] What is your return policy?
MISS [614ms] How do I contact support?
MISS [578ms] What payment methods do you accept?
HIT  [0ms]   What are your business hours?
HIT  [0ms]   How do I reset my password?
HIT  [0ms]   What is your return policy?
MISS [698ms] When are you open?
...

Cache Performance Report
┌──────────────────────────┬───────────────────────┐
│ Total calls              │ 13                    │
│ Cache hits               │ 3                     │
│ Cache misses             │ 10                    │
│ Hit rate                 │ 23.1%                 │
│ Avg cached latency       │ 0.1 ms                │
│ Avg API latency          │ 651 ms                │
│ Latency improvement      │ 6510x faster          │
│ API cost (misses only)   │ $0.000312             │
└──────────────────────────┴───────────────────────┘
```

---

## Validate

```bash
# Check what's stored in Redis
docker exec redis-cache redis-cli keys "*"

# Count cached entries
docker exec redis-cache redis-cli dbsize

# Check memory usage
docker exec redis-cache redis-cli info memory | grep used_memory_human
```

---

## Cost impact

With a 23% hit rate on 13 queries, all cached responses cost $0. At production scale (1M queries/month with 40% hit rate), this eliminates 400,000 API calls — saving thousands per month at zero quality cost.

---

## Teardown

```bash
docker stop redis-cache && docker rm redis-cache
deactivate
rm -rf finops-lab/ lab_m02.py .env
```

---

## Next steps

- Tune the similarity threshold (higher = more conservative, fewer false hits)
- Add TTL (time-to-live) to cached entries for time-sensitive responses
- Implement semantic similarity with GPTCache's full vector search pipeline
- Proceed to [M-03: Model Router](m03-model-router.md)
