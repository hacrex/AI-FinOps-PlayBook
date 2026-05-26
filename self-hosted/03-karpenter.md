# 03 — Karpenter

> Idle GPUs are the single largest source of wasted spend in self-hosted AI.

**Category:** Self-Hosted AI FinOps · Technique 03 of 06  
**Tags:** `node-autoscaling` `idle-reduction` `kubernetes`

---

## What it is

Karpenter is a Kubernetes-native node autoscaler that provisions the right GPU instance type for each workload on demand and terminates nodes the moment workloads complete. It eliminates the "always-on" GPU cluster pattern that leaves expensive hardware sitting underutilized between demand spikes.

---

## Why it matters

In self-hosted AI, you pay for GPU time whether or not inference is happening. The classic failure mode is a static cluster provisioned for peak load — sized for the busiest hour of the week but running at 15–20% utilization for most of the day.

```
Peak load: 8× A100s needed for 2 hours/day
Static cluster cost: 8 GPUs × $6/hr × 24 hrs = $1,152/day

With Karpenter:
  Peak (2 hrs): 8 GPUs × $6/hr = $96
  Off-peak (22 hrs): 1 GPU (baseline) × $6/hr = $132
  Daily cost: $228
  Daily saving: $924 (80% reduction)
```

---

## How it works

### Karpenter vs Cluster Autoscaler

Kubernetes ships with Cluster Autoscaler, but it has limitations for AI workloads:

| Feature | Cluster Autoscaler | Karpenter |
|---------|-------------------|-----------|
| Node selection | Predefined node groups | Any instance type, dynamically |
| Provisioning speed | 3–5 minutes | 30–60 seconds |
| GPU awareness | Limited | Native resource request matching |
| Spot instance support | Manual configuration | First-class, with fallback |
| Bin-packing | Limited | Optimized |

Karpenter provisions nodes directly from the cloud provider API, matching the exact GPU type and size needed for each pending pod.

### Core concepts

**NodePool** — defines which instance types and zones Karpenter can use:

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: gpu-inference
spec:
  template:
    metadata:
      labels:
        workload-type: inference
    spec:
      requirements:
        - key: karpenter.k8s.aws/instance-gpu-name
          operator: In
          values: ["a100", "h100", "l4"]        # allow multiple GPU types
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]          # prefer spot, fall back to on-demand
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
      nodeClassRef:
        apiVersion: karpenter.k8s.aws/v1beta1
        kind: EC2NodeClass
        name: gpu-nodeclass
  limits:
    nvidia.com/gpu: 32                           # max GPUs across this pool
  disruption:
    consolidationPolicy: WhenUnderutilized       # terminate idle nodes
    consolidateAfter: 5m                         # wait 5 minutes before consolidating
```

**EC2NodeClass** — AWS-specific configuration:

```yaml
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: gpu-nodeclass
spec:
  amiFamily: AL2
  role: KarpenterNodeRole
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
  instanceStorePolicy: RAID0
  userData: |
    #!/bin/bash
    /etc/eks/bootstrap.sh my-cluster
    # Install NVIDIA drivers
    yum install -y nvidia-driver-latest-dkms
```

### GPU workload pod spec

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-inference
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-inference
  template:
    metadata:
      labels:
        app: vllm-inference
    spec:
      nodeSelector:
        workload-type: inference
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        resources:
          requests:
            nvidia.com/gpu: "1"       # Karpenter provisions a node with exactly this
            memory: "60Gi"
            cpu: "8"
          limits:
            nvidia.com/gpu: "1"
        args:
          - "--model"
          - "meta-llama/Llama-3.1-8B-Instruct"
          - "--gpu-memory-utilization"
          - "0.90"
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```

### Consolidation strategy

Karpenter's consolidation removes underutilized nodes. For AI workloads, tune `consolidateAfter` conservatively — GPU nodes take longer to warm up than CPU nodes:

```yaml
disruption:
  consolidationPolicy: WhenUnderutilized
  consolidateAfter: 10m      # wait 10 minutes — allows for bursty patterns
  budgets:
    - nodes: "0"             # never disrupt during peak hours
      schedule: "0 9 * * 1-5"   # Mon–Fri 9am
      duration: 9h
```

---

## Tools

| Tool | Use |
|------|-----|
| [Karpenter](https://karpenter.sh) | Node autoscaler (AWS EKS native; also supports GCP, Azure) |
| [KEDA](https://keda.sh) | Scale pod replicas based on queue depth or custom metrics |
| [Kubecost](https://kubecost.com) | Per-namespace and per-workload cost attribution |
| [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) | GPU utilization metrics to inform scaling decisions |
| [Prometheus + Grafana](https://prometheus.io) | Monitor node lifecycle, utilization, and idle time |

---

## Example

**Scenario:** A batch inference pipeline processes documents throughout the day with strong peak/off-peak patterns. Previously running a static 4× A100 cluster on EKS.

Traffic pattern analysis:
- 8am–10am: peak, 4 GPUs needed
- 10am–6pm: medium, 2 GPUs needed
- 6pm–8am: near-zero, 0–1 GPU needed

```
Static cluster (before Karpenter):
4 GPUs × $6/hr × 24hr × 30 days = $17,280/month

Dynamic cluster (with Karpenter + WhenUnderutilized):
Estimated GPU-hours:
  Peak (4 GPU × 2hr × 22 weekdays) = 176 GPU-hours
  Medium (2 GPU × 8hr × 22 weekdays) = 352 GPU-hours
  Low (1 GPU × 14hr × 22 weekdays) = 308 GPU-hours
  Weekends minimal: ~100 GPU-hours
  Total: ~936 GPU-hours × $6/hr = $5,616/month

Monthly saving: $11,664 (67% reduction)
```

---

## Implementation checklist

- [ ] Install Karpenter on your EKS/GKE/AKS cluster
- [ ] Define a NodePool with appropriate GPU instance types
- [ ] Set `consolidateAfter` based on your workload's warm-up time
- [ ] Add schedule-based disruption budgets to protect peak hours
- [ ] Configure KEDA to scale pod replicas based on inference queue depth
- [ ] Install Kubecost and validate cost attribution per workload
- [ ] Review Karpenter node provisioning events weekly — tune instance type allowlist

---

## Further reading

- [Karpenter documentation](https://karpenter.sh/docs/)
- [Karpenter on EKS — AWS guide](https://docs.aws.amazon.com/eks/latest/userguide/karpenter.html)
- [Karpenter GPU workloads best practices](https://karpenter.sh/docs/concepts/nodepools/)
- [KEDA documentation](https://keda.sh/docs/)
- [Kubecost GPU cost attribution](https://docs.kubecost.com/using-kubecost/navigating-the-kubecost-ui/cost-allocation/gpu-cost-allocation)

---

**Previous:** [02 — vLLM](02-vllm.md)  
**Next:** [04 — MIG Partitioning](04-mig-partitioning.md)
