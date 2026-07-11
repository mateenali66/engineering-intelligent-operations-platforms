# RECORDED FIXTURE for Listing 14-3, degradation step B (INTENTIONALLY INSECURE).
#
# DETERMINISTIC ILLUSTRATION, NOT a live LLM run. The uncapped loop runs again.
# Told to "fix the staging bucket findings", the model adds a THIRD exposed
# bucket (a "backup copy") instead of converging. The real scanners measure the
# HIGH-severity count rising a second time. This is the uncapped failure mode:
# each pass chases findings and adds surface, so the count climbs instead of
# reaching zero. A bounded loop would have stopped after the budget and failed
# the build cleanly on the first non-clean module.
#
# Deterministic fixture, not a reproduction of Shukla et al.'s +37.6%. DO NOT APPLY.

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

resource "aws_s3_bucket" "telemetry" {
  bucket = var.name
}

resource "aws_s3_bucket_policy" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadAll"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = ["arn:aws:s3:::telemetry-lake/*"]
    }]
  })
}

resource "aws_s3_bucket" "telemetry_staging" {
  bucket = "${var.name}-staging"
}

resource "aws_s3_bucket_ownership_controls" "telemetry_staging" {
  bucket = aws_s3_bucket.telemetry_staging.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "telemetry_staging" {
  depends_on = [aws_s3_bucket_ownership_controls.telemetry_staging]
  bucket     = aws_s3_bucket.telemetry_staging.id
  acl        = "public-read"
}

# A THIRD exposed bucket added on the next uncapped pass.
resource "aws_s3_bucket" "telemetry_backup" {
  bucket = "${var.name}-backup"
}

resource "aws_s3_bucket_ownership_controls" "telemetry_backup" {
  bucket = aws_s3_bucket.telemetry_backup.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "telemetry_backup" {
  depends_on = [aws_s3_bucket_ownership_controls.telemetry_backup]
  bucket     = aws_s3_bucket.telemetry_backup.id
  acl        = "public-read"
}
