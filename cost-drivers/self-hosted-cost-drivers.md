# Cost drivers — Self-Hosted AI (GPU)

> In self-hosted AI, cost is driven by GPU hours — whether your hardware is busy or sitting idle.

---

## How self-hosted GPU billing works

Unlike managed APIs, there is no per-token billing. You pay for the cluster regardless of utilization:

```
Monthly cost = GPUs provisioned × hours running × price per GPU·hour

A GPU sitting at 5% utilization costs the same as one at 95% utilization.
The optimization goal is to maximize utilization and minimize idle time.
```

---

## The seven GPU cost drivers

### 1. Idle GPUs

**What it is:** GPUs that are provisioned but not serving inference requests — between jobs, during off-peak hours, or due to static cluster sizing.

**Impact:** The single largest source of wasted spend in self-hosted AI. A cluster sized for peak that runs at 20% average utilization is paying for 5× the needed capacity.

**Example:**
```
8× A100s sized for peak, 20% average utilization
Actual useful work: equivalent to 1.6 GPUs
Waste: 6.4 GPUs × $6/hr × 720 hrs = $27,648/month wasted
```

**Fix:** [Karpenter](../self-hosted/03-karpenter.md) — scale down idle nodes automatically

---

### 2. Wrong GPU type for the workload

**What it is:** Using a high-end GPU (H100, A100) for a workload that would run equally well on a lower-tier GPU (L4, A10G, T4).

**Impact:** H100 at ~$12/hr for a workload that runs fine on an L4 at ~$0.80/hr is a 15× overspend. GPU selection should match model size and throughput requirements.

**GPU selection guide:**

| Workload | Recommended | Avoid |
|----------|------------|-------|
| 7B model serving, low traffic | L4 (24GB) or A10G | H100 |
| 13B model serving | A100 40GB | H100 (overkill) |
| 70B model serving | A100 80GB or H100 | Multiple smaller GPUs |
| Batch embedding generation | T4 or L4 | A100/H100 |
| Model fine-tuning | A100 80GB | T4 (too slow) |
| Large-scale training | H100 | A100 (slower interconnect) |

**Fix:** Right-size GPU type; use [MIG Partitioning](../self-hosted/04-mig-partitioning.md) on A100/H100 for smaller workloads

---

### 3. Poor batching

**What it is:** Serving one request at a time, or using static batching that wastes GPU cycles between batches.

**Impact:** A GPU serving 5 requests/second with naive inference costs the same as one serving 50 requests/second with continuous batching. The difference is 10× more GPUs needed for the same throughput.

**Fix:** [vLLM](../self-hosted/02-vllm.md) — continuous batching with PagedAttention

---

### 4. VRAM fragmentation

**What it is:** KV cache memory allocated inefficiently, leaving VRAM space that can't be used for additional concurrent requests.

**Impact:** Naive inference servers pre-allocate worst-case KV cache for each request. A GPU with 80GB VRAM might only be able to serve 4 concurrent requests when it could serve 20+ with proper memory management.

**Fix:** [vLLM](../self-hosted/02-vllm.md) — PagedAttention manages KV cache like virtual memory

---

### 5. No autoscaling

**What it is:** A fixed number of GPU replicas that doesn't adapt to traffic patterns.

**Impact:** Static clusters must be sized for peak. Off-peak periods (nights, weekends) waste the full provisioned capacity. For workloads with 5:1 peak-to-trough ratios, this is 80% waste during troughs.

**Fix:** [Karpenter](../self-hosted/03-karpenter.md) + [Ray / Kubernetes](../self-hosted/05-ray-kubernetes.md) — dynamic scaling based on queue depth

---

### 6. Non-quantized models

**What it is:** Running models at full FP16 precision when INT8 or INT4 would serve the workload with acceptable quality.

**Impact:** A 70B FP16 model needs 8× A100 80GB GPUs. The same model quantized to INT4 needs 2× A100 80GB — a 4× hardware cost reduction with <2% quality loss on most tasks.

**Example:**
```
70B FP16: 8× A100 80GB = $48/hr = $34,560/month
70B INT4: 2× A100 80GB = $12/hr = $8,640/month
Monthly saving: $25,920
```

**Fix:** [Quantization](../self-hosted/01-quantization.md)

---

### 7. Scheduling inefficiency

**What it is:** Workloads placed on suboptimal nodes, gang scheduling failures, and bin-packing failures that leave GPUs fragmented across nodes.

**Impact:** 4-GPU jobs that can't start because 4 GPUs aren't available on any single node — even though 8 GPUs are free across the cluster. GPUs sit idle while jobs queue.

**Fix:** [Ray / Kubernetes](../self-hosted/05-ray-kubernetes.md) — bin-packing, gang scheduling, and Volcano for distributed jobs

---

## Cost driver summary

| Driver | Typical waste | Primary fix |
|--------|--------------|-------------|
| Idle GPUs | 50–80% of cost | Karpenter autoscaling |
| Wrong GPU type | 2–15× overspend | Right-sizing |
| Poor batching | 5–10× more GPUs than needed | vLLM |
| VRAM fragmentation | 50–75% less concurrent capacity | vLLM PagedAttention |
| No autoscaling | 60–80% waste off-peak | Karpenter + KEDA |
| Non-quantized models | 2–4× more GPUs than needed | Quantization |
| Scheduling inefficiency | 20–40% idle capacity | Ray / Kubernetes |

---

## Where to start

If you're new to self-hosted AI FinOps, this order maximizes early impact:

1. **Measure first** — deploy DCGM Exporter + Prometheus + Grafana. Get GPU utilization visibility.
2. **Quantize** — if utilization is high but you're paying for too many GPUs, quantize first. Biggest single reduction.
3. **vLLM** — if throughput is the bottleneck, switching to vLLM is usually the highest-ROI change.
4. **Karpenter** — if you have variable load and idle clusters, add autoscaling.
5. **MIG** — if you have A100/H100 and many small workloads, partition.
6. **Spot** — for batch/non-realtime workloads, switch to spot instances.

---

## Further reading

- [Self-Hosted AI FinOps — 6 techniques](../self-hosted/)
- [Cost model comparison](../comparison/cost-model.md)
- [Managed cost drivers](managed-cost-drivers.md)
