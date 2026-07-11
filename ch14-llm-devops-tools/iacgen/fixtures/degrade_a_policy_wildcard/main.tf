# RECORDED FIXTURE for Listing 14-3, degradation step A (INTENTIONALLY INSECURE).
#
# DETERMINISTIC ILLUSTRATION, NOT a live LLM run. This stands in for what an
# UNCAPPED refinement loop does when it chases a single finding and regresses.
# Told to "fix the public-read ACL warning but keep the data shareable", the
# model removes the original bucket's public-read ACL (clearing Trivy AWS-0092
# on that bucket) and switches to a bucket policy, but it OVER-CORRECTS: it
# spins up a second "staging copy" bucket that is itself public-read with no
# encryption and no public-access block. The net HIGH-severity count goes UP,
# not down.
#
# This is a deterministic fixture chosen so the real scanners measure a RISING
# blocking count across uncapped iterations. It is NOT a reproduction of the
# +37.6% figure from Shukla et al.; see labs/lab3_degradation.py and the README.
# DO NOT APPLY.

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

# Original bucket: the public-read ACL is gone, replaced by a bucket policy.
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

# OVER-CORRECTION: a second "staging copy" bucket the model added while chasing
# the finding. Also public-read, also unencrypted, also no public-access block.
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
