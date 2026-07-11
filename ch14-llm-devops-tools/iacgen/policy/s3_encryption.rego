package main

# Listing 4-4 (Section 4.7): an organization house rule. Every S3 bucket must
# have a matching server-side encryption configuration. Correlation is on the
# SSE config's `bucket` argument (which references the bucket resource's `id`)
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

# Collect the address of every S3 bucket declared in the plan.
buckets contains addr if {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  addr := resource.address
}

# Collect the addresses of buckets that have an SSE configuration pointing at
# them, using two complementary cases:
#
# Case 1: the SSE config's `bucket` argument value is KNOWN at plan time (the
# bucket name is a literal or comes from a known variable). We compare the
# planned bucket name in the SSE config against the planned bucket name of
# every aws_s3_bucket resource. This handles differently-named SSE configs
# correctly because it matches on the actual bucket value, not on Terraform
# resource labels.
encrypted contains bucket_addr if {
  sse := input.resource_changes[_]
  sse.type == "aws_s3_bucket_server_side_encryption_configuration"
  not sse.change.after_unknown.bucket # bucket value is known at plan time

  bucket := input.resource_changes[_]
  bucket.type == "aws_s3_bucket"
  # The SSE config's planned bucket value equals the bucket's planned name.
  sse.change.after.bucket == bucket.change.after.bucket
  bucket_addr := bucket.address
}

# Case 2: the SSE config's `bucket` argument is UNKNOWN at plan time because
# it is a resource reference (e.g. `aws_s3_bucket.telemetry.id`). Terraform
# records the reference string in `after.bucket` in the form
# "${aws_s3_bucket.<label>.id}" and marks `after_unknown.bucket = true`.
# We parse the referenced resource label out of that string to build the
# expected bucket address and match it against the bucket list.
encrypted contains bucket_addr if {
  sse := input.resource_changes[_]
  sse.type == "aws_s3_bucket_server_side_encryption_configuration"
  sse.change.after_unknown.bucket == true # bucket is a resource reference

  # The reference string has the form "${aws_s3_bucket.<label>.id}".
  # Extract <label> by stripping the known prefix and suffix.
  ref := sse.change.after.bucket
  startswith(ref, "${aws_s3_bucket.")
  endswith(ref, ".id}")
  inner := trim_prefix(ref, "${aws_s3_bucket.")
  label := trim_suffix(inner, ".id}")

  expected_addr := concat(".", ["aws_s3_bucket", label])
  some bucket_addr in buckets
  bucket_addr == expected_addr
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
