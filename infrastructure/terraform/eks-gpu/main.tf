terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# VPC for EKS
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-vpc"
  })
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    "Name"                                      = "${var.cluster_name}-private-${count.index + 1}"
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  })
}

resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    "Name"                                      = "${var.cluster_name}-public-${count.index + 1}"
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags = merge(var.tags, {
    Name = "${var.cluster_name}-igw"
  })
}

resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"
  tags = merge(var.tags, {
    Name = "${var.cluster_name}-nat-${count.index + 1}"
  })
}

resource "aws_nat_gateway" "main" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-nat-${count.index + 1}"
  })
}

resource "aws_route_table" "private" {
  count  = 2
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-private-${count.index + 1}"
  })
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

data "aws_availability_zones" "available" {
  state = "available"
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.eks_cluster.arn

  vpc_config {
    subnet_ids = aws_subnet.private[*].id
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  tags = var.tags
}

resource "aws_iam_role" "eks_cluster" {
  name = "${var.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# GPU Node Group
resource "aws_eks_node_group" "gpu" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-gpu-ng"
  node_role_arn   = aws_iam_role.gpu_nodes.arn
  subnet_ids      = aws_subnet.private[*].id

  instance_types = var.gpu_instance_types
  
  scaling_config {
    desired_size = var.desired_size
    max_size     = var.max_size
    min_size     = var.min_size
  }

  capacity_type  = var.use_spot_instances ? "SPOT" : "ON_DEMAND"
  
  launch_template {
    name = aws_launch_template.gpu_nodes.name
    version = "$Latest"
  }

  depends_on = [
    aws_iam_role_policy_attachment.gpu_nodes_cni,
    aws_iam_role_policy_attachment.gpu_nodes_ecr,
    aws_iam_role_policy_attachment.gpu_nodes_ssm
  ]

  tags = merge(var.tags, {
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  })
}

# Launch Template for GPU with NVIDIA drivers
resource "aws_launch_template" "gpu_nodes" {
  name = "${var.cluster_name}-gpu-lt"

  image_id = data.aws_ssm_parameter.nvidia_amazon_linux_2.value

  instance_type = var.gpu_instance_types[0]

  iam_instance_profile {
    arn = aws_iam_instance_profile.gpu_nodes.arn
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.gpu_nodes.id]
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.cluster_name}-gpu-node"
    })
  }

  user_data = base64encode(<<EOF
#!/bin/bash
# Install NVIDIA drivers and container toolkit
yum install -y nvidia-driver-latest-dkms cuda
systemctl restart docker
EOF
  )
}

data "aws_ssm_parameter" "nvidia_amazon_linux_2" {
  name = "/aws/service/eks/optimized-ami/${var.kubernetes_version}/amazon-linux-2-gpu/recommended/image_id"
}

resource "aws_iam_role" "gpu_nodes" {
  name = "${var.cluster_name}-gpu-nodes-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_instance_profile" "gpu_nodes" {
  name = "${var.cluster_name}-gpu-nodes-profile"
  role = aws_iam_role.gpu_nodes.name
}

resource "aws_iam_role_policy_attachment" "gpu_nodes_cni" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.gpu_nodes.name
}

resource "aws_iam_role_policy_attachment" "gpu_nodes_ecr" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.gpu_nodes.name
}

resource "aws_iam_role_policy_attachment" "gpu_nodes_ssm" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.gpu_nodes.name
}

resource "aws_security_group" "gpu_nodes" {
  name        = "${var.cluster_name}-gpu-nodes-sg"
  description = "Security group for GPU nodes"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

variable "region" {
  type        = string
  description = "AWS Region"
}

variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster"
}

variable "kubernetes_version" {
  type        = string
  default     = "1.29"
  description = "Kubernetes version"
}

variable "gpu_instance_types" {
  type        = list(string)
  default     = ["g5.xlarge"]
  description = "GPU instance types for node group"
}

variable "min_size" {
  type        = number
  default     = 1
  description = "Minimum number of nodes"
}

variable "max_size" {
  type        = number
  default     = 10
  description = "Maximum number of nodes"
}

variable "desired_size" {
  type        = number
  default     = 2
  description = "Desired number of nodes"
}

variable "use_spot_instances" {
  type        = bool
  default     = true
  description = "Use spot instances for cost savings"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply to resources"
}

output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "cluster_ca_certificate" {
  value     = aws_eks_cluster.main.certificate_authority[0].data
  sensitive = true
}

output "node_group_arn" {
  value = aws_eks_node_group.gpu.node_group_arn
}
