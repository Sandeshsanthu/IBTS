# filename: import.tf
# Native Terraform auto-import engine logic to reconcile the state tracking

import {
  to = module.eks.aws_eks_cluster.this[0]
  id = "ibts-eks"
}

import {
  to = aws_vpc.ibts
  id = "vpc-0a2914efe24745aa2" # Matched directly to your active working VPC ID from the logs
}
