# 05 — Ray / Kubernetes

> Prevent scheduling fragmentation. Keep GPUs working, not waiting.

**Category:** Self-Hosted AI FinOps · Technique 05 of 06  
**Tags:** `ray-serve` `kubernetes` `workload-scheduling`

---

## What it is

Ray and Kubernetes are complementary orchestration layers that eliminate scheduling fragmentation in GPU clusters — ensuring that GPUs are continuously utilized rather than sitting idle between jobs, waiting for co-located resources, or blocked by inefficient scheduling.

- **Ray Serve** handles distributed inference natively in Python: model parallelism, pipeline parallelism, autoscaling, and batching with minimal overhead.
- **Kubernetes** manages GPU scheduling, resource quotas, and bin-packing at the cluster level — ensuring workloads land on nodes that actually have capacity.

---

## Why it matters

Without proper orchestration, GPU clusters suffer from:

**Scheduling fragmentation** — 4 GPUs needed, only 3 available on any single node → jobs queue indefinitely while GPUs sit idle on different nodes.

**Gang scheduling failures** — distributed training and pipeline inference require multiple GPUs to start simultaneously. Without coordination, partial resource allocation blocks the whole job.

**Poor bin-packing** — multiple small workloads placed on separate nodes leave GPUs mostly idle instead of co-located on fewer nodes.

**No autoscaling** — static replica counts mean over-provisioning for off-peak or under-provisioning for peak, neither of which is cost-efficient.

---

## How it works

### Ray Serve for inference

Ray Serve provides a deployment abstraction with built-in autoscaling, batching, and routing:

```python
import ray
from ray import serve
from vllm import LLM, SamplingParams

@serve.deployment(
    num_replicas=2,
    ray_actor_options={"num_gpus": 1},
    autoscaling_config={
        "min_replicas": 1,
        "max_replicas": 8,
        "target_num_ongoing_requests_per_replica": 10,
        "upscale_delay_s": 30,
        "downscale_delay_s": 300,   # slow to scale down — GPU warm-up is expensive
    }
)
class LlamaInference:
    def __init__(self):
        self.llm = LLM(
            model="meta-llama/Llama-3.1-8B-Instruct",
            gpu_memory_utilization=0.90,
        )

    async def __call__(self, request):
        data = await request.json()
        sampling_params = SamplingParams(
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 512),
        )
        outputs = self.llm.generate([data["prompt"]], sampling_params)
        return {"text": outputs[0].outputs[0].text}

app = LlamaInference.bind()
```

**Deploy:**
```bash
serve run inference:app --host 0.0.0.0 --port 8000
```

### Pipeline parallelism with Ray

For large models that don't fit on a single GPU, Ray handles pipeline-parallel deployment across multiple GPUs:

```python
@serve.deployment(
    num_replicas=1,
    ray_actor_options={"num_gpus": 4},  # 4 GPUs per replica for 70B model
)
class Llama70BInference:
    def __init__(self):
        self.llm = LLM(
            model="meta-llama/Llama-3.1-70B-Instruct",
            tensor_parallel_size=4,
            gpu_memory_utilization=0.85,
        )
```

### Kubernetes GPU scheduling

**Request GPUs explicitly** — Kubernetes won't schedule on a GPU node unless the resource is declared:

```yaml
resources:
  requests:
    nvidia.com/gpu: "1"
  limits:
    nvidia.com/gpu: "1"
```

**Use node affinity for GPU type selection:**

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: nvidia.com/gpu.product
          operator: In
          values:
          - NVIDIA-A100-SXM4-80GB
          - NVIDIA-H100-SXM5-80GB
```

**Bin-packing with pod topology spread:**

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: inference
```

**Resource quotas per namespace** — enforce GPU limits per team:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-gpu-quota
  namespace: team-ml
spec:
  hard:
    requests.nvidia.com/gpu: "8"    # max 8 GPUs for this team
    limits.nvidia.com/gpu: "8"
```

### KEDA for queue-based autoscaling

Scale inference replicas based on actual request queue depth, not arbitrary CPU/memory metrics:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: inference-scaler
spec:
  scaleTargetRef:
    name: vllm-inference
  pollingInterval: 15
  cooldownPeriod: 300
  minReplicaCount: 1
  maxReplicaCount: 8
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: vllm_num_waiting_seqs
      query: sum(vllm:num_waiting_seqs{job="vllm"})
      threshold: "5"      # scale up when queue depth > 5
```

---

## Tools

| Tool | Use |
|------|-----|
| [Ray Serve](https://docs.ray.io/en/latest/serve/index.html) | Distributed inference with autoscaling |
| [KubeRay](https://ray-project.github.io/kuberay/) | Run Ray clusters on Kubernetes |
| [KEDA](https://keda.sh) | Queue-depth-based pod autoscaling |
| [Volcano](https://volcano.sh) | Gang scheduling for distributed training jobs |
| [Kubecost](https://kubecost.com) | Per-workload GPU cost attribution |
| [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) | GPU utilization metrics for scheduling decisions |

---

## Example

**Scenario:** A team runs batch document processing with variable load — quiet nights, peak during business hours. Static deployment: 4 replicas (4 GPUs) running 24/7.

```
Static deployment:
4 GPUs × $6/hr × 24hr × 30 days = $17,280/month
Average GPU utilization: 35% (idle most nights and weekends)

With Ray Serve autoscaling (min 1 replica, max 6):
  Estimated actual GPU-hours consumed: ~1,800 GPU-hours/month
  (vs 2,880 GPU-hours in static config)
  Cost: 1,800 × $6 = $10,800/month

Monthly saving: $6,480 (37.5%)
Peak performance: unchanged — scales to 6 GPUs during business hours
```

---

## Implementation checklist

- [ ] Deploy KubeRay operator on your cluster
- [ ] Migrate inference services to Ray Serve deployments with autoscaling config
- [ ] Configure `downscale_delay_s` conservatively (≥5 minutes for GPU workloads)
- [ ] Install KEDA and set up queue-depth triggers for your inference services
- [ ] Add resource quotas per namespace to enforce team GPU limits
- [ ] Install Kubecost and validate per-workload cost attribution
- [ ] Set up Volcano for any distributed training gang-scheduling requirements

---

## Further reading

- [Ray Serve documentation](https://docs.ray.io/en/latest/serve/index.html)
- [KubeRay on GitHub](https://github.com/ray-project/kuberay)
- [KEDA GPU scaling patterns](https://keda.sh/docs/2.13/scalers/prometheus/)
- [Kubernetes GPU scheduling guide](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [Volcano gang scheduling](https://volcano.sh/en/docs/)

---

**Previous:** [04 — MIG Partitioning](04-mig-partitioning.md)  
**Next:** [06 — Spot GPU Optimization](06-spot-gpu.md)
