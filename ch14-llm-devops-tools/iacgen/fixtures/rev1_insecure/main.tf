# RECORDED FIXTURE, revision 1 (INTENTIONALLY INSECURE).
#
# This is the recorded output of generate("a secure S3 bucket Terraform
# module for telemetry exports"). It stands in for a live LLM call: the
# generate() step in iacgen returns this file verbatim instead of calling a
# model, so the lab runs headless in CI with no API key. The SCANNERS that run
# over it (Checkov 3.3.1, Trivy 0.71.1) are real.
#
# It is the exact failure Chapter 4 and Chapter 14 warn about: the prompt asked
# for a "secure" bucket and the model produced a public-read, non-KMS-encrypted,
# unversioned, unlogged bucket. DO NOT APPLY.
#
# Defects, on purpose:
#   - acl = "public-read"                  (world-readable)
#   - no aws_s3_bucket_public_access_block (nothing blocks public access)
#   - no server-side encryption config     (no KMS key; default SSE-S3 only)
#   - no versioning                        (no object recovery)
#   - no access logging                    (no audit trail)

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

resource "aws_s3_bucket_ownership_controls" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "telemetry" {
  depends_on = [aws_s3_bucket_ownership_controls.telemetry]
  bucket     = aws_s3_bucket.telemetry.id
  acl        = "public-read"
}
