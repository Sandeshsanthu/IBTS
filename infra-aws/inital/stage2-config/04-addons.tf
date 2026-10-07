# ── EKS managed addons — need OIDC which comes from stage1
resource "aws_eks_addon" "pod_identity" {
  cluster_name                = var.cluster_name
  addon_name                  = "eks-pod-identity-agent"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "coredns" {
  cluster_name                = var.cluster_name
  addon_name                  = "coredns"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  # Ensure CoreDNS can schedule onto your tainted system node
  configuration_values = jsonencode({
    tolerations = [{
      key      = "CriticalAddonsOnly"
      operator = "Exists"
      effect   = "NoSchedule"
    }]
  })
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = var.cluster_name
  addon_name                  = "kube-proxy"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = var.cluster_name
  addon_name                  = "vpc-cni"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name                = var.cluster_name
  addon_name                  = "aws-ebs-csi-driver"
  service_account_role_arn    = module.ebs_csi_irsa.iam_role_arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [module.ebs_csi_irsa]
}

# ── gp3 storage class
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
  depends_on = [aws_eks_addon.ebs_csi]
}

# ── ALB controller
resource "helm_release" "aws_lb_controller" {
  namespace  = "kube-system"
  name       = "aws-load-balancer-controller"
  repository = "https://github.io"
  chart      = "aws-load-balancer-controller"
  version    = var.aws_lb_controller_version

  values = [yamlencode({
    clusterName = var.cluster_name
    region      = var.aws_region
    vpcId       = data.terraform_remote_state.stage1.outputs.vpc_id
    serviceAccount = {
      create = true
      name   = "aws-load-balancer-controller"
      annotations = {
        "://amazonaws.com" = module.irsa_aws_lb_controller.iam_role_arn
      }
    }
    tolerations = [{ key = "CriticalAddonsOnly", operator = "Exists", effect = "NoSchedule" }]
    nodeSelector = { "node.kubernetes.io/purpose" = "system" }
    enableWaf    = false
    enableWafv2  = false
    enableShield = false
    replicaCount = 1
  })]

  depends_on = [module.irsa_aws_lb_controller]
}

# ── Metrics server
resource "helm_release" "metrics_server" {
  namespace  = "kube-system"
  name       = "metrics-server"
  repository = "https://github.io"
  chart      = "metrics-server"
  version    = "3.12.1"

  values = [yamlencode({
    tolerations  = [{ key = "CriticalAddonsOnly", operator = "Exists", effect = "NoSchedule" }]
    nodeSelector = { "node.kubernetes.io/purpose" = "system" }
    args         = ["--kubelet-insecure-tls"]
  })]
}
