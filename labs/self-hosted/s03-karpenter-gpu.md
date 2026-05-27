# S-03 — Karpenter GPU autoscaler on EKS

> Provision GPU nodes on demand. Terminate them the moment they go idle. Stop paying for capacity you're not using.

**Technique:** [Karpenter](../../self-hosted/03-karpenter.md)  
**Time:** ~90 minutes  
**Requires:** AWS account, EKS cluster, `kubectl`, `helm`, `eksctl`  
**Estimated cost:** $2–5 for lab duration (tear down when done)

---

## Objective

By the end of this lab you will have:
- Karpenter installed on EKS with a GPU NodePool
- A vLLM deployment that triggers GPU node provisioning on pod scheduling
- Consolidation configured to terminate idle GPU nodes
- KEDA scaling inference replicas based on request queue depth
- Kubecost showing per-namespace GPU cost attribution

---

## Prerequisites

```bash
# Required tools
aws --version          # AWS CLI v2
eksctl version         # >= 0.180.0
kubectl version        # >= 1.28
helm version           # >= 3.12

# Required AWS permissions
# EC2: RunInstances, DescribeInstances, TerminateInstances
# IAM: CreateRole, AttachRolePolicy, PassRole
# EKS: DescribeCluster
```

---

## Step 1 — Create EKS cluster (or use existing)

```bash
export CLUSTER_NAME="ai-finops-lab"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create cluster WITHOUT a managed node group for GPU nodes
# (Karpenter will provision GPU nodes dynamically)
eksctl create cluster \
  --name $CLUSTER_NAME \
  --region $AWS_REGION \
  --version 1.29 \
  --nodegroup-name system-nodes \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 2 \
  --managed

# Verify cluster is up
kubectl get nodes
# Expected: 2× t3.medium nodes (system workloads only — no GPUs yet)
```

---

## Step 2 — Install Karpenter

```bash
# Set up Karpenter IAM role
export KARPENTER_VERSION="v0.37.0"
export KARPENTER_NAMESPACE="karpenter"

# Create the Karpenter controller IAM role
eksctl create iamserviceaccount \
  --cluster $CLUSTER_NAME \
  --namespace $KARPENTER_NAMESPACE \
  --name karpenter \
  --role-name KarpenterControllerRole-$CLUSTER_NAME \
  --attach-policy-arn "arn:aws:iam::$AWS_ACCOUNT_ID:policy/KarpenterControllerPolicy-$CLUSTER_NAME" \
  --approve \
  --override-existing-serviceaccounts

# Create the node IAM role (for GPU nodes Karpenter will launch)
aws cloudformation deploy \
  --stack-name KarpenterNodeRole-$CLUSTER_NAME \
  --template-file https://raw.githubusercontent.com/aws/karpenter-provider-aws/$KARPENTER_VERSION/website/content/en/docs/getting-started/getting-started-with-karpenter/cloudformation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides ClusterName=$CLUSTER_NAME

# Install Karpenter via Helm
helm registry logout public.ecr.aws 2>/dev/null || true
helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --version $KARPENTER_VERSION \
  --namespace $KARPENTER_NAMESPACE \
  --create-namespace \
  --set settings.clusterName=$CLUSTER_NAME \
  --set settings.interruptionQueue=$CLUSTER_NAME \
  --set controller.resources.requests.cpu=1 \
  --set controller.resources.requests.memory=1Gi \
  --wait

# Verify Karpenter is running
kubectl get pods -n $KARPENTER_NAMESPACE
# Expected: karpenter-xxx Running
```

---

## Step 3 — Create GPU NodePool

Save as `gpu-nodepool.yaml`:

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: gpu-inference
spec:
  template:
    metadata:
      labels:
        workload-type: gpu-inference
    spec:
      nodeClassRef:
        apiVersion: karpenter.k8s.aws/v1beta1
        kind: EC2NodeClass
        name: gpu-nodes

      requirements:
        # GPU instance types — ordered by cost efficiency
        - key: karpenter.k8s.aws/instance-family
          operator: In
          values: ["g5", "g4dn", "p3"]   # A10G, T4, V100

        - key: karpenter.k8s.aws/instance-size
          operator: In
          values: ["xlarge", "2xlarge"]   # single-GPU instances for this lab

        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]   # spot first, on-demand fallback

        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]

      # Terminate nodes after 10 minutes of underutilization
      disruption:
        consolidationPolicy: WhenUnderutilized
        consolidateAfter: 10m

  # Safety limits — never provision more than 4 GPUs in this lab
  limits:
    nvidia.com/gpu: 4

---
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: gpu-nodes
spec:
  amiFamily: AL2
  role: KarpenterNodeRole-${CLUSTER_NAME}

  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: ${CLUSTER_NAME}

  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: ${CLUSTER_NAME}

  # Install NVIDIA drivers on node startup
  userData: |
    #!/bin/bash
    set -ex
    /etc/eks/bootstrap.sh ${CLUSTER_NAME}

    # Install NVIDIA device plugin
    kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml

  tags:
    Environment: lab
    Project: ai-finops
```

```bash
# Substitute environment variables and apply
envsubst < gpu-nodepool.yaml | kubectl apply -f -

# Verify NodePool created
kubectl get nodepool gpu-inference
kubectl get ec2nodeclass gpu-nodes
```

---

## Step 4 — Deploy vLLM (triggers GPU node provisioning)

Save as `vllm-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-inference
  namespace: default
  labels:
    app: vllm-inference
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
      # Schedule on Karpenter GPU nodes only
      nodeSelector:
        workload-type: gpu-inference

      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule

      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          args:
            - "--model"
            - "microsoft/Phi-3-mini-4k-instruct"    # no HF token needed
            - "--host"
            - "0.0.0.0"
            - "--port"
            - "8000"
            - "--gpu-memory-utilization"
            - "0.85"
            - "--max-model-len"
            - "4096"

          ports:
            - containerPort: 8000
              name: http

          resources:
            requests:
              nvidia.com/gpu: "1"
              memory: "12Gi"
              cpu: "4"
            limits:
              nvidia.com/gpu: "1"
              memory: "14Gi"

          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 120
            periodSeconds: 15
            timeoutSeconds: 10

---
apiVersion: v1
kind: Service
metadata:
  name: vllm-inference
spec:
  selector:
    app: vllm-inference
  ports:
    - port: 8000
      targetPort: 8000
  type: ClusterIP
```

```bash
kubectl apply -f vllm-deployment.yaml

# Watch Karpenter provision a GPU node
kubectl get nodes --watch &
kubectl get events -n default --watch &

# Check pod status
kubectl get pods -l app=vllm-inference --watch
```

**Expected sequence:**
```
NAME                             STATUS    REASON
vllm-inference-xxx               Pending   0/2 nodes available: 2 Insufficient nvidia.com/gpu
# Karpenter detects unschedulable pod → provisions GPU node (~60 seconds)
# New node appears:
ip-xxx.ec2.internal   Ready   <none>   45s   v1.29.0
# Pod schedules and starts:
vllm-inference-xxx   Running
```

---

## Step 5 — Install KEDA for queue-based autoscaling

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --wait
```

Save as `vllm-scaledobject.yaml`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-queue-scaler
  namespace: default
spec:
  scaleTargetRef:
    name: vllm-inference
  pollingInterval: 15
  cooldownPeriod: 600        # 10 min — GPU scale-down is expensive
  minReplicaCount: 0         # Scale to zero during idle!
  maxReplicaCount: 4
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring.svc:9090
        metricName: vllm_waiting_requests
        query: sum(vllm:num_waiting_seqs)
        threshold: "3"       # Scale up when > 3 requests waiting
```

```bash
kubectl apply -f vllm-scaledobject.yaml

# Verify KEDA is watching vLLM
kubectl get scaledobject vllm-queue-scaler
kubectl describe scaledobject vllm-queue-scaler
```

---

## Step 6 — Install Kubecost

```bash
helm repo add kubecost https://kubecost.github.io/cost-analyzer/
helm repo update

helm install kubecost kubecost/cost-analyzer \
  --namespace kubecost \
  --create-namespace \
  --set kubecostToken="" \
  --set prometheus.nodeExporter.enabled=true \
  --wait

# Access Kubecost UI
kubectl port-forward -n kubecost svc/kubecost-cost-analyzer 9090:9090 &
# Open: http://localhost:9090
```

---

## Step 7 — Observe the full lifecycle

```bash
# Generate some inference load
kubectl run load-gen --image=curlimages/curl --rm -it --restart=Never -- sh -c '
for i in $(seq 1 20); do
  curl -s -X POST http://vllm-inference:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"microsoft/Phi-3-mini-4k-instruct\",\"messages\":[{\"role\":\"user\",\"content\":\"What is GPU quantization?\"}],\"max_tokens\":100}"
  sleep 2
done'

# Watch GPU node status
kubectl get nodes -l workload-type=gpu-inference --watch

# Check Karpenter logs
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter --follow
```

**Watch for Karpenter consolidation (after load stops):**
```
# After 10 minutes of idle:
{"level":"INFO","msg":"disrupting node","reason":"underutilized","node":"ip-xxx.ec2.internal"}
{"level":"INFO","msg":"node deleted"}
```

---

## Step 8 — Verify cost attribution in Kubecost

1. Open http://localhost:9090
2. Navigate to **Cost Allocation** → **Namespace**
3. Find `default` namespace — shows GPU cost for the vLLM workload
4. Navigate to **Savings** → see rightsizing and spot migration recommendations

---

## Validate

- [ ] GPU node was provisioned automatically when vLLM pod was pending
- [ ] vLLM pod reached Running state and serves inference requests
- [ ] `kubectl get nodes` shows GPU node type (g5, g4dn, or p3 family)
- [ ] Karpenter logs show consolidation events after idle period
- [ ] Kubecost shows per-namespace cost breakdown

---

## Cost impact

A static GPU cluster sized for peak wastes GPU hours during off-peak periods. With Karpenter:
- **Scale to zero** overnight and on weekends → 100% savings on idle hours
- **Spot instances** via Karpenter's capacity-type preference → 60–70% per-hour savings
- **Right-sized instances** → no more over-provisioned GPUs for small models

For a batch workload with 25% utilization, Karpenter + spot typically saves **80–85%** vs a static on-demand cluster.

---

## Teardown

```bash
# Delete all lab resources
kubectl delete -f vllm-deployment.yaml
kubectl delete -f vllm-scaledobject.yaml
kubectl delete -f gpu-nodepool.yaml

# Uninstall Helm releases
helm uninstall keda -n keda
helm uninstall kubecost -n kubecost
helm uninstall karpenter -n karpenter

# Delete the EKS cluster (this terminates all nodes and stops billing)
eksctl delete cluster --name $CLUSTER_NAME --region $AWS_REGION

# Verify no GPU instances are still running
aws ec2 describe-instances \
  --filters "Name=tag:karpenter.sh/provisioner-name,Values=gpu-inference" \
            "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId"
# Expected: empty list
```

---

## Next steps

- Add schedule-based disruption budgets to protect peak hours
- Configure multi-GPU instance types (g5.12xlarge for 4× A10G)
- Try MIG partitioning on the provisioned node: [S-02: Quantization](s02-quantization-bench.md)
- Add node termination alerts to Grafana when GPU idle time exceeds threshold
