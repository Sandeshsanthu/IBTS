terraform {
  backend "s3" {
  bucket = "sandesh-tf-file"
  key    = "ibts-eks/terraform.tfstate"   # ← ONLY THIS LINE CHANGES
  region       = "us-east-1"
  encrypt      = true
  use_lockfile = true
}
}
