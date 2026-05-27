# S-01 — vLLM deployment + GPU metrics

> Deploy a production-grade inference server. Wire it to Prometheus and Grafana. See your GPU in real time.

**Technique:** [vLLM](../../self-hosted/02-vllm.md) + [Observability](../../tools/self-hosted-stack.md)  
**Time:** ~90 minutes  
**Requires:** 1× NVIDIA GPU (T4, A10G, A100, or H100), CUDA 12.x, Docker

---

## Objective

By the end of this lab you will have:
- vLLM serving a Llama 3.1 8B model via OpenAI-compatible API
- DCGM Exporter scraping GPU hardware metrics
- Prometheus storing all metrics
- Grafana dashboard showing GPU utilization, VRAM, throughput, and queue depth
- A load test confirming throughput vs baseline

---

## Prerequisites

```bash
# Verify GPU is available
nvidia-smi

# Verify CUDA version
nvcc --version   # needs CUDA 12.x

# Verify Docker with GPU support
docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
```

You need at least **16 GB VRAM** for Llama 3.1 8B in FP16, or **8 GB** with INT4 quantization.

---

## Setup — Project structure

```bash
mkdir lab-s01 && cd lab-s01

# Create docker-compose and config files
mkdir -p prometheus grafana/provisioning/{datasources,dashboards}
```

---

## Step 1 — Docker Compose stack

Save as `docker-compose.yml`:

```yaml
version: "3.8"

services:

  # ── vLLM inference server ──────────────────────────────────────────
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    command: >
      --model meta-llama/Llama-3.2-1B-Instruct
      --host 0.0.0.0
      --port 8000
      --gpu-memory-utilization 0.85
      --max-num-seqs 64
      --max-model-len 4096
      --enable-prefix-caching
      --disable-log-requests
    ports:
      - "8000:8000"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5

  # ── DCGM Exporter — GPU hardware metrics ──────────────────────────
  dcgm-exporter:
    image: nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04
    container_name: dcgm-exporter
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    cap_add:
      - SYS_ADMIN
    ports:
      - "9400:9400"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  # ── Prometheus ─────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=7d'

  # ── Grafana ────────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:10.4.0
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning

volumes:
  prometheus_data:
  grafana_data:
```

---

## Step 2 — Prometheus config

Save as `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:

  - job_name: 'vllm'
    static_configs:
      - targets: ['vllm:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'dcgm'
    static_configs:
      - targets: ['dcgm-exporter:9400']
    scrape_interval: 15s
```

---

## Step 3 — Grafana auto-provisioning

Save as `grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

---

## Step 4 — Environment file

```bash
cat > .env << 'EOF'
HF_TOKEN=your_huggingface_token_here
EOF
```

Get your HF token at: https://huggingface.co/settings/tokens  
Accept the Llama 3 license at: https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct

> **Note:** For a smaller model with no license gate, replace `meta-llama/Llama-3.2-1B-Instruct` with `microsoft/Phi-3-mini-4k-instruct` in the compose file — no HF token needed.

---

## Step 5 — Start the stack

```bash
docker compose up -d

# Watch vLLM start up (model download + load takes 2–5 minutes)
docker compose logs -f vllm
```

**Wait for:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 6 — Verify vLLM is healthy

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# List available models
curl http://localhost:8000/v1/models | python3 -m json.tool

# Test inference
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.2-1B-Instruct",
    "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
    "max_tokens": 10
  }'
```

**Expected response:**
```json
{
  "choices": [{
    "message": {"role": "assistant", "content": "Four."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 28, "completion_tokens": 3, "total_tokens": 31}
}
```

---

## Step 7 — Run a load test

```bash
pip install locust

cat > locustfile.py << 'EOF'
import json
import random
from locust import HttpUser, task, between

PROMPTS = [
    "Summarize the benefits of cloud computing in 2 sentences.",
    "What is Kubernetes used for?",
    "Explain GPU memory bandwidth in simple terms.",
    "What is the difference between SQL and NoSQL?",
    "Describe what a container image is.",
]

class InferenceUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def infer(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "meta-llama/Llama-3.2-1B-Instruct",
                "messages": [{"role": "user", "content": random.choice(PROMPTS)}],
                "max_tokens": 100,
            },
        )
EOF

# Run: 10 concurrent users, 60 seconds
locust --headless -u 10 -r 2 -t 60s \
  --host http://localhost:8000 \
  --html load-test-report.html
```

---

## Step 8 — Set up Grafana dashboard

1. Open **http://localhost:3000** (admin / admin)
2. Go to **Dashboards → Import**
3. Enter dashboard ID **12239** (NVIDIA DCGM Exporter Dashboard) → Load
4. Select **Prometheus** as data source → Import

**Key panels to watch during load test:**
- GPU Utilization (%) — should rise to 80–95% under load
- FB Memory Used (VRAM) — shows KV cache growth
- SM Clock — GPU clock speed under inference load

**Create a vLLM panel manually:**

In Grafana → New Dashboard → Add Panel:

```promql
# Requests per second
rate(vllm:request_success_total[1m])

# Queue depth (waiting requests)
vllm:num_waiting_seqs

# KV cache utilization
vllm:gpu_cache_usage_perc

# Time to first token (p95)
histogram_quantile(0.95, rate(vllm:time_to_first_token_seconds_bucket[5m]))
```

---

## Step 9 — Check vLLM metrics directly

```bash
# View raw metrics
curl -s http://localhost:8000/metrics | grep vllm | head -30

# Key metrics to check
curl -s http://localhost:8000/metrics | grep -E \
  "vllm:(gpu_cache|num_running|num_waiting|request_throughput)"
```

**Expected output:**
```
vllm:gpu_cache_usage_perc{model_name="meta-llama/Llama-3.2-1B-Instruct"} 0.342
vllm:num_running_seqs{model_name="meta-llama/Llama-3.2-1B-Instruct"} 8
vllm:num_waiting_seqs{model_name="meta-llama/Llama-3.2-1B-Instruct"} 0
vllm:request_throughput{model_name="meta-llama/Llama-3.2-1B-Instruct"} 14.2
```

---

## Validate

- [ ] `curl localhost:8000/health` returns `{"status":"ok"}`
- [ ] Inference API returns valid responses
- [ ] Prometheus at `localhost:9090` shows `vllm` and `dcgm` targets as UP
- [ ] Grafana DCGM dashboard shows GPU utilization rising under load test
- [ ] Load test shows > 10 req/s throughput on a T4 or better

---

## Cost impact

vLLM's continuous batching typically achieves **3–8× higher throughput** than HuggingFace generate() on the same hardware. Fewer GPUs needed for the same workload = direct infrastructure cost reduction. A T4 on AWS ($0.526/hr) running vLLM can replace 3–4 naive inference servers — saving $1.05–$1.58/hr or ~$760–$1,137/month.

---

## Teardown

```bash
docker compose down -v

# Remove model cache if disk space needed
rm -rf ~/.cache/huggingface/hub/models--meta-llama*
```

---

## Next steps

- Enable `--enable-prefix-caching` and measure KV cache hit rate on repeated system prompts
- Try tensor parallelism across 2 GPUs: add `--tensor-parallel-size 2`
- Proceed to [S-02: Quantization Benchmark](s02-quantization-bench.md)
