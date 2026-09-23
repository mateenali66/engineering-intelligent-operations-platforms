# WARNING: This file is INTENTIONALLY INSECURE. It is the representative output
# of a careless "write me Terraform for a public-facing data bucket" prompt
# (Listing 4-3, Section 4.5). It is here so the scan-and-gate pipeline in
# Chapter 4 has a real defect to catch. DO NOT APPLY THIS MODULE.
#
# Defects, on purpose:
#   - aws_s3_bucket_public_access_block with all four flags false (the model
#     disabled the bucket's guardrail because the prompt said "public-facing";
#     since April 2023 this is what makes the public ACL below take effect,
#     unless account-level Block Public Access is on, which would still block it)
#   - no server-side encryption configuration (no KMS key; S3 still applies its
#     default SSE-S3 encryption to new objects, which cannot be turned off)
#   - acl = "public-read" (the bucket is world-readable)
#   - no versioning

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

# Public-facing data bucket for telemetry exports.
resource "aws_s3_bucket" "telemetry" {
  bucket = var.name
}

# The prompt said "public-facing", so the model turned off this bucket's Block
# Public Access. Since April 2023 new buckets block public access and disable
# ACLs by default, so without this the public-read ACL below would be rejected
# at apply. An account-level Block Public Access setting would still refuse it.
resource "aws_s3_bucket_public_access_block" "telemetry" {
  bucket                  = aws_s3_bucket.telemetry.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
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
