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

  # ✅ KEEP THIS: Switches authentication mode to handle API entries
  authentication_mode = "API_AND_CONFIG_MAP"

  # ✅ KEEP THIS: Natively maps your GitHub Actions role as cluster admin
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

  # ❌ REMOVED: Your custom github_actions map block has been removed 
  # to prevent the duplicate 409 ResourceInUseException.
  access_entries = {} 

  tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }
}
