# Main infrastructure uses the bucket created by infra/bootstrap.
terraform {
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
