# Prompts for the Chapter 4 lab

The lab in Section 4.8 starts by asking a model to generate the module our
running SaaS team needs, then runs the output through the scan-and-gate
pipeline. These are the prompts to reproduce it. The point is not which model
you use. The point is that the output is untrusted code until the pipeline
clears it.

## Prompt 1: the careless prompt (reproduces the defect)

> Write me Terraform for a public-facing data bucket for telemetry exports.

This is the prompt that produces something close to `generated-module/main.tf`:
a world-readable bucket with no encryption. Run it through the pipeline and
watch it fail. This is the breach from the opening of the chapter.

## Prompt 2: the careful prompt (better, still scan it)

> Write a Terraform module for an AWS S3 bucket named "telemetry-lake" that
> holds internal telemetry exports. It must be private with all public access
> blocked, encrypted at rest with KMS, and versioned. Target the AWS provider
> version 6.x and Terraform 1.9 or newer. Do not enable any public ACL.

A specific, security-aware prompt produces much safer output, closer to
`clean-module/main.tf`. It is still untrusted code. Scan it anyway, because a
better prompt lowers the defect rate, it does not eliminate it.

## Prompt 3: feeding findings back (the fix loop)

After the scanners flag the generated module, you can paste the findings back:

> Here are the Checkov and Trivy findings for the module you wrote. Fix every
> high-severity finding: add an aws_s3_bucket_public_access_block that blocks
> all public access, add a server-side encryption configuration using KMS,
> remove the public-read ACL, and add versioning. Return the corrected module.

This is a legitimate use of the tool, as long as the corrected output goes back
through the same gate before it reaches plan and apply.
