# 06 — Spot GPU optimization

> 60–80% compute savings on workloads that can tolerate interruption.

**Category:** Self-Hosted AI FinOps · Technique 06 of 06  
**Tags:** `spot-instances` `preemptible` `60-80-savings`

---

## What it is

Spot GPU instances (AWS) and Preemptible VMs (GCP) offer spare cloud GPU capacity at 60–80% discount compared to on-demand pricing. The trade-off: the cloud provider can reclaim the instance with 2 minutes' notice when demand for on-demand capacity increases.

For the right workload categories, this trade-off is highly favorable — the savings are enormous and the interruption risk is manageable with the right engineering patterns.

---

## Why it matters

On-demand GPU instances are expensive. Spot pricing makes GPU workloads viable that otherwise wouldn't be:

| Instance | On-demand | Spot (approx) | Saving |
|----------|-----------|---------------|--------|
| p4d.24xlarge (8× A100) | $32.77/hr | ~$9.83/hr | 70% |
| p3.2xlarge (1× V100) | $3.06/hr | ~$0.92/hr | 70% |
| g5.xlarge (1× A10G) | $1.01/hr | ~$0.30/hr | 70% |
| GCP A100 80GB | $3.67/hr | ~$1.10/hr | 70% |

For a team running 4× A100 GPUs 24/7:
```
On-demand: 4 × $6/hr × 24 × 30 = $17,280/month
Spot:       4 × $1.80/hr × 24 × 30 = $5,184/month
Monthly saving: $12,096
```

---

## How it works

### Which workloads are spot-safe

**Safe for spot** (interruption-tolerant):
- Batch inference jobs — process documents, embeddings, classifications in bulk
- Offline embeddings generation — index builds, dataset preprocessing
- Model fine-tuning and training (with checkpointing)
- Non-realtime pipelines — ETL, report generation, model evaluation
- Dev/test inference environments

**Not safe for spot** (require on-demand):
- Realtime user-facing inference (chatbots, copilots)
- Streaming inference with strict SLA requirements
- Jobs with no checkpoint/resume capability

### Design for interruption

**Checkpoint frequently** — the most important pattern:

```python
import torch
import signal
import sys

class CheckpointingTrainer:
    def __init__(self, model, checkpoint_dir: str):
        self.model = model
        self.checkpoint_dir = checkpoint_dir
        self.current_step = self.load_latest_checkpoint()
        
        # Handle SIGTERM (spot interruption signal)
        signal.signal(signal.SIGTERM, self.handle_interruption)
    
    def handle_interruption(self, signum, frame):
        print(f"Spot interruption detected at step {self.current_step}. Saving checkpoint...")
        self.save_checkpoint()
        sys.exit(0)
    
    def save_checkpoint(self):
        torch.save({
            "step": self.current_step,
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
        }, f"{self.checkpoint_dir}/checkpoint_{self.current_step}.pt")
    
    def load_latest_checkpoint(self) -> int:
        checkpoints = sorted(Path(self.checkpoint_dir).glob("checkpoint_*.pt"))
        if not checkpoints:
            return 0
        ckpt = torch.load(checkpoints[-1])
        self.model.load_state_dict(ckpt["model_state"])
        return ckpt["step"]
```

**Use durable storage for in-progress work** — write intermediate results to S3/GCS, not local disk:

```python
import boto3

s3 = boto3.client("s3")

def process_document_batch(batch: list[str], batch_id: str) -> None:
    results = []
    for doc in batch:
        result = model.embed(doc)
        results.append(result)
    
    # Write to S3 immediately — not memory
    s3.put_object(
        Bucket="embeddings-bucket",
        Key=f"batches/{batch_id}.json",
        Body=json.dumps(results),
    )
```

**Build idempotent processing** — safe to re-run if interrupted:

```python
def process_with_deduplication(document_ids: list[str]) -> None:
    already_processed = get_completed_ids_from_s3()
    
    to_process = [id for id in document_ids if id not in already_processed]
    
    for doc_id in to_process:
        result = process(doc_id)
        mark_completed(doc_id)   # atomic write to S3 or DynamoDB
```

### Kubernetes spot configuration

**Node affinity to prefer spot, fall back to on-demand:**

```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      preference:
        matchExpressions:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot"]
    - weight: 1
      preference:
        matchExpressions:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
```

**Handle spot termination notice in pods:**

```yaml
# AWS Node Termination Handler — handles 2-minute spot warning
helm repo add eks https://aws.github.io/eks-charts
helm install aws-node-termination-handler eks/aws-node-termination-handler \
  --namespace kube-system \
  --set enableSpotInterruptionDraining=true \
  --set enableRebalanceMonitoring=true
```

### Multi-region spot strategy

Spot availability varies by region and instance type. Spread across multiple pools to reduce interruption risk:

```yaml
# Karpenter NodePool with multiple spot fallback options
requirements:
  - key: karpenter.k8s.aws/instance-type
    operator: In
    values:
      - p4d.24xlarge   # 8× A100 — first choice
      - p3.16xlarge    # 8× V100 — fallback
      - g5.48xlarge    # 8× A10G — fallback
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot", "on-demand"]   # on-demand is last resort
```

---

## Tools

| Tool | Use |
|------|-----|
| [Karpenter](https://karpenter.sh) | Spot-first node provisioning with automatic on-demand fallback |
| [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler) | Graceful pod draining on spot interruption |
| [AWS Fault Injection Service](https://aws.amazon.com/fis/) | Test interruption handling before production |
| [GCP Spot VM preemption handler](https://cloud.google.com/compute/docs/instances/preemptible) | GCP equivalent |
| [Argo Workflows](https://argoproj.github.io/argo-workflows/) | Batch workflow orchestration with retry on interruption |
| [Ray on Spot](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/aws-eks-gpu-cluster.html) | Ray cluster with spot GPU nodes |

---

## Example

**Scenario:** An ML team runs nightly batch inference to generate embeddings for 10 million product descriptions. Currently using 4× on-demand A100 80GB instances for 6 hours nightly.

```
On-demand baseline:
4 GPUs × $6/hr × 6hrs × 30 days = $4,320/month

After switching to spot with checkpoint/resume:
Estimated spot rate: $1.80/hr
Interruption rate: ~15% of runs (occasional retry adds <30 min)
Effective cost: 4 GPUs × $1.80/hr × 6.5hrs avg × 30 days = $1,404/month

Monthly saving: $2,916 (67.5%)
Operational impact: occasional delayed completion by 30 minutes — acceptable for batch
```

---

## Implementation checklist

- [ ] Audit workloads — identify which are interruption-tolerant
- [ ] Add SIGTERM handler and checkpoint logic to all training/batch jobs
- [ ] Move in-progress state to durable object storage (S3/GCS)
- [ ] Make all batch processing idempotent with deduplication
- [ ] Configure Karpenter with spot-first + on-demand fallback NodePool
- [ ] Install AWS Node Termination Handler (or GCP equivalent)
- [ ] Test interruption handling with AWS FIS before production cutover
- [ ] Monitor interruption rate and adjust instance type allowlist if too high

---

## Further reading

- [AWS EC2 Spot Instances best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
- [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler)
- [GCP Preemptible VMs](https://cloud.google.com/compute/docs/instances/preemptible)
- [Karpenter spot configuration](https://karpenter.sh/docs/concepts/nodepools/#capacity-type)
- [Argo Workflows for fault-tolerant batch jobs](https://argoproj.github.io/argo-workflows/workflow-concepts/)

---

**Previous:** [05 — Ray / Kubernetes](05-ray-kubernetes.md)  
**Back to:** [README](../README.md)
