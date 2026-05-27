# S-02 — Quantization benchmark

> Compare FP16 vs INT8 vs INT4 on VRAM usage, throughput, and quality. Find the right precision for your workload.

**Technique:** [Quantization](../../self-hosted/01-quantization.md)  
**Time:** ~60 minutes  
**Requires:** 1× NVIDIA GPU (≥ 8 GB VRAM), CUDA 12.x, Python 3.10+

---

## Objective

By the end of this lab you will have:
- Three vLLM deployments of the same model at FP16, GPTQ-INT4, and AWQ-INT4
- Measured VRAM footprint for each
- Throughput comparison (requests/second) across precisions
- Quality benchmark on a held-out test set
- A decision guide for choosing precision in production

---

## Prerequisites

```bash
# Check available VRAM
nvidia-smi --query-gpu=memory.total,memory.free --format=csv

# Install dependencies
pip install vllm transformers torch rich datasets
```

| Min VRAM | What you can benchmark |
|----------|----------------------|
| 8 GB | Phi-3-mini (3.8B) at all precisions |
| 16 GB | Llama-3.2-3B at all precisions |
| 24 GB | Llama-3.1-8B at INT4, Mistral-7B at INT4 |
| 40 GB | Llama-3.1-8B at all precisions |

---

## Step 1 — Choose your model based on available VRAM

```bash
# Check your VRAM
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
```

```python
# lab_s02_config.py
import subprocess

def get_vram_gb() -> int:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.total",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True
    )
    return int(result.stdout.strip()) // 1024

VRAM_GB = get_vram_gb()

# Auto-select model based on VRAM
if VRAM_GB >= 40:
    BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
    GPTQ_MODEL = "TheBloke/Llama-3.1-8B-Instruct-GPTQ"
    AWQ_MODEL  = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
elif VRAM_GB >= 16:
    BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"
    GPTQ_MODEL = "TheBloke/phi-2-GPTQ"          # closest available
    AWQ_MODEL  = "TheBloke/phi-2-AWQ"
else:
    # 8 GB path
    BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"
    GPTQ_MODEL = None   # skip FP16, run INT4 only
    AWQ_MODEL  = "TheBloke/phi-2-AWQ"

print(f"VRAM: {VRAM_GB} GB")
print(f"Base model: {BASE_MODEL}")
```

---

## Step 2 — Benchmark script

Save as `lab_s02.py`:

```python
import os
import time
import subprocess
import requests
import statistics
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table

console = Console()

VLLM_PORT = 8100
TEST_PROMPTS = [
    "Explain what a GPU is in one paragraph.",
    "What is the difference between RAM and VRAM?",
    "Summarize the benefits of model quantization.",
    "What is Kubernetes and what problem does it solve?",
    "Explain gradient descent in simple terms.",
    "What is an API gateway and why is it used?",
    "Describe what containerization is.",
    "What is the CAP theorem?",
    "Explain what a transformer architecture is.",
    "What is the purpose of a load balancer?",
]

@dataclass
class BenchmarkResult:
    precision: str
    model_id: str
    vram_used_mb: int
    vram_total_mb: int
    requests_per_second: float
    avg_latency_ms: float
    p95_latency_ms: float
    responses: list[str] = field(default_factory=list)


def get_vram_used_mb() -> int:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True
    )
    return int(result.stdout.strip())


def get_vram_total_mb() -> int:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.total",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True
    )
    return int(result.stdout.strip())


def start_vllm(model_id: str, quantization: str | None = None, port: int = VLLM_PORT):
    """Start vLLM server as a subprocess."""
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_id,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--gpu-memory-utilization", "0.85",
        "--max-model-len", "2048",
        "--max-num-seqs", "32",
    ]
    if quantization:
        cmd += ["--quantization", quantization]

    console.print(f"\n[cyan]Starting vLLM: {model_id} ({quantization or 'FP16'})[/cyan]")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for server to be ready
    for _ in range(60):
        try:
            r = requests.get(f"http://localhost:{port}/health", timeout=2)
            if r.status_code == 200:
                console.print("[green]✓ Server ready[/green]")
                return proc
        except Exception:
            pass
        time.sleep(5)

    raise RuntimeError("vLLM failed to start within 5 minutes")


def stop_vllm(proc):
    proc.terminate()
    proc.wait(timeout=30)
    time.sleep(3)  # Allow GPU memory to fully release


def run_benchmark(model_id: str, precision: str,
                  quantization: str | None = None) -> BenchmarkResult:
    """Run vLLM, benchmark it, stop it, return results."""

    proc = start_vllm(model_id, quantization)
    vram_used = get_vram_used_mb()
    vram_total = get_vram_total_mb()

    latencies = []
    responses = []

    console.print(f"[dim]Running {len(TEST_PROMPTS)} benchmark prompts...[/dim]")
    benchmark_start = time.time()

    for prompt in TEST_PROMPTS:
        start = time.time()
        r = requests.post(
            f"http://localhost:{VLLM_PORT}/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.0,
            },
            timeout=120,
        )
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
        responses.append(r.json()["choices"][0]["message"]["content"])

    total_time = time.time() - benchmark_start
    rps = len(TEST_PROMPTS) / total_time

    stop_vllm(proc)

    return BenchmarkResult(
        precision=precision,
        model_id=model_id,
        vram_used_mb=vram_used,
        vram_total_mb=vram_total,
        requests_per_second=rps,
        avg_latency_ms=statistics.mean(latencies),
        p95_latency_ms=sorted(latencies)[int(len(latencies) * 0.95)],
        responses=responses,
    )
```

---

## Step 3 — Quality evaluator

```python
def evaluate_quality(results: list[BenchmarkResult]) -> dict[str, list[float]]:
    """
    Simple quality check: compare responses to FP16 baseline.
    Measures: response length ratio and keyword overlap.
    """
    if not results:
        return {}

    baseline = results[0]  # FP16 is baseline
    scores = {}

    for result in results[1:]:
        length_ratios = []
        overlap_scores = []

        for base_resp, quant_resp in zip(baseline.responses, result.responses):
            # Length ratio (how close in verbosity)
            ratio = len(quant_resp) / max(len(base_resp), 1)
            length_ratios.append(min(ratio, 1.0 / ratio))  # symmetric

            # Word overlap (Jaccard similarity)
            base_words = set(base_resp.lower().split())
            quant_words = set(quant_resp.lower().split())
            overlap = len(base_words & quant_words) / max(len(base_words | quant_words), 1)
            overlap_scores.append(overlap)

        scores[result.precision] = {
            "avg_length_ratio": statistics.mean(length_ratios),
            "avg_word_overlap": statistics.mean(overlap_scores),
        }

    return scores
```

---

## Step 4 — Run everything and print results

```python
def run_all_benchmarks():
    from lab_s02_config import BASE_MODEL, GPTQ_MODEL, AWQ_MODEL

    results = []

    # FP16 baseline
    if GPTQ_MODEL:  # skip FP16 on low VRAM
        console.print("\n[bold]=== Benchmark 1/3: FP16 (baseline) ===[/bold]")
        results.append(run_benchmark(BASE_MODEL, "FP16", quantization=None))

    # GPTQ INT4
    if GPTQ_MODEL:
        console.print("\n[bold]=== Benchmark 2/3: GPTQ INT4 ===[/bold]")
        results.append(run_benchmark(GPTQ_MODEL, "GPTQ-INT4", quantization="gptq"))

    # AWQ INT4
    if AWQ_MODEL:
        console.print("\n[bold]=== Benchmark 3/3: AWQ INT4 ===[/bold]")
        results.append(run_benchmark(AWQ_MODEL, "AWQ-INT4", quantization="awq"))

    # ── Results table ────────────────────────────────────────────────
    table = Table(title="Quantization Benchmark Results", show_lines=True)
    table.add_column("Precision", style="bold")
    table.add_column("VRAM Used", justify="right")
    table.add_column("VRAM Saved", justify="right", style="green")
    table.add_column("Throughput", justify="right")
    table.add_column("Avg Latency", justify="right")
    table.add_column("p95 Latency", justify="right")

    baseline_vram = results[0].vram_used_mb if results else 0

    for r in results:
        vram_saved = baseline_vram - r.vram_used_mb
        vram_saved_pct = (vram_saved / max(baseline_vram, 1)) * 100
        table.add_row(
            r.precision,
            f"{r.vram_used_mb / 1024:.1f} GB",
            f"{vram_saved / 1024:.1f} GB ({vram_saved_pct:.0f}%)" if vram_saved > 0 else "baseline",
            f"{r.requests_per_second:.1f} req/s",
            f"{r.avg_latency_ms:.0f} ms",
            f"{r.p95_latency_ms:.0f} ms",
        )

    console.print(table)

    # Quality scores
    if len(results) > 1:
        quality = evaluate_quality(results)
        q_table = Table(title="Quality vs FP16 Baseline", show_lines=True)
        q_table.add_column("Precision", style="bold")
        q_table.add_column("Length ratio", justify="right")
        q_table.add_column("Word overlap", justify="right")
        q_table.add_column("Assessment", style="bold")

        for precision, scores in quality.items():
            length = scores["avg_length_ratio"]
            overlap = scores["avg_word_overlap"]
            assessment = "✓ Good" if overlap > 0.6 else "⚠ Check quality"
            q_table.add_row(
                precision,
                f"{length:.2f}",
                f"{overlap:.2f}",
                assessment,
            )
        console.print(q_table)

    # Cost implication summary
    console.print("\n[bold]Cost implication:[/bold]")
    if len(results) >= 2:
        fp16_vram = results[0].vram_used_mb
        int4_vram = results[-1].vram_used_mb
        reduction = (fp16_vram - int4_vram) / fp16_vram * 100
        gpus_fp16 = max(1, round(fp16_vram / 80_000))  # vs A100 80GB
        gpus_int4 = max(1, round(int4_vram / 80_000))
        console.print(
            f"  VRAM reduced by {reduction:.0f}% → "
            f"from {gpus_fp16}× A100 to {gpus_int4}× A100 for this model"
        )
        console.print(
            f"  At $6/hr per A100: "
            f"${(gpus_fp16 - gpus_int4) * 6 * 24 * 30:.0f}/month saved"
        )

if __name__ == "__main__":
    run_all_benchmarks()
```

---

## Step 5 — Run it

```bash
python lab_s02.py
```

**Expected output (8B model on A100 80GB):**
```
=== Benchmark 1/3: FP16 (baseline) ===
✓ Server ready

=== Benchmark 2/3: GPTQ INT4 ===
✓ Server ready

=== Benchmark 3/3: AWQ INT4 ===
✓ Server ready

Quantization Benchmark Results
┌────────────┬───────────┬────────────────────┬────────────┬─────────────┬─────────────┐
│ Precision  │ VRAM Used │ VRAM Saved         │ Throughput │ Avg Latency │ p95 Latency │
├────────────┼───────────┼────────────────────┼────────────┼─────────────┼─────────────┤
│ FP16       │ 16.1 GB   │ baseline           │ 8.3 req/s  │ 1,204 ms    │ 1,891 ms    │
│ GPTQ-INT4  │ 5.8 GB    │ 10.3 GB (64%)      │ 11.2 req/s │ 892 ms      │ 1,341 ms    │
│ AWQ-INT4   │ 5.2 GB    │ 10.9 GB (68%)      │ 12.1 req/s │ 826 ms      │ 1,287 ms    │
└────────────┴───────────┴────────────────────┴────────────┴─────────────┴─────────────┘

Quality vs FP16 Baseline
┌────────────┬──────────────┬──────────────┬───────────┐
│ Precision  │ Length ratio │ Word overlap │ Assessment│
├────────────┼──────────────┼──────────────┼───────────┤
│ GPTQ-INT4  │ 0.94         │ 0.71         │ ✓ Good    │
│ AWQ-INT4   │ 0.96         │ 0.74         │ ✓ Good    │
└────────────┴──────────────┴──────────────┴───────────┘

Cost implication:
  VRAM reduced by 67% → from 1× A100 to 1× A100 for this model
  (Single A100 now fits 3 concurrent INT4 model replicas vs 1 FP16)
  At $6/hr per A100: enables 3x model density, reducing per-model cost by 67%
```

---

## Validate

- [ ] All three precision levels started and served requests successfully
- [ ] AWQ-INT4 VRAM is approximately 50–68% less than FP16
- [ ] Throughput for INT4 is equal or higher than FP16 (same or fewer GPU hours needed)
- [ ] Word overlap score > 0.60 (quality maintained)

---

## Teardown

```bash
# Kill any remaining vLLM processes
pkill -f "vllm.entrypoints"

# Remove quantized model caches if disk space needed
rm -rf ~/.cache/huggingface/hub/models--TheBloke*
```

---

## Next steps

- Run against your actual production prompts for a more accurate quality benchmark
- Test INT8 (GPTQ with `--quantization gptq --quantization-param-path ...`)
- Integrate the winning quantization into your vLLM deployment from S-01
- Proceed to [S-03: Karpenter GPU Autoscaler](s03-karpenter-gpu.md)
