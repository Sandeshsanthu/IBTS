# filename: infra-aws/stage1-cluster/03-eks-cluster.tf

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

  # ✅ STEP 1: Enable the API access entries feature (CRITICAL FIX)
  authentication_mode = "API_AND_CONFIG_MAP"

  # ✅ STEP 2: Restore this flag. It prevents Stage 1 from locking itself 
  # out during creation, and works alongside your access_entries block.
  enable_cluster_creator_admin_permissions = true

  cluster_enabled_log_types = ["api", "audit"]

  cluster_addons = {}

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

  # ✅ Valid explicit entry for the pipeline role across all future sessions
  access_entries = {
    github_actions = {
      principal_arn = "arn:aws:iam::149614785419:role/github-actions-terraform-role"

      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }
}
