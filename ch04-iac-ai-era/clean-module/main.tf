# Listing 4-2 (Section 4.3). The provider-requirements block lives in
# versions.tf; the customer-managed KMS key and the access-log bucket that let
# this module pass the HIGH/CRITICAL gate cleanly live in hardening.tf; the node
# IAM role and the device plugin live in iam.tf and device-plugin.tf. main.tf
# holds the core resources the printed listing shows.

variable "name" {
  type    = string
  default = "telemetry-lake"
}

variable "cluster_name" {
  type    = string
  default = "saas-platform"
}

# Telemetry lake: private and encrypted by default.
resource "aws_s3_bucket" "telemetry" {
  #checkov:skip=CKV_AWS_144:Cross-region replication is a per-deployment choice
  bucket = var.name
}

resource "aws_s3_bucket_public_access_block" "telemetry" {
  bucket                  = aws_s3_bucket.telemetry.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.telemetry.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  versioning_configuration {
    status = "Enabled"
  }
}

# GPU node group: labeled and tainted so only GPU workloads land here.
resource "aws_eks_node_group" "gpu" {
  cluster_name    = var.cluster_name
  node_group_name = "gpu-workers"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = ["g5.xlarge"]

  scaling_config {
    desired_size = 1
    min_size     = 0
    max_size     = 4
  }

  labels = {
    "workload-type" = "gpu"
  }

  taint {
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }
}
