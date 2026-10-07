data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${var.cluster_name}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true
}

resource "aws_cloudwatch_event_rule" "karpenter_interruption_spot" {
  name        = "${var.cluster_name}-karpenter-spot"
  description = "Karpenter spot interruption warning"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
}

resource "aws_cloudwatch_event_target" "karpenter_interruption_spot" {
  rule      = aws_cloudwatch_event_rule.karpenter_interruption_spot.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_rebalance" {
  name        = "${var.cluster_name}-karpenter-rebalance"
  description = "Karpenter rebalance recommendation"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance Rebalance Recommendation"]
  })
}

resource "aws_cloudwatch_event_target" "karpenter_rebalance" {
  rule      = aws_cloudwatch_event_rule.karpenter_rebalance.name
  target_id = "KarpenterRebalanceQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_instance_state" {
  name        = "${var.cluster_name}-karpenter-instance-state"
  description = "Karpenter EC2 instance state change"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })
}

resource "aws_cloudwatch_event_target" "karpenter_instance_state" {
  rule      = aws_cloudwatch_event_rule.karpenter_instance_state.name
  target_id = "KarpenterInstanceStateQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridge"
      Effect    = "Allow"
      Principal = { Service = "://amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.karpenter_interruption.arn
    }]
  })
}

resource "aws_iam_role" "karpenter_node" {
  name = "${var.cluster_name}-karpenter-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "://amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "karpenter_node_worker" {
  role       = aws_iam_role.karpenter_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "karpenter_node_cni" {
  role       = aws_iam_role.karpenter_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "karpenter_node_ecr" {
  role       = aws_iam_role.karpenter_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "karpenter_node_ssm" {
  role       = aws_iam_role.karpenter_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "karpenter_node" {
  name = "${var.cluster_name}-karpenter-node"
  role = aws_iam_role.karpenter_node.name
}

resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = var.cluster_name
  principal_arn = aws_iam_role.karpenter_node.arn
  type          = "EC2_LINUX"
}

module "karpenter_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.39"

  role_name                          = "${var.cluster_name}-karpenter-controller"
  attach_karpenter_controller_policy = true

  karpenter_controller_cluster_id         = var.cluster_name
  karpenter_controller_node_iam_role_arns = [aws_iam_role.karpenter_node.arn]

  oidc_providers = {
    main = {
      provider_arn               = local.oidc_provider_arn
      namespace_service_accounts = ["kube-system:karpenter"]
    }
  }
}

resource "kubernetes_service_account" "karpenter" {
  metadata {
    name      = "karpenter"
    namespace = "kube-system"
    annotations = {
      "://amazonaws.com" = module.karpenter_irsa.iam_role_arn
    }
  }
}

resource "time_sleep" "wait_for_alb_webhook" {
  create_duration = "60s"
  depends_on      = [helm_release.aws_lb_controller]
}

resource "helm_release" "karpenter" {
  name       = "karpenter"
  namespace  = "kube-system"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_version

  timeout         = 600
  atomic          = false   
  cleanup_on_fail = false   

  values = [yamlencode({
    serviceAccount = {
      create = false
      name   = kubernetes_service_account.karpenter.metadata[0].name
    }
    settings = {
      clusterName       = var.cluster_name
      clusterEndpoint   = data.aws_eks_cluster.this.endpoint
      interruptionQueue = aws_sqs_queue.karpenter_interruption.name
    }
    # Properly scopes Karpenter pod to match the System Node group
    tolerations = [{
      key      = "CriticalAddonsOnly"
      operator = "Exists"
      effect   = "NoSchedule"
    }]
    nodeSelector = { "node.kubernetes.io/purpose" = "system" }
    controller = {
      resources = {
        requests = { cpu = "100m", memory = "256Mi" }
        limits   = { cpu = "500m", memory = "512Mi" }
      }
    }
  })]

  depends_on = [
    kubernetes_service_account.karpenter,
    time_sleep.wait_for_alb_webhook
  ]
}

resource "time_sleep" "wait_for_karpenter_webhook" {
  create_duration = "90s"
  depends_on      = [helm_release.karpenter]
}

resource "kubectl_manifest" "karpenter_node_class" {
  yaml_body = yamlencode({
    apiVersion = "karpenter.k8s.aws/v1"
    kind       = "EC2NodeClass"
    metadata   = { name = "default" }
    spec = {
      amiFamily = "AL2"
      role      = aws_iam_role.karpenter_node.name
      subnetSelectorTerms = [{
        tags = { "karpenter.sh/discovery" = var.cluster_name }
      }]
      securityGroupSelectorTerms = [{
        tags = { "karpenter.sh/discovery" = var.cluster_name }
      }]
      blockDeviceMappings = [{
        deviceName = "/dev/xvda"
        ebs = {
          volumeSize          = "20Gi"
          volumeType          = "gp3"
          encrypted           = true
          deleteOnTermination = true
        }
      }]
    }
  })
  depends_on = [time_sleep.wait_for_karpenter_webhook]
}

resource "kubectl_manifest" "karpenter_node_pool" {
  yaml_body = yamlencode({
    apiVersion = "karpenter.sh/v1"
    kind       = "NodePool"
    metadata   = { name = "default" }
    spec = {
      template = {
        spec = {
          nodeClassRef = {
            apiVersion = "karpenter.k8s.aws/v1"
            group      = "karpenter.k8s.aws"
            kind       = "EC2NodeClass"
            name       = "default"
          }
          requirements = [
            # 🚀 CHANGED: Enforces only Spot instances for workloads to meet budget goals
            { key = "karpenter.sh/capacity-type",       operator = "In", values = ["spot"] },
            { key = "node.kubernetes.io/instance-type", operator = "In", values = ["t3.medium", "t3a.medium", "t3.large"] },
            { key = "kubernetes.io/arch",               operator = "In", values = ["amd64"] },
            { key = "topology.kubernetes.io/zone",      operator = "In", values = var.availability_zones }
          ]
        }
      }
      limits = { cpu = "8", memory = "16Gi" }
      disruption = {
        consolidationPolicy = "WhenUnderutilized"
        expireAfter         = "720h"
      }
    }
  })
  depends_on = [kubectl_manifest.karpenter_node_class]
}
