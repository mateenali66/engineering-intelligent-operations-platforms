# RECORDED FIXTURE, revision 2 (HARDENED, gate-clean).
#
# This is the recorded output of repair(rev1, findings): the model is handed the
# Checkov + Trivy findings from rev1 and returns a corrected module. iacgen's
# repair() step returns this file verbatim instead of calling a model, so the
# loop runs headless. The scanners that re-scan it are real.
#
# Every rev1 defect is fixed:
#   - public-read ACL removed; ownership set to BucketOwnerEnforced (ACLs off)
#   - aws_s3_bucket_public_access_block blocks all four public-access vectors
#   - SSE configured with a customer-managed KMS key (CMK), bucket key enabled
#   - versioning enabled
#   - access logging to a private, encrypted, versioned log bucket
#   - CMK key policy, lifecycle rules, and event notifications added
#
# This module passes Checkov 3.3.1 (any-failed-check gate) and
# Trivy 0.71.1 config (--severity HIGH,CRITICAL --exit-code 1), and the
# OPA/Conftest s3_encryption.rego gate, with the same narrow, documented
# inline skips the Chapter 4 clean-module uses for the log-bucket edge cases
# (a logging destination bucket cannot itself be logged, and AWS forbids
# SSE-KMS on it, so AES256 is the only permitted algorithm there).

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "name" {
  type    = string
  default = "telemetry-lake"
}

# ---------------------------------------------------------------------------
# Telemetry lake: private and encrypted by default.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "telemetry" {
  #checkov:skip=CKV_AWS_144:Cross-region replication is a per-deployment choice
  bucket = var.name
}

resource "aws_s3_bucket_ownership_controls" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "telemetry" {
  bucket                  = aws_s3_bucket.telemetry.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_kms_key" "telemetry" {
  description             = "CMK for the telemetry lake"
  enable_key_rotation     = true
  deletion_window_in_days = 7
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

resource "aws_s3_bucket_logging" "telemetry" {
  bucket        = aws_s3_bucket.telemetry.id
  target_bucket = aws_s3_bucket.telemetry_logs.id
  target_prefix = "access-logs/"
}

resource "aws_s3_bucket_lifecycle_configuration" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  rule {
    id     = "expire-old-telemetry"
    status = "Enabled"
    filter {}
    expiration {
      days = 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ---------------------------------------------------------------------------
# Access-log destination bucket: private, encrypted, versioned.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "telemetry_logs" {
  #checkov:skip=CKV_AWS_144:Log bucket does not need cross-region replication
  #checkov:skip=CKV_AWS_18:This IS the access-log destination bucket
  #checkov:skip=CKV_AWS_145:AWS prohibits SSE-KMS on logging destination buckets; AES256 (SSE-S3) is the correct and only supported algorithm here
  bucket = "${var.name}-logs"
}

resource "aws_s3_bucket_ownership_controls" "telemetry_logs" {
  bucket = aws_s3_bucket.telemetry_logs.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "telemetry_logs" {
  bucket                  = aws_s3_bucket.telemetry_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

#trivy:ignore:AVD-AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "telemetry_logs" {
  bucket = aws_s3_bucket.telemetry_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "telemetry_logs" {
  bucket = aws_s3_bucket.telemetry_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "telemetry_logs" {
  bucket = aws_s3_bucket.telemetry_logs.id
  rule {
    id     = "expire-old-access-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ---------------------------------------------------------------------------
# CMK key policy and event notifications.
# ---------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_kms_key_policy" "telemetry" {
  key_id = aws_kms_key.telemetry.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowAccountAdmin"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
      Action    = "kms:*"
      Resource  = "*"
    }]
  })
}

resource "aws_sns_topic" "telemetry_events" {
  name              = "${var.name}-events"
  kms_master_key_id = aws_kms_key.telemetry.id
}

resource "aws_s3_bucket_notification" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  topic {
    topic_arn = aws_sns_topic.telemetry_events.arn
    events    = ["s3:ObjectCreated:*"]
  }
}

resource "aws_s3_bucket_notification" "telemetry_logs" {
  bucket = aws_s3_bucket.telemetry_logs.id
  topic {
    topic_arn = aws_sns_topic.telemetry_events.arn
    events    = ["s3:ObjectCreated:*"]
  }
}
