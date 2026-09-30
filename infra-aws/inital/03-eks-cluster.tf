# filename: 03-eks-cluster.tf
# Source: https://terraform.io
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.11"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  # ── Network placement
  vpc_id     = aws_vpc.ibts.id
  subnet_ids = aws_subnet.private[*].id

  # ── Private endpoint with POC convenience toggles
  cluster_endpoint_public_access  = true # Set false in prod; keep true for POC convenience
  cluster_endpoint_private_access = true

  # ── OIDC Provider — foundation of IRSA
  enable_irsa = true

  # ── Control plane logging
  cluster_enabled_log_types = ["api", "audit"]

  # ── EKS Managed Addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # ── Node security group rules
  # Allows inter-pod communication securely within cluster internal space
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

  tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }
}

# ==============================================================================
# 2. STANDALONE SECURITY GROUP RULES (BREAKS CIRCULAR DEPENDENCIES)
# ==============================================================================
# 🚀 FIXED: Extracted this inline rule to map directly after EKS module builds its native SGs
resource "aws_security_group_rule" "ingress_alb_to_nodes" {
  description              = "Allow ALB to reach pods on node high ports"
  type                     = "ingress"
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = module.eks.node_security_group_id # Attaches directly to the generated EKS SG
}

# ==============================================================================
# 3. ALB SECURITY GROUP CONFIGURATION
# ==============================================================================
resource "aws_security_group" "alb" {
  name        = "${var.cluster_name}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.ibts.id

  ingress {
    description = "HTTP from Global Accelerator / internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from Global Accelerator / internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound to reach pod target groups"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.cluster_name}-alb-sg" }
}

# ==============================================================================
# 4. IDENTITY BLOCK (IRSA FOR EBS STORAGE BACKING)
# ==============================================================================
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.39"

  role_name             = "${var.cluster_name}-ebs-csi-driver"
  attach_ebs_csi_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# ==============================================================================
# 5. STORAGE CLASS INTERACTION WITH CLUSTER STATE
# ==============================================================================
resource "kubernetes_storage_class" "gp3" {
  metadata {
    name = "gp3"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner    = "://aws.com"
  reclaim_policy         = "Retain"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    type      = "gp3"
    encrypted = "true"
  }

  depends_on = [module.eks]
}
