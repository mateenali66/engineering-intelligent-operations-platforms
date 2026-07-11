# Listing 4-5 (Section 4.7): an organization house rule. Every S3 bucket must
# have a matching server-side encryption configuration. Correlation is on the
# SSE config's `bucket` argument (the actual reference to the bucket resource)
# rather than on the Terraform resource label, so a differently-named SSE
# config still satisfies its target bucket and a mismatched label does not
# produce a false pass.
#
# Run with Conftest against the JSON form of a Terraform plan:
#
#   terraform -chdir=clean-module init -backend=false
#   terraform -chdir=clean-module plan -out tfplan
#   terraform -chdir=clean-module show -json tfplan > plan.json
#   conftest test plan.json --policy policy
#
# Against generated-module (no SSE resource) the deny rule fires.
# Against clean-module it passes.
# A bucket with a differently-named SSE config also passes (Case 1 below).
#
# The fixtures in testdata/ are trimmed from real `terraform show -json`
# output (Terraform 1.5.7, AWS provider 6.54.0): only the S3 bucket and SSE
# entries in resource_changes and configuration are kept, unmodified.

package main

# Collect the address of every S3 bucket declared in the plan.
buckets contains addr if {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  addr := resource.address
}

# Collect the addresses of buckets that have an SSE configuration.
#
# Case 1: the SSE config's bucket argument is known at plan time (a literal
# name or a known variable), so the plan records it in change.after. Compare
# it against every bucket's planned name; resource labels play no part.
encrypted contains bucket_addr if {
  sse := input.resource_changes[_]
  sse.type == "aws_s3_bucket_server_side_encryption_configuration"

  bucket := input.resource_changes[_]
  bucket.type == "aws_s3_bucket"
  sse.change.after.bucket == bucket.change.after.bucket
  bucket_addr := bucket.address
}

# Case 2: the SSE config's bucket argument is a resource reference (e.g.
# aws_s3_bucket.telemetry.id), unknown until apply. The plan OMITS it from
# change.after and marks change.after_unknown.bucket = true; the reference
# itself is recorded in the plan's configuration section. Resolve it there:
# the references list for the bucket argument names the target bucket address.
encrypted contains bucket_addr if {
  sse := input.configuration.root_module.resources[_]
  sse.type == "aws_s3_bucket_server_side_encryption_configuration"

  ref := sse.expressions.bucket.references[_]
  some bucket_addr in buckets
  bucket_addr == ref
}

# Deny any bucket that lacks a matching encryption configuration.
deny contains msg if {
  some bucket_addr in buckets
  not encrypted[bucket_addr]
  label := trim_prefix(bucket_addr, "aws_s3_bucket.")
  msg := sprintf(
    "S3 bucket '%s' has no server-side encryption configuration",
    [label],
  )
}
