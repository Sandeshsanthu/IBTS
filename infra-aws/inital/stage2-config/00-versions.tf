# filename: infra-aws/stage2-config/00-versions.tf


terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.47"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.0"
    }
  }

  backend "s3" {
    bucket       = "sandesh-tf-file"
    key          = "ibts-eks/stage2/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "ibts"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ══════════════════════════════════════════════════════
# READ STAGE 1 OUTPUTS
# Cluster guaranteed to exist — stage2 runs after stage1
# ══════════════════════════════════════════════════════
data "terraform_remote_state" "stage1" {
  backend = "s3"
  config = {
    bucket = "sandesh-tf-file"
    key    = "ibts-eks/stage1/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  cluster_name     = data.terraform_remote_state.stage1.outputs.cluster_name
  cluster_endpoint = data.terraform_remote_state.stage1.outputs.cluster_endpoint
  cluster_ca       = base64decode(
    data.terraform_remote_state.stage1.outputs.cluster_certificate_authority_data
  )
}

# ══════════════════════════════════════════════════════
# PROVIDERS — use exec instead of static token
#
# WHY exec and NOT aws_eks_cluster_auth data source:
#   aws_eks_cluster_auth token expires after 15 minutes
#   Long applies (20+ mins) hit "Unauthorized" errors
#   exec fetches a FRESH token on every single API call
#   → never expires mid-apply
# ══════════════════════════════════════════════════════
provider "kubernetes" {
  host                   = local.cluster_endpoint
  cluster_ca_certificate = local.cluster_ca

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks", "get-token",
      "--cluster-name", local.cluster_name,
      "--region", var.aws_region
    ]
  }
}

provider "helm" {
  kubernetes {
    host                   = local.cluster_endpoint
    cluster_ca_certificate = local.cluster_ca

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks", "get-token",
        "--cluster-name", local.cluster_name,
        "--region", var.aws_region
      ]
    }
  }
}

provider "kubectl" {
  host                   = local.cluster_endpoint
  cluster_ca_certificate = local.cluster_ca
  load_config_file       = false

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks", "get-token",
      "--cluster-name", local.cluster_name,
      "--region", var.aws_region
    ]
  }
}
