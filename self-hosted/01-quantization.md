# 01 — Quantization

> Shrink model memory footprint. Run more on less hardware.

**Category:** Self-Hosted AI FinOps · Technique 01 of 06  
**Tags:** `int8` `int4` `vram-reduction` `throughput`

---

## What it is

Quantization reduces the numerical precision of a model's weights from 32-bit or 16-bit floating point to 8-bit integers (INT8) or 4-bit integers (INT4). This shrinks the model's VRAM footprint significantly — enabling deployment on cheaper hardware, or running multiple models on a single GPU — with minimal quality loss.

---

## Why it matters

GPU VRAM is the scarcest and most expensive resource in self-hosted AI. A full-precision (FP16) model requires approximately 2 bytes per parameter:

| Model | FP16 VRAM | INT8 VRAM | INT4 VRAM |
|-------|-----------|-----------|-----------|
| 7B params | 14 GB | 7 GB | 3.5 GB |
| 13B params | 26 GB | 13 GB | 6.5 GB |
| 70B params | 140 GB | 70 GB | 35 GB |

A 70B model that requires 8× A100 80GB GPUs in FP16 can fit on 2× A100 80GB in INT4 — a 4x hardware cost reduction. Or you can run four 7B model replicas on a single A100 that previously held one.

---

## How it works

### Quantization methods

**Post-Training Quantization (PTQ)** — quantize after training, no fine-tuning required:

- **GPTQ** — weight-only quantization, applied once, fast inference. Best for INT4/INT8.
- **AWQ (Activation-aware Weight Quantization)** — preserves important weights, better quality than GPTQ at the same bit width.
- **bitsandbytes** — dynamic 8-bit quantization, easy to integrate with Hugging Face.

**Quantization-Aware Training (QAT)** — quantization baked into the training process. Higher quality but requires retraining. Practical only if you control the training pipeline.

### Quality impact

INT8 quantization typically shows less than 1% quality degradation on standard benchmarks. INT4 shows 1–4% degradation — usually acceptable for most production tasks. Always benchmark on your specific task before production rollout.

```python
# Quick quality check pattern
from evaluate import load

# Load perplexity metric
perplexity = load("perplexity", module_type="metric")

fp16_score = evaluate_model(fp16_model, benchmark_dataset)
int8_score  = evaluate_model(int8_model, benchmark_dataset)
int4_score  = evaluate_model(int4_model, benchmark_dataset)

print(f"FP16: {fp16_score:.2f} | INT8: {int8_score:.2f} | INT4: {int4_score:.2f}")
```

### Deploying a quantized model with vLLM

```bash
# Serve a GPTQ-quantized Llama model
vllm serve meta-llama/Llama-3-8B-Instruct \
  --quantization gptq \
  --gpu-memory-utilization 0.90 \
  --max-model-len 8192
```

```bash
# Serve with AWQ quantization
vllm serve mistralai/Mistral-7B-Instruct-v0.3 \
  --quantization awq \
  --gpu-memory-utilization 0.85
```

### Using bitsandbytes with Hugging Face

```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
import torch

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",       # NormalFloat4 — better quality
    bnb_4bit_use_double_quant=True,  # nested quantization for extra savings
)

model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3-8B-Instruct",
    quantization_config=quantization_config,
    device_map="auto",
)
```

---

## Tools

| Tool | Use |
|------|-----|
| [vLLM](https://github.com/vllm-project/vllm) | Serves quantized models (GPTQ, AWQ, GGUF) with high throughput |
| [bitsandbytes](https://github.com/TimDettmers/bitsandbytes) | Dynamic INT8/INT4 quantization via Hugging Face |
| [AutoGPTQ](https://github.com/AutoGPTQ/AutoGPTQ) | GPTQ quantization toolkit |
| [llama.cpp](https://github.com/ggerganov/llama.cpp) | GGUF format, runs quantized models on CPU+GPU hybrid |
| [Ollama](https://ollama.com) | Easy local deployment of pre-quantized models |
| [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) | Monitor VRAM usage post-quantization |

---

## Example

**Scenario:** A team is serving a 13B parameter instruction-tuned model for internal code review. Currently running two A100 40GB GPUs (FP16), costing $12/hour on cloud.

```
FP16 setup:
  13B × 2 bytes = 26 GB VRAM
  2× A100 40GB required
  Cost: $12/hour × 24 × 30 = $8,640/month

After INT4 quantization (AWQ):
  13B × 0.5 bytes = 6.5 GB VRAM
  1× A100 40GB (fits with room for KV cache)
  Cost: $6/hour × 24 × 30 = $4,320/month

Monthly saving: $4,320 (50% reduction)
Quality benchmark: 98.3% retention on code completion task
```

---

## Implementation checklist

- [ ] Identify target model and measure baseline VRAM usage with DCGM
- [ ] Choose quantization method: INT8 for quality-sensitive, INT4 for max savings
- [ ] Run quality benchmark on your specific task before production
- [ ] Deploy quantized model via vLLM and compare throughput (should be equal or better)
- [ ] Monitor VRAM headroom for KV cache — leave at least 15–20% free
- [ ] A/B test output quality with a small traffic split before full rollout

---

## Further reading

- [AWQ: Activation-aware Weight Quantization](https://arxiv.org/abs/2306.00978)
- [GPTQ: Accurate Post-Training Quantization](https://arxiv.org/abs/2210.17323)
- [vLLM quantization documentation](https://docs.vllm.ai/en/latest/quantization/supported_hardware.html)
- [bitsandbytes documentation](https://huggingface.co/docs/bitsandbytes)
- [Hugging Face quantization guide](https://huggingface.co/docs/transformers/quantization)

---

**Next:** [02 — vLLM](02-vllm.md)
