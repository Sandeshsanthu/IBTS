module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.11"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = aws_vpc.ibts.id
  subnet_ids = aws_subnet.private[*].id

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  enable_irsa = true

  # ✅ Switches authentication mode to handle API entries
  authentication_mode = "API_AND_CONFIG_MAP"

  # ✅ Natively maps your GitHub Actions role as cluster admin
  enable_cluster_creator_admin_permissions = true

  cluster_enabled_log_types = ["api", "audit"]
  cluster_addons             = {}

  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
  }

  access_entries = {} 

  tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }

  # 🚀 ADDED: System Node Group Strategy (On-Demand)
  eks_managed_node_groups = {
    system = {
      name           = "eks-system-nodes"
      instance_types = ["t3.medium"]

      # Fixed capacity of 1 node as planned
      min_size     = 1
      max_size     = 1
      desired_size = 1

      # Force nodes to be On-Demand for core infrastructure stability
      capacity_type = "ON_DEMAND"

      # Structural selectors for Core Addons and Karpenter
      labels = {
        "node.kubernetes.io/purpose" = "system"
      }

      taints = {
        addons = {
          key    = "CriticalAddonsOnly"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }
}
