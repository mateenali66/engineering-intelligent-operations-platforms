# Chapter 04: Infrastructure as Code in the AI Era

Code for Chapter 4. Each listing in the printed book maps to a file here. The
chapter's thesis: Infrastructure as Code is the provisioning layer beneath the
whole book's reference architecture, and machine-generated IaC is measurably
defective, so you treat every generation as untrusted code and run it through a
scan-and-gate pipeline before `terraform apply`.

| Listing | File | Description |
|---|---|---|
| 4-1 | `k8s/nvidia-device-plugin.yaml` | A minimal NVIDIA device-plugin DaemonSet that advertises `nvidia.com/gpu` so the scheduler can place GPU pods. EKS has no managed add-on for this: install it with the NVIDIA device-plugin Helm chart or the NVIDIA GPU Operator. Bottlerocket accelerated AMIs ship it preinstalled; AL2023 accelerated AMIs do not |
| 4-2 | `clean-module/main.tf` | A clean, hand-written Terraform module: an encrypted, private S3 telemetry bucket and a labeled, tainted EKS GPU node group. The reference to compare generated output against |
| 4-3 | `generated-module/main.tf` | The same module as plausibly generated from a careless prompt, with a real injected misconfiguration: public-access block disabled at the bucket level, no KMS encryption declared, a public-read ACL. INTENTIONALLY INSECURE, do not apply |
| 4-4 | `../.github/workflows/ci.yml` (jobs `iac-clean` and `iac-insecure`) | GitHub Actions workflow that runs Checkov and Trivy against the Terraform. The scan logic from the chapter lives in the companion-repo root workflow because GitHub Actions only executes workflows in the repository root `.github/workflows/`. The file `.github/workflows/iac-scan.yml` in this directory is a non-executing reference copy retained for the book listing; see the comment block at its top |
| 4-5 | `policy/s3_encryption.rego` | An OPA/Conftest policy enforcing one house rule: every S3 bucket must declare an explicit server-side encryption configuration |
| support | `clean-module/versions.tf` | The single provider-requirements block (aws, kubernetes) for the clean module |
| support | `clean-module/hardening.tf` | The customer-managed KMS key, access-log bucket, lifecycle rules, KMS key policy, and event notifications that let the module pass the HIGH/CRITICAL gate cleanly (kept out of the printed listing for focus) |
| support | `clean-module/iam.tf` | Node IAM role and the `subnet_ids` input the GPU node group depends on |
| support | `clean-module/device-plugin.tf` | The NVIDIA device-plugin DaemonSet: a GPU node is not schedulable until the plugin advertises `nvidia.com/gpu` (Section 4.3) |
| prompts | `prompts.md` | The prompts that reproduce the lab: the careless prompt that creates the defect, a careful prompt, and the fix-loop prompt |
| versions | `versions.md` | Pinned tool versions and 2026 scanner-landscape notes |

## Pinned versions

See `versions.md`. The short list: Terraform 1.15.6 / OpenTofu 1.12.3, AWS
provider 6.58.0, Checkov 3.3.1, Trivy 0.71.1, Conftest 0.68.2.

## Run the lab (Section 4.8)

```bash
# 1. Generate a module with a model using prompts.md (or use generated-module/).

# 2. Scan it. Both should fail (exit non-zero) on the generated module.
#    Note: gate Checkov on any failed check, NOT --hard-fail-on HIGH, because
#    many OSS community checks carry no severity and slip past a severity filter.
checkov --directory generated-module --quiet --compact
trivy config generated-module --severity HIGH,CRITICAL --exit-code 1

# 3. Policy-gate it against the plan JSON. The deny rule fires.
terraform -chdir=generated-module init -backend=false
terraform -chdir=generated-module plan -out tfplan
terraform -chdir=generated-module show -json tfplan > plan.json
conftest test plan.json --policy policy

# 4. Fix the module (make it look like clean-module/), then re-run the scans
#    and the policy. They pass. Now a human reviews the diff, and only then:
terraform -chdir=clean-module plan
```

## Warning

`generated-module/main.tf` is deliberately insecure so the pipeline has a real
defect to catch. Never apply it. It exists only to be blocked.
