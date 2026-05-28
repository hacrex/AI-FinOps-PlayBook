#!/usr/bin/env python3
"""
GPU Monitoring Script for FinOps
Collects GPU utilization, memory usage, and estimates cost per inference.
Exports metrics in Prometheus format.
"""

import pynvml
import time
import json
from datetime import datetime
from prometheus_client import start_http_server, Gauge, Counter, Histogram

# Initialize Prometheus Metrics
gpu_utilization = Gauge('gpu_utilization_percent', 'GPU Utilization %', ['gpu_id'])
gpu_memory_used = Gauge('gpu_memory_used_bytes', 'GPU Memory Used (Bytes)', ['gpu_id'])
gpu_memory_total = Gauge('gpu_memory_total_bytes', 'GPU Memory Total (Bytes)', ['gpu_id'])
gpu_temperature = Gauge('gpu_temperature_celsius', 'GPU Temperature (°C)', ['gpu_id'])
gpu_power_draw = Gauge('gpu_power_watts', 'GPU Power Draw (W)', ['gpu_id'])

inference_counter = Counter('llm_inferences_total', 'Total LLM Inferences', ['model_name'])
inference_latency = Histogram('llm_inference_latency_seconds', 'LLM Inference Latency', ['model_name'])
cost_per_inference = Counter('llm_cost_usd_total', 'Estimated Cost per Inference', ['model_name', 'gpu_type'])

# Cost Configuration (per hour)
GPU_COSTS = {
    "NVIDIA A100": 3.67,
    "NVIDIA A10G": 1.006,
    "NVIDIA T4": 0.526,
    "NVIDIA V100": 2.48,
    "NVIDIA H100": 7.35
}

def get_gpu_info():
    """Collect GPU metrics using NVML"""
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        metrics = []
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            
            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = util.gpu
            
            # Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used = mem.used
            mem_total = mem.total
            
            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                temp = 0
                
            # Power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
            except:
                power = 0
            
            # GPU Name
            gpu_name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(gpu_name, bytes):
                gpu_name = gpu_name.decode('utf-8')
            
            metrics.append({
                'gpu_id': i,
                'gpu_name': gpu_name,
                'utilization': gpu_util,
                'memory_used': mem_used,
                'memory_total': mem_total,
                'temperature': temp,
                'power_watts': power
            })
            
        pynvml.nvmlShutdown()
        return metrics
    except Exception as e:
        print(f"Error collecting GPU metrics: {e}")
        return []

def update_prometheus_metrics(gpu_metrics):
    """Update Prometheus gauges with GPU data"""
    for metric in gpu_metrics:
        gpu_id = str(metric['gpu_id'])
        gpu_name = metric['gpu_name']
        
        gpu_utilization.labels(gpu_id=gpu_id).set(metric['utilization'])
        gpu_memory_used.labels(gpu_id=gpu_id).set(metric['memory_used'])
        gpu_memory_total.labels(gpu_id=gpu_id).set(metric['memory_total'])
        gpu_temperature.labels(gpu_id=gpu_id).set(metric['temperature'])
        gpu_power_draw.labels(gpu_id=gpu_id).set(metric['power_watts'])

def calculate_hourly_cost(gpu_metrics):
    """Calculate current hourly cost based on GPU types"""
    total_cost = 0.0
    for metric in gpu_metrics:
        gpu_name = metric['gpu_name']
        # Find matching cost (partial match)
        cost = 0.0
        for key, value in GPU_COSTS.items():
            if key in gpu_name or gpu_name in key:
                cost = value
                break
        total_cost += cost
    return total_cost

def record_inference(model_name, latency_sec, gpu_type):
    """Record an inference event for cost tracking"""
    inference_counter.labels(model_name=model_name).inc()
    inference_latency.labels(model_name=model_name).observe(latency_sec)
    
    # Estimate cost based on latency and GPU hourly rate
    hourly_rate = GPU_COSTS.get(gpu_type, 1.0)
    cost = (latency_sec / 3600) * hourly_rate
    cost_per_inference.labels(model_name=model_name, gpu_type=gpu_type).inc(cost)

def main():
    print("Starting GPU FinOps Monitor...")
    print("Prometheus metrics available at http://localhost:8000/metrics")
    
    # Start Prometheus server
    start_http_server(8000)
    
    iteration = 0
    while True:
        try:
            gpu_metrics = get_gpu_info()
            
            if gpu_metrics:
                update_prometheus_metrics(gpu_metrics)
                
                # Log summary every 60 seconds
                if iteration % 60 == 0:
                    hourly_cost = calculate_hourly_cost(gpu_metrics)
                    avg_util = sum(m['utilization'] for m in gpu_metrics) / len(gpu_metrics)
                    
                    print(f"[{datetime.now().isoformat()}] "
                          f"GPUs: {len(gpu_metrics)}, "
                          f"Avg Util: {avg_util:.1f}%, "
                          f"Est. Hourly Cost: ${hourly_cost:.2f}")
            
            iteration += 1
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nShutting down monitor...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
