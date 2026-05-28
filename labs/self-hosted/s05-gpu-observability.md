# S-05: GPU Utilization Monitoring with DCGM + Grafana

> Build a comprehensive GPU observability stack to track utilization, memory, power, and temperature metrics for cost optimization.

---

## Objective

By the end of this lab, you will have:

- NVIDIA DCGM Exporter collecting GPU metrics
- Prometheus scraping and storing time-series data
- Grafana dashboard showing real-time GPU utilization
- Alerts for underutilized or overheating GPUs
- Cost-per-inference metrics tracking

**Time:** 75 minutes  
**Cost:** Free (runs on your existing GPU hardware)

---

## Prerequisites

- NVIDIA GPU with drivers installed (CUDA 11.x or 12.x)
- Docker + NVIDIA Container Toolkit
- Helm 3.x installed
- Kubernetes cluster (local kind/minikube or cloud EKS/GKE/AKS)
- Basic understanding of Prometheus/Grafana

```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

Expected output:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 525.60.13    Driver Version: 525.60.13    CUDA Version: 12.0     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  Tesla T4            On   | 00000000:00:1E.0 Off |                    0 |
| N/A   46C    P8    11W /  70W |      0MiB / 15360MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

---

## Background

GPU cost optimization starts with **visibility**. You can't optimize what you don't measure. Common issues detected through monitoring:

| Issue | Symptom | Cost Impact |
|-------|---------|-------------|
| **Underutilization** | GPU < 30% utilization | Paying for 70%+ wasted capacity |
| **Memory bottlenecks** | VRAM at 95-100% | Throttled throughput, need larger GPUs |
| **Thermal throttling** | Temperature > 80°C | Reduced performance, hardware risk |
| **Idle GPUs** | 0% utilization for extended periods | 100% wasted spend |

### Key metrics to track

| Metric | Ideal Range | Why it matters |
|--------|-------------|----------------|
| **GPU Utilization** | 70-95% | Measures compute efficiency |
| **Memory Utilization** | 60-90% | Balances batch size vs OOM risk |
| **Power Draw** | 60-80% of TDP | Correlates with cost and heat |
| **Temperature** | 60-75°C | Prevents thermal throttling |
| **SM Clock** | Near max rated | Confirms no throttling |

---

## Setup

### Step 1: Create Kubernetes namespace

```bash
kubectl create namespace gpu-monitoring
```

### Step 2: Add Helm repositories

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

Expected output:
```
"prometheus-community" has been added to your repositories
"grafana" has been added to your repositories
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "prometheus-community" chart repository
...Successfully got an update from the "grafana" chart repository
Update Complete. ⎈Happy Helming!⎈
```

---

## Step-by-step

### Step 1: Deploy NVIDIA DCGM Exporter

DCGM (Data Center GPU Manager) exports GPU metrics in Prometheus format.

Create `dcgm-values.yaml`:

```yaml
serviceMonitor:
  enabled: true
  namespace: gpu-monitoring
  interval: 15s

resources:
  limits:
    nvidia.com/gpu: 1
  requests:
    nvidia.com/gpu: 1

nodeSelector:
  nvidia.com/gpu.present: "true"

tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

Deploy:

```bash
helm install dcgm-exporter nvdp/dcgm-exporter \
  --namespace gpu-monitoring \
  -f dcgm-values.yaml \
  --repo https://nvidia.github.io/k8s-device-plugin
```

Verify DCGM is running:

```bash
kubectl get pods -n gpu-monitoring -l app=dcgm-exporter
```

Expected output:
```
NAME                             READY   STATUS    RESTARTS   AGE
dcgm-exporter-7d8f9c6b5-xk2m9   1/1     Running   0          45s
```

Check metrics endpoint:

```bash
kubectl port-forward svc/dcgm-exporter 9400:9400 -n gpu-monitoring
```

Then in another terminal:

```bash
curl localhost:9400/metrics | grep DC
```

Expected output (sample):
```
DCGM_FI_DEV_GPU_TEMP{gpu="0",UUID="GPU-xxxx"} 46
DCGM_FI_DEV_POWER_USAGE{gpu="0",UUID="GPU-xxxx"} 11
DCGM_FI_DEV_SM_CLOCK{gpu="0",UUID="GPU-xxxx"} 1395
DCGM_FI_DEV_MEM_COPY_UTIL{gpu="0",UUID="GPU-xxxx"} 0
DCGM_FI_DEV_GPU_UTIL{gpu="0",UUID="GPU-xxxx"} 0
DCGM_FI_DEV_FB_USED{gpu="0",UUID="GPU-xxxx"} 0
```

Press `Ctrl+C` to stop port-forwarding.

### Step 2: Deploy Prometheus

Create `prometheus-values.yaml`:

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
    
    resources:
      requests:
        cpu: 500m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi
    
    retention: 7d
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi

alertmanager:
  enabled: true
  
server:
  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi
```

Deploy:

```bash
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace gpu-monitoring \
  -f prometheus-values.yaml
```

Wait for all pods to be ready:

```bash
kubectl wait --for=condition=ready pod -l app=prometheus -n gpu-monitoring --timeout=120s
```

### Step 3: Create ServiceMonitor for DCGM

Create `servicemonitor.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: dcgm-exporter
  namespace: gpu-monitoring
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: dcgm-exporter
  endpoints:
    - port: http
      interval: 15s
      path: /metrics
  namespaceSelector:
    matchNames:
      - gpu-monitoring
```

Apply:

```bash
kubectl apply -f servicemonitor.yaml
```

Verify Prometheus is scraping DCGM:

```bash
kubectl port-forward svc/prometheus-operated 9090:9090 -n gpu-monitoring
```

Then visit `http://localhost:9090/targets` in your browser. You should see `dcgm-exporter` with status "UP".

Press `Ctrl+C` to stop.

### Step 4: Deploy Grafana

Grafana is already included in the kube-prometheus-stack. Get the admin password:

```bash
kubectl get secret prometheus-grafana -n gpu-monitoring -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```

Port-forward to Grafana:

```bash
kubectl port-forward svc/prometheus-grafana 3000:80 -n gpu-monitoring
```

Visit `http://localhost:3000` and log in with:
- Username: `admin`
- Password: (from previous command)

### Step 5: Import GPU Dashboard

Create `gpu-dashboard.json`:

```json
{
  "dashboard": {
    "title": "GPU Cost Optimization Dashboard",
    "tags": ["gpu", "finops", "nvidia"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "GPU Utilization (%)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_GPU_UTIL * 100",
            "legendFormat": "GPU {{gpu}} - {{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 30},
                {"color": "green", "value": 70}
              ]
            }
          }
        }
      },
      {
        "id": 2,
        "title": "GPU Memory Utilization (%)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_FB_USED",
            "legendFormat": "GPU {{gpu}} - {{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100
          }
        }
      },
      {
        "id": 3,
        "title": "GPU Power Draw (W)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_POWER_USAGE",
            "legendFormat": "GPU {{gpu}} - {{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "watt"
          }
        }
      },
      {
        "id": 4,
        "title": "GPU Temperature (°C)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_GPU_TEMP",
            "legendFormat": "GPU {{gpu}} - {{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "celsius",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 75},
                {"color": "red", "value": 85}
              ]
            }
          }
        }
      },
      {
        "id": 5,
        "title": "GPU Underutilization Alert",
        "type": "stat",
        "gridPos": {"h": 6, "w": 8, "x": 0, "y": 16},
        "targets": [
          {
            "expr": "count(DCGM_FI_DEV_GPU_UTIL < 30)",
            "legendFormat": "Underutilized GPUs"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "red", "value": 1}
              ]
            }
          }
        }
      },
      {
        "id": 6,
        "title": "Average GPU Utilization (24h)",
        "type": "stat",
        "gridPos": {"h": 6, "w": 8, "x": 8, "y": 16},
        "targets": [
          {
            "expr": "avg_over_time(DCGM_FI_DEV_GPU_UTIL[24h])",
            "legendFormat": "Avg Util %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "decimals": 1
          }
        }
      },
      {
        "id": 7,
        "title": "Estimated Daily Cost per GPU",
        "type": "stat",
        "gridPos": {"h": 6, "w": 8, "x": 16, "y": 16},
        "targets": [
          {
            "expr": "(avg(DCGM_FI_DEV_POWER_USAGE) / 1000) * 24 * 0.12",
            "legendFormat": "$/day @ $0.12/kWh",
            "instant": true
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "decimals": 2
          }
        }
      }
    ],
    "refresh": "15s",
    "schemaVersion": 38,
    "version": 1
  }
}
```

Import via Grafana UI:
1. Go to Dashboards → Import
2. Paste the JSON content
3. Select Prometheus as data source
4. Click Import

Or import via API:

```bash
GRAFANA_URL="http://localhost:3000"
GRAFANA_PASSWORD=$(kubectl get secret prometheus-grafana -n gpu-monitoring -o jsonpath="{.data.admin-password}" | base64 --decode)

curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "admin:$GRAFANA_PASSWORD" \
  -d @gpu-dashboard.json
```

### Step 6: Create Alerting Rules

Create `gpu-alerts.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: gpu-cost-alerts
  namespace: gpu-monitoring
  labels:
    release: prometheus
spec:
  groups:
    - name: gpu.cost.optimization
      rules:
        - alert: GPUUnderutilized
          expr: avg_over_time(DCGM_FI_DEV_GPU_UTIL[1h]) < 30
          for: 1h
          labels:
            severity: warning
          annotations:
            summary: "GPU {{ $labels.gpu }} underutilized"
            description: "GPU utilization has been below 30% for 1 hour (current: {{ $value }}%)"
            
        - alert: GPUIdle
          expr: avg_over_time(DCGM_FI_DEV_GPU_UTIL[30m]) == 0
          for: 30m
          labels:
            severity: critical
          annotations:
            summary: "GPU {{ $labels.gpu }} is idle"
            description: "GPU has been completely idle for 30 minutes - consider scaling down"
            
        - alert: GPUHighTemperature
          expr: DCGM_FI_DEV_GPU_TEMP > 80
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "GPU {{ $labels.gpu }} temperature high"
            description: "GPU temperature is {{ $value }}°C - risk of thermal throttling"
            
        - alert: GPUMemoryNearFull
          expr: DCGM_FI_DEV_FB_USED > 95
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "GPU {{ $labels.gpu }} memory nearly full"
            description: "GPU memory usage is {{ $value }}% - may cause OOM errors"
```

Apply:

```bash
kubectl apply -f gpu-alerts.yaml
```

### Step 7: Generate Load Test (Optional)

To see metrics in action, deploy a simple GPU load generator:

Create `gpu-load-test.py`:

```python
import torch
import time

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")

# Allocate memory
tensor = torch.randn(5000, 5000).cuda()
print(f"Allocated {tensor.element_size() * tensor.nelement() / 1e6:.1f} MB VRAM")

# Generate compute load
print("Starting matrix multiplication load test...")
for i in range(100):
    result = torch.matmul(tensor, tensor)
    if i % 10 == 0:
        print(f"Iteration {i}/100")
    time.sleep(0.5)

print("Load test complete!")
```

Run in a GPU-enabled pod:

```bash
kubectl run gpu-test --image=pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime \
  --restart=Never \
  --limits='nvidia.com/gpu=1' \
  --requests='nvidia.com/gpu=1' \
  -- python3 -c "
import torch
import time
tensor = torch.randn(5000, 5000).cuda()
for i in range(100):
    result = torch.matmul(tensor, tensor)
    time.sleep(0.5)
"
```

Watch the GPU utilization spike in Grafana!

---

## Validate

### Verification checklist

- [ ] DCGM Exporter pod is running
- [ ] Prometheus shows DCGM as an active target
- [ ] Grafana dashboard displays GPU metrics
- [ ] Metrics update every 15 seconds
- [ ] Alerts are configured and visible in Prometheus

### Expected dashboard views

**GPU Utilization Panel:**
- Shows real-time utilization percentage
- Green when > 70%, yellow 30-70%, red < 30%

**Power Draw Panel:**
- Displays watts consumed
- Correlates with utilization

**Temperature Panel:**
- Tracks thermal performance
- Alerts if > 80°C

**Cost Estimation Panel:**
- Calculates daily cost based on power draw
- Example: 150W average × 24h × $0.12/kWh = $0.43/day

---

## Cost Impact

**Without monitoring:**
- Idle GPUs go unnoticed (100% waste)
- Underutilized GPUs run continuously (50-70% waste)
- No visibility into cost per inference

**With monitoring:**
- Identify and terminate idle GPUs immediately
- Right-size GPU instances based on actual usage patterns
- Track cost per model/inference for pricing decisions

**Estimated savings:**
- **30-50%** reduction in GPU costs through better utilization
- **$500-2000/month** per GPU by eliminating idle time
- **15-25%** savings from right-sizing based on metrics

---

## Advanced: Cost Per Inference Tracking

Create `cost-tracking.yaml` to add custom metrics:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cost-calculator
  namespace: gpu-monitoring
data:
  calculate_cost.py: |
    #!/usr/bin/env python3
    """
    Calculate cost per inference from GPU metrics
    """
    import os
    import requests
    
    PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
    GPU_COST_PER_HOUR = float(os.getenv('GPU_COST_PER_HOUR', '1.01'))  # T4 on-demand
    
    def get_avg_utilization():
        query = 'avg(avg_over_time(DCGM_FI_DEV_GPU_UTIL[1h]))'
        response = requests.get(f'{PROMETHEUS_URL}/api/v1/query', params={'query': query})
        data = response.json()
        return float(data['data']['result'][0]['value'][1]) if data['data']['result'] else 0
    
    def get_requests_per_hour():
        # Query your inference server metrics (example for vLLM)
        query = 'sum(increase(vllm:num_requests_total[1h]))'
        response = requests.get(f'{PROMETHEUS_URL}/api/v1/query', params={'query': query})
        data = response.json()
        return float(data['data']['result'][0]['value'][1]) if data['data']['result'] else 1
    
    def calculate_cost_per_inference():
        utilization = get_avg_utilization()
        requests_count = get_requests_per_hour()
        
        effective_gpu_cost = GPU_COST_PER_HOUR * (utilization / 100)
        cost_per_request = effective_gpu_cost / max(requests_count, 1)
        
        return {
            'utilization_percent': utilization,
            'requests_per_hour': requests_count,
            'cost_per_inference_usd': round(cost_per_request, 6),
            'hourly_gpu_cost_usd': round(effective_gpu_cost, 2)
        }
    
    if __name__ == '__main__':
        import json
        print(json.dumps(calculate_cost_per_inference(), indent=2))
```

---

## Teardown

```bash
# Remove all monitoring components
helm uninstall dcgm-exporter -n gpu-monitoring
helm uninstall prometheus -n gpu-monitoring

# Delete namespace
kubectl delete namespace gpu-monitoring

# Clean up local files
rm -f dcgm-values.yaml prometheus-values.yaml servicemonitor.yaml gpu-dashboard.json gpu-alerts.yaml gpu-load-test.py
```

---

## Next Steps

1. **Integrate with Kubecost** — Combine GPU metrics with cluster cost allocation
2. **Add vLLM metrics** — Track tokens/sec, request latency, queue depth
3. **Build cost reports** — Generate weekly GPU cost reports by team/project
4. **Automate scaling** — Use metrics to trigger Karpenter scale-down decisions
5. **Set up PagerDuty** — Route critical GPU alerts to on-call engineers

---

## Related Techniques

- [S-01: vLLM Deployment](s01-vllm-prometheus.md) — Add inference metrics to this dashboard
- [S-03: Karpenter Autoscaling](s03-karpenter-gpu.md) — Use utilization metrics for scaling decisions
- [S-06: Spot GPU Optimization](s04-spot-gpu.md) — Monitor spot GPU health and interruptions

---

## Troubleshooting

**DCGM not showing metrics:**
```bash
kubectl logs -n gpu-monitoring -l app=dcgm-exporter
# Check for permission errors or GPU access issues
```

**Prometheus not scraping:**
```bash
kubectl get servicemonitor -n gpu-monitoring
kubectl describe servicemonitor dcgm-exporter -n gpu-monitoring
```

**Grafana dashboard empty:**
- Verify Prometheus data source is configured
- Check metric names match (use Explore tab in Grafana)
- Ensure time range is set correctly
