# 04 — MIG partitioning

> One H100 can be seven isolated GPU slices. Stop dedicating a full H100 to a small model.

**Category:** Self-Hosted AI FinOps · Technique 04 of 06  
**Tags:** `a100` `h100` `multi-instance-gpu` `gpu-sharing`

---

## What it is

Multi-Instance GPU (MIG) is an NVIDIA feature available on A100 and H100 GPUs that partitions a single physical GPU into up to 7 isolated GPU instances, each with dedicated compute engines, memory, and memory bandwidth. Each MIG instance runs a separate workload with full hardware isolation — unlike time-slicing, which shares resources and can cause interference.

---

## Why it matters

Without MIG, each inference workload occupies an entire GPU — even if that workload only uses 20% of the GPU's compute capacity. A team running five 7B models would require five A100s.

With MIG, a single A100 80GB can run:
- 7× `1g.10gb` instances (10 GB each) — ideal for small models
- 4× `2g.20gb` instances (20 GB each) — medium models
- 2× `3g.40gb` instances (40 GB each) — larger models
- 1× `7g.80gb` instance — full GPU, no partitioning

This directly multiplies the number of models that can run on a single piece of hardware.

---

## How it works

### MIG instance profiles (A100 80GB)

| Profile | VRAM | Compute | Use case |
|---------|------|---------|---------|
| `1g.10gb` | 10 GB | 1/7 of A100 | 7B models at INT4, small classifiers |
| `2g.20gb` | 20 GB | 2/7 of A100 | 7B models at FP16, 13B at INT4 |
| `3g.40gb` | 40 GB | 3/7 of A100 | 13B–30B models |
| `4g.40gb` | 40 GB | 4/7 of A100 | 30B models with higher throughput |
| `7g.80gb` | 80 GB | Full A100 | 70B models |

### Enabling MIG on a node

```bash
# Enable MIG mode (requires node reboot)
sudo nvidia-smi -i 0 -mig 1

# Verify MIG is enabled
nvidia-smi -i 0 --query-gpu=mig.mode.current --format=csv,noheader

# Create 7× 1g.10gb instances on GPU 0
sudo nvidia-smi mig -i 0 -cgi 1g.10gb,1g.10gb,1g.10gb,1g.10gb,1g.10gb,1g.10gb,1g.10gb -C

# Verify instances
nvidia-smi -L
# GPU 0: NVIDIA A100 ...
#   MIG 1g.10gb     Device  0: ...
#   MIG 1g.10gb     Device  1: ...
#   ...
```

### Kubernetes integration with MIG device plugin

NVIDIA provides a device plugin and MIG manager for Kubernetes:

```bash
# Install NVIDIA device plugin with MIG support
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm install nvdp nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin \
  --create-namespace \
  --set migStrategy=mixed

# Install MIG manager (automates MIG configuration on nodes)
helm repo add nvidia https://nvidia.github.io/mig-parted
helm install mig-manager nvidia/nvidia-mig-manager \
  --namespace nvidia-mig-manager \
  --create-namespace
```

Configure which MIG profile to use on each node via label:

```bash
kubectl label node gpu-node-01 \
  nvidia.com/mig.config=all-1g.10gb    # partition into 7 × 1g.10gb
```

### Pod requesting a MIG instance

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: small-model-inference
spec:
  containers:
  - name: inference
    image: vllm/vllm-openai:latest
    resources:
      limits:
        nvidia.com/mig-1g.10gb: "1"    # request one 1g.10gb MIG slice
    args:
      - "--model"
      - "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
      - "--gpu-memory-utilization"
      - "0.85"
```

### Mixed MIG profiles on one node

You can mix profiles on a single GPU when your workloads have different memory requirements:

```bash
# 1× 3g.40gb (for a 13B model) + 2× 2g.20gb (for two 7B models)
sudo nvidia-smi mig -i 0 -cgi 3g.40gb,2g.20gb,2g.20gb -C
```

---

## Tools

| Tool | Use |
|------|-----|
| [NVIDIA MIG Manager](https://github.com/NVIDIA/mig-parted) | Kubernetes-native MIG profile management |
| [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin) | Expose MIG instances as schedulable Kubernetes resources |
| [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) | Per-MIG-instance metrics (utilization, memory, throughput) |
| [Prometheus + Grafana](https://prometheus.io) | Monitor per-instance utilization |

---

## Example

**Scenario:** An ML platform team runs 6 different small-to-medium models for various internal services. Currently using 6× A100 40GB GPUs ($36/hour on cloud), one per model.

Model inventory:
- 3× 7B models (7 GB VRAM each at INT4) → fit in `1g.10gb`
- 2× 13B models (13 GB VRAM each at INT4) → fit in `2g.20gb`
- 1× 30B model (30 GB VRAM at INT4) → needs `3g.40gb`

All 6 models fit on 1× A100 80GB using mixed MIG:
```
3g.40gb (30B model)   → 40 GB used
2g.20gb (13B model)   → 20 GB used
1g.10gb + 1g.10gb (remaining 2× 13B would need larger; reconfigure)
```

Realistic MIG layout for this workload:
- 1× A100 80GB: `3g.40gb` + `2g.20gb` + `2g.20gb` = 6 of 7 slices used
- Move 3× 7B models to a second A100: `1g.10gb` × 3 = 3 of 7 slices used

```
Before MIG: 6× A100 40GB = $36/hour × 24 × 30 = $25,920/month

After MIG: 2× A100 80GB = $24/hour × 24 × 30 = $17,280/month

Monthly saving: $8,640 (33%)
Additional capacity: 4 spare MIG slices available for new models at no extra cost
```

---

## When NOT to use MIG

- Workloads that need the full A100/H100 memory bandwidth (large model training, 70B inference)
- When you need GPU peer-to-peer communication across MIG instances (not supported)
- If your GPU model doesn't support MIG (MIG is only on A100, H100, and A30)

For older GPUs (V100, T4), use time-slicing (less isolation) or CUDA Multi-Process Service (MPS) instead.

---

## Implementation checklist

- [ ] Confirm your GPUs support MIG (A100, H100, or A30)
- [ ] Inventory workloads by VRAM requirement to choose profiles
- [ ] Enable MIG mode on target nodes (requires reboot — plan maintenance window)
- [ ] Install NVIDIA MIG Manager and Device Plugin on the cluster
- [ ] Update pod specs to request MIG resources instead of full GPU
- [ ] Set up per-MIG-instance monitoring with DCGM Exporter
- [ ] Validate inference throughput — MIG instances have proportionally less bandwidth

---

## Further reading

- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/)
- [MIG on Kubernetes — NVIDIA documentation](https://docs.nvidia.com/datacenter/cloud-native/kubernetes/mig-k8s.html)
- [NVIDIA MIG Manager on GitHub](https://github.com/NVIDIA/mig-parted)
- [A100 MIG profiles reference](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/#partitioning)

---

**Previous:** [03 — Karpenter](03-karpenter.md)  
**Next:** [05 — Ray / Kubernetes](05-ray-kubernetes.md)
