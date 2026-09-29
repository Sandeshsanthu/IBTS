terraform {
  backend "s3" {
    bucket       = "sandesh-tf-file" # Change to your actual S3 bucket
    key          = "ec2-auto-stop/terraform.tfstate"
    region       = "us-east-1"                       # Change to your bucket's region
    encrypt      = true
    use_lockfile = true                              # Native S3 state locking (Requires Terraform v1.10+)
  }
}
