# Extra hardening kept out of the printed Listing 4-2 for focus, but required
# for the clean module to pass the HIGH/CRITICAL scanner gate cleanly:
#   - a customer-managed KMS key (Trivy AWS-0132 wants a CMK, not the AWS key)
#   - an access-log destination bucket, itself private and encrypted

resource "aws_kms_key" "telemetry" {
  description             = "CMK for the telemetry lake"
  enable_key_rotation     = true
  deletion_window_in_days = 7
}

resource "aws_s3_bucket" "telemetry_logs" {
  #checkov:skip=CKV_AWS_144:Log bucket does not need cross-region replication
  #checkov:skip=CKV_AWS_18:This IS the access-log destination bucket
  #checkov:skip=CKV_AWS_145:AWS prohibits SSE-KMS on logging destination buckets; AES256 (SSE-S3) is the correct and only supported algorithm here
  bucket = "${var.name}-logs"
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
      # AWS does not support SSE-KMS on a logging destination bucket.
      # S3-managed keys (AES256 / SSE-S3) are the required algorithm here.
      # Checkov CKV_AWS_145 and Trivy AWS-0132 are suppressed with narrow
      # inline skips because this IS the access-log destination; AES256 is
      # not a downgrade, it is the only algorithm AWS permits for this role.
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

resource "aws_s3_bucket_logging" "telemetry" {
  bucket        = aws_s3_bucket.telemetry.id
  target_bucket = aws_s3_bucket.telemetry_logs.id
  target_prefix = "access-logs/"
}

# An explicit key policy so the CMK is not left on the implicit default.
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

# Lifecycle rules: expire old telemetry and clean up old log objects.
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

# Event notifications: telemetry writes fan out to an SNS topic the feature
# pipeline can subscribe to.
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
