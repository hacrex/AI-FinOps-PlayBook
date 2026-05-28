# Terraform Infrastructure for Self-Hosted LLM on EKS

This module provisions an EKS cluster optimized for running LLM workloads with NVIDIA GPUs.

## Features
- EKS Cluster with managed node groups
- NVIDIA GPU support (T4, A10G, A100)
- Autoscaling enabled (Cluster Autoscaler + Karpenter)
- Spot instance support for cost savings
- VPC with public/private subnets

## Usage

```hcl
module "llm_eks" {
  source = "./modules/eks-gpu"

  cluster_name    = "finops-llm-prod"
  region          = "us-east-1"
  kubernetes_version = "1.29"

  # Node Group Configuration
  gpu_instance_types = ["g5.xlarge", "g5.2xlarge"]
  min_size           = 1
  max_size           = 10
  desired_size       = 2
  
  # Cost Optimization
  use_spot_instances = true
  spot_allocation_strategy = "capacity-optimized"
  
  tags = {
    Environment = "production"
    CostCenter  = "ai-inference"
  }
}
```

## Outputs
- `cluster_endpoint`: EKS API endpoint
- `cluster_ca_certificate`: CA cert for kubectl
- `node_group_arn`: ARN of the GPU node group

## Cost Estimates
- **On-Demand g5.xlarge**: ~$1.006/hr per GPU
- **Spot g5.xlarge**: ~$0.30/hr per GPU (70% savings)
- **Monthly Estimate (2 nodes, 50% spot)**: ~$500/mo vs $1,450/mo on-demand
