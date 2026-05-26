# Self-Hosted AI FinOps — Tools stack

> The self-hosted GPU observability stack gives you visibility into hardware utilization, inference throughput, and infrastructure cost — the layer that managed API tools cannot reach.

---

## Stack overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Applications                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Inference Layer (vLLM)                        │
│         continuous batching · PagedAttention · /metrics         │
└───────────────┬───────────────────────────────┬────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│  GPU Hardware Layer      │    │  Kubernetes Orchestration    │
│  DCGM Exporter           │    │  Karpenter · KEDA · Kubecost │
│  (per-GPU metrics)       │    │  (scheduling · autoscaling)  │
└──────────┬───────────────┘    └──────────────┬───────────────┘
           │                                   │
           └───────────────┬───────────────────┘
                           ▼
           ┌──────────────────────────────────┐
           │       Prometheus                 │
           │  (metrics storage + alerting)    │
           └──────────────────┬───────────────┘
                              ▼
           ┌──────────────────────────────────┐
           │       Grafana                    │
           │  (dashboards · alerts · cost)    │
           └──────────────────────────────────┘
```

---

## Tool reference

### DCGM Exporter — GPU metrics

**Role:** Exports NVIDIA GPU hardware metrics to Prometheus. The foundational telemetry layer for all GPU observability.

**Why it's essential:** Without DCGM, you're flying blind on GPU health. You cannot see utilization, VRAM usage, temperature, or power draw — all of which directly affect cost and reliability.

**Key metrics exposed:**

| Metric | What it tells you |
|--------|------------------|
| `DCGM_FI_DEV_GPU_UTIL` | GPU compute utilization % |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | Memory bandwidth utilization % |
| `DCGM_FI_DEV_FB_USED` | VRAM used (MB) |
| `DCGM_FI_DEV_FB_FREE` | VRAM free (MB) |
| `DCGM_FI_DEV_POWER_USAGE` | Power draw (watts) |
| `DCGM_FI_DEV_GPU_TEMP` | GPU temperature (°C) |
| `DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL` | NVLink bandwidth (for multi-GPU) |

**Deploy on Kubernetes:**
```bash
helm repo add gpu-helm-charts \
  https://nvidia.github.io/dcgm-exporter/helm-charts

helm install dcgm-exporter gpu-helm-charts/dcgm-exporter \
  --namespace monitoring \
  --create-namespace \
  --set serviceMonitor.enabled=true \
  --set serviceMonitor.interval=15s
```

**Links:**
- [GitHub](https://github.com/NVIDIA/dcgm-exporter)
- [DCGM documentation](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-user-guide/index.html)

---

### Prometheus — Metrics storage

**Role:** Time-series database that scrapes and stores metrics from DCGM Exporter, vLLM, Karpenter, and Kubernetes. The central data store for all GPU observability.

**Why it's the backbone:** Every other tool in this stack either writes to Prometheus (DCGM, vLLM) or reads from it (Grafana, KEDA, alerting). Without Prometheus, there is no metrics pipeline.

**Key scrape targets for AI FinOps:**

```yaml
# prometheus.yml scrape config
scrape_configs:
  - job_name: 'dcgm'
    static_configs:
      - targets: ['dcgm-exporter:9400']
    scrape_interval: 15s

  - job_name: 'vllm'
    static_configs:
      - targets: ['vllm-service:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s

  - job_name: 'karpenter'
    static_configs:
      - targets: ['karpenter:8080']
    scrape_interval: 30s

  - job_name: 'kubecost'
    static_configs:
      - targets: ['kubecost-cost-analyzer:9003']
    scrape_interval: 60s
```

**Useful PromQL queries:**

```promql
# Average GPU utilization across all nodes
avg(DCGM_FI_DEV_GPU_UTIL) by (instance)

# VRAM utilization percentage
DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE) * 100

# vLLM requests per second
rate(vllm:request_success_total[5m])

# vLLM queue depth (waiting requests)
vllm:num_waiting_seqs

# GPU idle time (utilization < 10%)
count(DCGM_FI_DEV_GPU_UTIL < 10) by (instance)
```

**Deploy with kube-prometheus-stack:**
```bash
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts

helm install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.retentionSize=50GB
```

**Links:**
- [prometheus.io](https://prometheus.io)
- [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)

---

### Grafana — Dashboards and alerting

**Role:** Visualization layer for all Prometheus metrics. Build GPU utilization dashboards, cost attribution views, and inference throughput tracking.

**Why Grafana:** Industry-standard for infrastructure dashboards. NVIDIA and vLLM both publish pre-built Grafana dashboards you can import directly.

**Essential dashboards for AI FinOps:**

| Dashboard | What it shows | Import ID |
|-----------|--------------|-----------|
| NVIDIA DCGM Exporter | Per-GPU utilization, VRAM, temperature, power | 12239 |
| vLLM Stats | Throughput, latency, queue depth, KV cache | community |
| Kubernetes GPU | GPU allocation per namespace/pod | 15572 |
| Kubecost | Cost per workload and namespace | built-in |

**Import DCGM dashboard:**
```bash
# Via Grafana UI: Dashboards → Import → ID 12239
# Or via API:
curl -X POST http://grafana:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d '{"dashboard": {"id": 12239}, "overwrite": true}'
```

**Key alerts to configure:**

```yaml
# GPU utilization alert — low utilization = wasted spend
- alert: GPUUtilizationLow
  expr: avg_over_time(DCGM_FI_DEV_GPU_UTIL[30m]) < 20
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "GPU {{ $labels.instance }} utilization below 20% for 30 minutes"
    description: "Consider scaling down or consolidating workloads"

# vLLM queue depth — requests backing up
- alert: InferenceQueueDepthHigh
  expr: vllm:num_waiting_seqs > 20
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "vLLM request queue depth {{ $value }} — inference falling behind"

# VRAM near capacity
- alert: VRAMNearCapacity
  expr: DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE) > 0.92
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "GPU VRAM above 92% on {{ $labels.instance }}"
```

**Links:**
- [grafana.com](https://grafana.com)
- [NVIDIA DCGM dashboard](https://grafana.com/grafana/dashboards/12239)

---

### vLLM — Inference engine

**Role:** High-throughput LLM inference server. The primary inference engine for self-hosted models — also the primary source of per-request throughput and latency metrics.

**Why vLLM:** PagedAttention + continuous batching achieves 2–10× higher throughput than naive HuggingFace inference on the same hardware. This directly reduces the number of GPUs needed.

**Key metrics vLLM exposes at `/metrics`:**

```
vllm:gpu_cache_usage_perc          # KV cache fill % (target 70–90%)
vllm:num_running_seqs              # Concurrent active requests
vllm:num_waiting_seqs              # Queue depth (should be ~0 steady state)
vllm:request_throughput            # Requests/second
vllm:time_to_first_token_seconds   # TTFT (p50, p95, p99)
vllm:time_per_output_token_seconds # Per-token generation latency
vllm:prompt_tokens_total           # Cumulative input tokens
vllm:generation_tokens_total       # Cumulative output tokens
```

**Deploy:**
```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 256 \
  --enable-prefix-caching \
  --max-model-len 8192
```

**Links:**
- [docs.vllm.ai](https://docs.vllm.ai)
- [GitHub](https://github.com/vllm-project/vllm)
- Technique doc: [02 — vLLM](../self-hosted/02-vllm.md)

---

### Karpenter — Node autoscaler

**Role:** Provisions and terminates GPU nodes dynamically based on pending pod demand. Eliminates idle GPU clusters between demand spikes.

**Why Karpenter:** Cluster Autoscaler is limited to predefined node groups. Karpenter selects the exact GPU instance type needed for each pending workload — including spot instances — and terminates nodes within minutes of workload completion.

**Key metrics:**
```promql
# Nodes provisioned by Karpenter
karpenter_nodes_total{state="ready"}

# Node termination events (consolidation working correctly)
rate(karpenter_nodes_terminated_total[1h])

# Provisioning latency
karpenter_provisioner_scheduling_duration_seconds
```

**Links:**
- [karpenter.sh](https://karpenter.sh)
- Technique doc: [03 — Karpenter](../self-hosted/03-karpenter.md)

---

### Kubecost — Cost attribution

**Role:** Kubernetes-native cost allocation. Breaks down GPU and infrastructure cost by namespace, deployment, team, and label — making chargeback and showback possible at the workload level.

**Why Kubecost:** Raw cloud billing gives you total spend. Kubecost maps that spend to individual Kubernetes workloads — so you know exactly which model, team, or feature is responsible for each dollar of GPU cost.

**Key features:**
- Per-namespace cost breakdown
- GPU cost allocation (nvidia.com/gpu resource costs)
- Cost over time trending
- Budget alerts per namespace
- Savings recommendations (rightsizing, spot migration)

**Deploy:**
```bash
helm repo add kubecost https://kubecost.github.io/cost-analyzer/

helm install kubecost kubecost/cost-analyzer \
  --namespace kubecost \
  --create-namespace \
  --set kubecostToken="your-token" \
  --set prometheus.nodeExporter.enabled=true
```

**GPU cost query (API):**
```bash
curl "http://kubecost:9090/model/allocation?window=7d&aggregate=namespace&includeIdle=true" \
  | jq '.data[0] | to_entries[] | {namespace: .key, gpu_cost: .value.gpuCost}'
```

**Links:**
- [kubecost.com](https://kubecost.com)
- [GPU cost allocation docs](https://docs.kubecost.com/using-kubecost/navigating-the-kubecost-ui/cost-allocation/gpu-cost-allocation)

---

## Tool selection guide

| Need | Primary tool | Alternative |
|------|-------------|------------|
| GPU hardware metrics | DCGM Exporter | node-exporter (limited GPU) |
| Metrics storage | Prometheus | Victoria Metrics, Thanos |
| Dashboards | Grafana | Datadog, New Relic |
| Inference engine | vLLM | TGI (HuggingFace), TensorRT-LLM |
| Node autoscaling | Karpenter | Cluster Autoscaler |
| Pod autoscaling | KEDA | HPA (less flexible) |
| Cost attribution | Kubecost | OpenCost (open-source Kubecost) |
| Distributed inference | Ray Serve | Triton Inference Server |

---

## Minimum viable observability stack

If you're starting from scratch, deploy in this order:

1. **DCGM Exporter** — GPU hardware visibility (day 1)
2. **Prometheus** — metrics storage (day 1)
3. **Grafana + DCGM dashboard** — GPU utilization visibility (day 1)
4. **vLLM `/metrics` scraping** — inference performance visibility (day 2)
5. **Kubecost** — cost attribution per workload (week 1)
6. **Grafana alerts** — GPU idle, VRAM, queue depth (week 1)
7. **Karpenter** — autoscaling (week 2)

---

## Further reading

- [Self-Hosted AI FinOps — 6 techniques](../self-hosted/)
- [Managed tools stack](managed-stack.md)
- [NVIDIA GPU monitoring best practices](https://docs.nvidia.com/datacenter/dcgm/latest/)
- [vLLM production deployment guide](https://docs.vllm.ai/en/latest/serving/deploying_with_k8s.html)
- [Kubecost GPU cost allocation](https://docs.kubecost.com/using-kubecost/navigating-the-kubecost-ui/cost-allocation/gpu-cost-allocation)
