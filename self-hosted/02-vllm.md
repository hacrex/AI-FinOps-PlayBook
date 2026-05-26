# 02 — vLLM

> More requests per GPU. Fewer GPUs per workload.

**Category:** Self-Hosted AI FinOps · Technique 02 of 06  
**Tags:** `continuous-batching` `pagedattention` `gpu-utilization`

---

## What it is

vLLM is a high-throughput inference engine for large language models. Its core innovation — PagedAttention — manages the KV cache like virtual memory in an OS, enabling multiple requests to share GPU memory efficiently and serving dramatically more requests per second than naive inference servers.

---

## Why it matters

In self-hosted AI, GPU cost is fixed per hour regardless of utilization. A GPU serving 5 requests per second costs the same as one serving 50 requests per second. vLLM's throughput improvements translate directly into fewer GPUs needed to serve the same load — a direct cost reduction.

Naive inference servers (including basic Hugging Face `generate()`) suffer from:
- **Memory waste:** Allocate maximum context length for every request upfront, even if the response is short
- **Sequential processing:** Serve one request at a time or with inefficient static batching
- **KV cache fragmentation:** Memory freed between requests cannot be reused efficiently

vLLM solves all three.

---

## How it works

### PagedAttention

The KV (key-value) cache stores attention states computed during generation. In naive systems, this is pre-allocated as a contiguous block per request — leading to fragmentation and waste.

PagedAttention divides the KV cache into fixed-size pages (like OS virtual memory pages) and allocates them dynamically as generation proceeds. Pages are:
- Allocated on demand — no upfront worst-case reservation
- Shared across requests with identical prefixes (prompt caching)
- Freed immediately when a request completes

This enables 2–4x more concurrent requests on the same GPU compared to HuggingFace `generate()`.

### Continuous batching

Naive static batching waits for a batch to fill before processing, introducing latency. Continuous batching processes a request as soon as GPU capacity is available — mixing in-flight requests at the token level:

```
Static batching:      [req1 req2 req3 ----] → wait → [req4 req5 req6 ----]
Continuous batching:  [req1 req2 req3 req4] → req1 done → [req5 req2 req3 req4] → ...
```

This keeps GPU utilization at 90–95% continuously rather than the 40–60% typical of static batching.

### Deploying vLLM

**Basic server:**
```bash
pip install vllm

vllm serve meta-llama/Llama-3.1-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 256 \
  --max-model-len 8192
```

**With tensor parallelism across multiple GPUs:**
```bash
vllm serve meta-llama/Llama-3.1-70B-Instruct \
  --tensor-parallel-size 4 \    # spread across 4 GPUs
  --gpu-memory-utilization 0.85 \
  --max-num-seqs 512
```

**OpenAI-compatible API:**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-required"  # vLLM doesn't enforce API keys by default
)

response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Summarize this document: ..."}],
    max_tokens=512,
)
```

### Key configuration parameters

| Parameter | What it controls | Guidance |
|-----------|-----------------|---------|
| `--gpu-memory-utilization` | Fraction of VRAM allocated to vLLM | 0.85–0.90; leave headroom for OS |
| `--max-num-seqs` | Max concurrent requests | Start at 256; increase if GPU isn't saturated |
| `--max-model-len` | Max context length | Set to your actual use case — not model maximum |
| `--tensor-parallel-size` | Number of GPUs to shard across | Match to GPU count for multi-GPU models |
| `--enable-prefix-caching` | Cache common prompt prefixes | Enable for workloads with shared system prompts |

---

## Tools

| Tool | Use |
|------|-----|
| [vLLM](https://github.com/vllm-project/vllm) | Primary inference engine |
| [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) | GPU utilization metrics from vLLM |
| [Prometheus](https://prometheus.io) | Scrape vLLM `/metrics` endpoint |
| [Grafana](https://grafana.com) | Dashboard for throughput, queue depth, GPU utilization |
| [Locust](https://locust.io) | Load test to find optimal `--max-num-seqs` for your workload |

### vLLM Prometheus metrics

vLLM exposes metrics at `/metrics` — key ones to track:

```
vllm:gpu_cache_usage_perc          # KV cache utilization (target: 70–90%)
vllm:num_running_seqs              # Current concurrent requests
vllm:num_waiting_seqs              # Queue depth (should be near 0 at steady state)
vllm:request_throughput            # Requests per second
vllm:time_to_first_token_seconds   # TTFT latency (p50, p95, p99)
```

---

## Example

**Scenario:** A team serves a 7B instruction model for a high-volume document processing pipeline. Currently using a Hugging Face `generate()` server on 1× A100 80GB.

```
Baseline (HF generate, static batching):
  Throughput: ~8 requests/second
  GPU utilization: ~45%
  To handle 50 req/s peak: need 7× A100 = $42/hour

After vLLM with continuous batching:
  Throughput: ~65 requests/second (same GPU)
  GPU utilization: ~88%
  To handle 50 req/s peak: 1× A100 is sufficient = $6/hour

Monthly saving (at 24/7 operation):
  $42/hr vs $6/hr → $36/hr × 24 × 30 = $25,920/month saved
  (Or: redeploy the freed GPUs to other workloads)
```

---

## Implementation checklist

- [ ] Install vLLM and test with your target model
- [ ] Set `--gpu-memory-utilization` to 0.85–0.90 (don't go higher — OOM risk)
- [ ] Enable `--enable-prefix-caching` if your workload has shared system prompts
- [ ] Configure Prometheus scraping of `/metrics`
- [ ] Build a Grafana dashboard for throughput, KV cache utilization, and queue depth
- [ ] Load test with Locust to find your actual peak throughput and right-size your GPU fleet

---

## Further reading

- [vLLM documentation](https://docs.vllm.ai)
- [PagedAttention paper](https://arxiv.org/abs/2309.06180)
- [vLLM blog: High-throughput LLM serving](https://blog.vllm.ai/2023/06/20/vllm.html)
- [vLLM performance benchmarks](https://docs.vllm.ai/en/latest/performance/benchmarks.html)

---

**Previous:** [01 — Quantization](01-quantization.md)  
**Next:** [03 — Karpenter](03-karpenter.md)
