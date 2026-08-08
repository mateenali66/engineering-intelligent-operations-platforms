# Pinned versions for Chapter 4

Every tool below is pinned to the version used to write and test the listings.
An unpinned scanner that updates its rule set overnight will change your build's
behavior without a single line of your code changing, so pin everything in a
security gate.

| Component | Version | Why pinned |
|---|---|---|
| Terraform | 1.15.6 | HCL and `required_version >= 1.9` baseline |
| OpenTofu | 1.12.3 | drop-in alternative; the modules run under both `terraform` and `tofu` |
| hashicorp/aws provider | 6.58.0 (`~> 6.0`) | S3 and EKS resource syntax in Listings 4-1 and 4-2 |
| hashicorp/kubernetes provider | 2.x (`~> 2.0`) | NVIDIA device-plugin DaemonSet |
| Checkov | 3.3.1 | broad built-in IaC policy library; the day-one workhorse |
| Trivy | 0.71.1 | config, secret, and vulnerability scanning; absorbed tfsec in 2023 |
| Conftest | 0.68.2 | runs the OPA/Rego house-rule policy against the plan JSON |
| Python | 3.12 | runs Checkov in CI |

## Tool notes (2026)

- tfsec was merged into Trivy in 2023 (final tfsec maintenance release 2024).
  Use `trivy config` instead of tfsec.
- Terrascan was archived by its maintainer in November 2025. Do not adopt it
  for new work.
- Checkov gotcha: `--hard-fail-on HIGH` can pass the build even with real
  findings, because many open-source community checks carry no severity and
  slip past the severity filter. Gate on any failed check instead (plain
  `checkov --directory ... --quiet --compact` exits non-zero on any failure).
  Trivy is reliable with `--severity HIGH,CRITICAL --exit-code 1`, since it
  assigns severities to its config checks.
- Conftest evaluates the JSON form of a Terraform plan
  (`terraform show -json tfplan`), so the policy checks what will actually be
  created, not just the source.
