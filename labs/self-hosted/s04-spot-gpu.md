# S-04: Spot GPU batch inference with checkpointing

> Run batch LLM inference on spot GPUs with automatic checkpointing and resumption on interruption.

**Time:** 75 min  
**Difficulty:** Intermediate  
**Prerequisites:** AWS account, NVIDIA GPU instance, Docker, Python 3.10+

---

## Objective

By the end of this lab you will have:

1. A batch inference job running on a spot GPU instance
2. Automatic checkpointing every N documents processed
3. Graceful interruption handling with job resumption
4. Cost comparison showing 60-80% savings vs on-demand

---

## Prerequisites

- AWS account with EC2 access
- An NVIDIA GPU instance (g5.xlarge with A10G recommended for this lab)
- Docker + NVIDIA Container Toolkit installed
- Python 3.10+
- Hugging Face account (for model access if needed)

Estimated cost for this lab: $1-3 on spot vs $5-10 on-demand

---

## Setup

### 1. Launch a spot GPU instance

```bash
# Request a spot instance via AWS CLI
aws ec2 run-instances \
  --image-id ami-0f9e4c8f8d8f8f8f8  # Replace with latest Deep Learning AMI
  --instance-type g5.xlarge \
  --spot-price "0.50" \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100}}]' \
  --iam-instance-profile Name=ec2-spot-role \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=spot-gpu-lab}]' \
  --count 1
```

SSH into your instance:

```bash
ssh -i your-key.pem ubuntu@YOUR_INSTANCE_IP
```

### 2. Install dependencies

```bash
# Update and install Docker
sudo apt update
sudo apt install -y docker.io nvidia-docker2
sudo systemctl start docker
sudo usermod -aG docker $USER

# Create project directory
mkdir -p s04-spot-inference && cd s04-spot-inference
python3 -m venv venv
source venv/bin/activate
pip install torch transformers boto3
```

### 3. Create S3 bucket for checkpoints

```bash
BUCKET_NAME="spot-checkpoints-$(date +%s)"
aws s3 mb s3://$BUCKET_NAME
echo "Bucket created: $BUCKET_NAME"
```

---

## Step-by-step

### Step 1: Build the checkpoint-aware batch processor

Create `batch_processor.py`:

```python
import os
import json
import time
import signal
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime
import boto3

class SpotBatchProcessor:
    def __init__(self, model_name, bucket_name, checkpoint_interval=10):
        self.model_name = model_name
        self.bucket_name = bucket_name
        self.checkpoint_interval = checkpoint_interval
        self.s3 = boto3.client('s3')
        
        self.processed_count = 0
        self.checkpoint_file = None
        self.interrupted = False
        
        # Register signal handler for spot interruption
        signal.signal(signal.SIGTERM, self._handle_interruption)
        
    def _handle_interruption(self, signum, frame):
        print("\n⚠️  Spot interruption detected! Saving checkpoint...")
        self.interrupted = True
        self._save_checkpoint()
        
    def load_model(self):
        print(f"Loading model: {self.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto",
            torch_dtype=torch.float16
        )
        print("Model loaded successfully!")
        
    def _get_checkpoint_key(self, job_id):
        return f"checkpoints/{job_id}/state.json"
    
    def _save_checkpoint(self):
        """Save current progress to S3."""
        if not self.checkpoint_file:
            return
            
        state = {
            "processed_count": self.processed_count,
            "timestamp": datetime.now().isoformat(),
            "model_name": self.model_name,
            "checkpoint_file": self.checkpoint_file
        }
        
        key = self._get_checkpoint_key(state["checkpoint_file"])
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(state)
        )
        
        print(f"✓ Checkpoint saved: {self.processed_count} documents processed")
        
    def _load_checkpoint(self, job_id):
        """Load progress from S3 if available."""
        try:
            key = self._get_checkpoint_key(job_id)
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            state = json.loads(response['Body'].read())
            
            self.processed_count = state["processed_count"]
            self.checkpoint_file = state["checkpoint_file"]
            
            print(f"✓ Resumed from checkpoint: {self.processed_count} documents already processed")
            return True
        except self.s3.exceptions.NoSuchKey:
            print("No checkpoint found, starting fresh")
            return False
            
    def process_document(self, doc):
        """Process a single document through the model."""
        inputs = self.tokenizer(doc[:1000], return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=True,
                temperature=0.7
            )
        
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return result
    
    def run_batch_job(self, input_file, output_file, job_id):
        """Run batch processing with checkpointing."""
        self.checkpoint_file = job_id
        
        # Try to resume from checkpoint
        self._load_checkpoint(job_id)
        
        # Load input documents
        with open(input_file, 'r') as f:
            documents = [line.strip() for line in f.readlines()]
        
        # Skip already processed documents
        documents = documents[self.processed_count:]
        
        print(f"Processing {len(documents)} documents...")
        
        results = []
        for i, doc in enumerate(documents):
            if self.interrupted:
                print("Job interrupted, stopping gracefully")
                break
                
            result = self.process_document(doc)
            results.append({
                "input": doc[:200],
                "output": result,
                "timestamp": datetime.now().isoformat()
            })
            
            self.processed_count += 1
            
            # Save checkpoint periodically
            if self.processed_count % self.checkpoint_interval == 0:
                self._save_checkpoint()
                
            # Progress logging
            if i % 5 == 0:
                print(f"Progress: {i+1}/{len(documents)} documents")
        
        # Save final results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        # Final checkpoint
        self._save_checkpoint()
        
        print(f"✓ Job complete! Processed {self.processed_count} documents")
        return results

# Usage example
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True, help="Unique job identifier")
    parser.add_argument("--input", required=True, help="Input file path")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--bucket", required=True, help="S3 bucket for checkpoints")
    parser.add_argument("--model", default="microsoft/DialoGPT-medium", help="Model name")
    args = parser.parse_args()
    
    processor = SpotBatchProcessor(
        model_name=args.model,
        bucket_name=args.bucket,
        checkpoint_interval=10
    )
    
    processor.load_model()
    processor.run_batch_job(args.input, args.output, args.job_id)
```

### Step 2: Create test input data

Create `sample_docs.txt` with 50 sample documents:

```bash
cat > sample_docs.txt << 'EOF'
The future of artificial intelligence is bright, with applications in healthcare, finance, and transportation.
Machine learning models require large amounts of training data to achieve high accuracy.
Deep learning has revolutionized computer vision, enabling self-driving cars and medical diagnosis.
Natural language processing allows computers to understand and generate human language.
Reinforcement learning agents learn by interacting with their environment and receiving rewards.
Transformer architectures have become the foundation of modern language models like GPT and BERT.
Computer vision systems can now detect objects, faces, and emotions in images and videos.
Generative AI models can create realistic images, music, and text from simple prompts.
Edge AI brings machine learning capabilities to mobile devices and IoT sensors.
Federated learning enables training models across distributed devices while preserving privacy.
EOF

# Repeat to get 50 documents
for i in {1..4}; do cat sample_docs.txt >> sample_docs_extended.txt; done
mv sample_docs_extended.txt sample_docs.txt
wc -l sample_docs.txt
```

Expected output:
```
50 sample_docs.txt
```

### Step 3: Simulate spot interruption testing

Create `test_interruption.sh`:

```bash
#!/bin/bash

JOB_ID="test-job-$(date +%s)"
echo "Starting batch job: $JOB_ID"

# Start the batch processor in background
python3 batch_processor.py \
  --job-id $JOB_ID \
  --input sample_docs.txt \
  --output results.json \
  --bucket $BUCKET_NAME &

PID=$!
echo "Batch processor PID: $PID"

# Wait 15 seconds then simulate interruption
sleep 15
echo "Simulating spot interruption..."
kill -SIGTERM $PID

# Wait for graceful shutdown
wait $PID

echo "Interruption test complete. Check results.json for partial results."
```

Make it executable:

```bash
chmod +x test_interruption.sh
```

### Step 4: Run the batch job

First, test without interruption:

```bash
export BUCKET_NAME="your-bucket-name-here"

python3 batch_processor.py \
  --job-id "full-run-$(date +%s)" \
  --input sample_docs.txt \
  --output results_full.json \
  --bucket $BUCKET_NAME
```

Expected output:
```
Loading model: microsoft/DialoGPT-medium
Model loaded successfully!
No checkpoint found, starting fresh
Processing 50 documents...
Progress: 1/50 documents
Progress: 6/50 documents
Progress: 11/50 documents
...
✓ Checkpoint saved: 10 documents processed
✓ Checkpoint saved: 20 documents processed
...
✓ Job complete! Processed 50 documents
```

### Step 5: Test interruption and resumption

Run the interruption test:

```bash
./test_interruption.sh
```

Expected output:
```
Starting batch job: test-job-1234567890
Batch processor PID: 12345
Loading model: microsoft/DialoGPT-medium
Model loaded successfully!
Processing 50 documents...
Progress: 1/50 documents
Progress: 6/50 documents
Simulating spot interruption...

⚠️  Spot interruption detected! Saving checkpoint...
✓ Checkpoint saved: 15 documents processed
Job interrupted, stopping gracefully
Interruption test complete. Check results.json for partial results.
```

Now resume the job:

```bash
# Get the job ID from the interrupted run
LAST_JOB_ID=$(aws s3 ls s3://$BUCKET_NAME/checkpoints/ | tail -1 | awk '{print $2}' | cut -d'/' -f2)

python3 batch_processor.py \
  --job-id $LAST_JOB_ID \
  --input sample_docs.txt \
  --output results_resumed.json \
  --bucket $BUCKET_NAME
```

Expected output:
```
Loading model: microsoft/DialoGPT-medium
Model loaded successfully!
✓ Resumed from checkpoint: 15 documents already processed
Processing 35 documents...
Progress: 1/35 documents
...
✓ Job complete! Processed 50 documents
```

### Step 6: Calculate cost savings

Create `cost_calculator.py`:

```python
#!/usr/bin/env python3

def calculate_savings(instance_type="g5.xlarge", hours=24, days=30):
    """Calculate monthly savings using spot vs on-demand."""
    
    pricing = {
        "g5.xlarge": {"on_demand": 1.01, "spot": 0.30},
        "g5.2xlarge": {"on_demand": 2.02, "spot": 0.60},
        "g5.4xlarge": {"on_demand": 4.04, "spot": 1.20},
        "p4d.24xlarge": {"on_demand": 32.77, "spot": 9.83},
    }
    
    if instance_type not in pricing:
        print(f"Unknown instance type: {instance_type}")
        return
    
    rates = pricing[instance_type]
    
    on_demand_cost = rates["on_demand"] * hours * days
    spot_cost = rates["spot"] * hours * days
    savings = on_demand_cost - spot_cost
    savings_pct = (savings / on_demand_cost) * 100
    
    print(f"\n{'='*60}")
    print(f"COST ANALYSIS: {instance_type}")
    print(f"{'='*60}")
    print(f"On-demand: ${rates['on_demand']:.2f}/hr")
    print(f"Spot:      ${rates['spot']:.2f}/hr")
    print(f"\nMonthly cost ({hours} hrs/day × {days} days):")
    print(f"  On-demand: ${on_demand_cost:,.2f}")
    print(f"  Spot:      ${spot_cost:,.2f}")
    print(f"  Savings:   ${savings:,.2f} ({savings_pct:.1f}%)")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    calculate_savings("g5.xlarge")
    calculate_savings("p4d.24xlarge")
```

Run the calculator:

```bash
python3 cost_calculator.py
```

Expected output:
```
============================================================
COST ANALYSIS: g5.xlarge
============================================================
On-demand: $1.01/hr
Spot:      $0.30/hr

Monthly cost (24 hrs/day × 30 days):
  On-demand: $727.20
  Spot:      $216.00
  Savings:   $511.20 (70.4%)
============================================================

============================================================
COST ANALYSIS: p4d.24xlarge
============================================================
On-demand: $32.77/hr
Spot:      $9.83/hr

Monthly cost (24 hrs/day × 30 days):
  On-demand: $23,594.40
  Spot:      $7,077.60
  Savings:   $16,516.80 (70.0%)
============================================================
```

---

## Validate

Checklist to confirm success:

- [ ] Batch job processes all 50 documents successfully
- [ ] Checkpoints are saved to S3 every 10 documents
- [ ] SIGTERM signal triggers graceful checkpoint save
- [ ] Job resumes from last checkpoint after interruption
- [ ] No duplicate processing on resume
- [ ] Cost calculator shows 60-80% savings

---

## Cost impact

This lab demonstrates:

```
Single GPU (g5.xlarge) running batch inference 24/7:
On-demand: $727/month
Spot:      $216/month
Savings:   $511/month (70%)

8× GPU cluster (p4d.24xlarge):
On-demand: $23,594/month
Spot:      $7,078/month
Savings:   $16,516/month (70%)
```

With proper checkpointing, spot instances become viable for production batch workloads.

---

## Teardown

Clean up resources:

```bash
# Stop the spot instance (or terminate if done)
aws ec2 stop-instances --instance-ids YOUR_INSTANCE_ID

# Empty and delete S3 bucket
aws s3 rm s3://$BUCKET_NAME --recursive
aws s3 rb s3://$BUCKET_NAME

# Deactivate virtual environment
deactivate
```

---

## Next steps

1. **Add retry logic**: Implement exponential backoff for transient failures
2. **Multi-instance scaling**: Distribute batch jobs across multiple spot instances
3. **Spot fleet**: Use AWS Spot Fleet for automatic capacity rebalancing
4. **Mixed strategy**: Combine spot for batch + on-demand for realtime
5. **Read the technique doc**: [06 — Spot GPU Optimization](../../self-hosted/06-spot-gpu.md)

---

## Troubleshooting

**Issue:** Spot instance not launching  
**Fix:** Increase your spot price limit or try a different instance type/region.

**Issue:** Model loading fails due to memory  
**Fix:** Use a smaller model or enable gradient checkpointing.

**Issue:** Checkpoint not saving to S3  
**Fix:** Verify IAM role has S3 write permissions. Check network connectivity.

**Issue:** Job doesn't resume correctly  
**Fix:** Ensure the same job ID is used. Check that checkpoint file exists in S3.

**Issue:** Interruption signal not caught  
**Fix:** Verify signal handler is registered before starting batch processing. Test with manual SIGTERM.
