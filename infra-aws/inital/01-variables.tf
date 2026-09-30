# filename: 01-variables.tf

variable "aws_region" {
  description = "AWS region — matches your LocalStack config"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "poc | staging | prod"
  type        = string
  default     = "poc"
}

variable "cluster_name" {
  description = "EKS cluster name — used in many resource names and tags"
  type        = string
  default     = "ibts-eks"
}

variable "cluster_version" {
  description = "Kubernetes version — pin this, never use 'latest'"
  type        = string
  default     = "1.30"
}

# ── VPC CIDRs
# /16 gives 65,536 IPs — plenty of room for pods (VPC CNI uses real IPs)
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

# 🚀 FIXED: Expanded to two AZs to satisfy the strict AWS EKS API constraint.
# You can still isolate your actual nodes to 'ap-south-1a' later in Karpenter/NodeGroups.
variable "availability_zones" {
  description = "AZs to use — minimum of 2 required by AWS EKS API"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "private_subnet_cidrs" {
  description = "Private subnets — nodes and pods live here"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "public_subnet_cidrs" {
  description = "Public subnets — ALB and NAT Gateway live here"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

# ── Node sizing
variable "system_node_instance_type" {
  description = "On-Demand instance for system node group"
  type        = string
  default     = "t3.medium" # 2 vCPU, 4GB — fits CoreDNS + Karpenter + LB Controller
}

# ── Spot instance families for Karpenter workload nodes
# Multiple families = fewer interruptions (see architecture explanation)
variable "karpenter_spot_instance_families" {
  description = "EC2 instance families Karpenter can use for Spot"
  type        = list(string)
  default     = ["t3", "t3a", "t2"]
}

variable "karpenter_spot_instance_sizes" {
  description = "EC2 instance sizes Karpenter can use"
  type        = list(string)
  default     = ["medium", "large"]
}

# ── Karpenter version — check https://github.com/aws/karpenter/releases
variable "karpenter_version" {
  description = "Karpenter Helm chart version"
  type        = string
  default     = "0.36.2"
}

# ── AWS LB Controller version
variable "aws_lb_controller_version" {
  description = "AWS Load Balancer Controller Helm chart version"
  type        = string
  default     = "1.8.1"
}
