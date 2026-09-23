# Chapter 14: Building LLM-Powered DevOps Tools

Code listings for Chapter 14. The running example is **iacgen**: a CLI that takes
a natural-language request, generates Terraform, scans it in parallel with
multiple security scanners, runs a BOUNDED generate-scan-repair loop, fails closed
on blocking findings (HIGH, CRITICAL, or unranked) and scanner errors, runs an OPA policy gate, and emits SARIF for GitHub code scanning.

It is the operational counterpart to Chapter 4: Chapter 4 builds the scan-and-gate
pipeline for IaC; Chapter 14 wraps a model around it and shows how to build a
tool that generates IaC safely, including the failure mode where unbounded
refinement makes things worse.

| Listing | File | Description | CI |
|---|---|---|---|
| 14-1 | `iacgen/labs/lab1_generate_scan.py` | generate (stubbed LLM) + scan with Checkov AND Trivy in parallel; report findings by severity | RUNS |
| 14-2 | `iacgen/labs/lab2_loop_gate_sarif.py` | the bounded generate-scan-repair loop + OPA/Conftest gate + SARIF 2.1.0 emission | RUNS |
| 14-3 | `iacgen/labs/lab3_degradation.py` | the refinement-degradation paradox: uncapped refinement ADDS vulnerabilities (deterministic illustration) | RUNS |
| support | `iacgen/iacgen/` | the `iacgen` package: `generate`, `scanners`, `loop`, `gate`, `sarif`, `cli` | RUNS |
| support | `iacgen/fixtures/` | recorded Terraform: `rev1_insecure`, `rev2_hardened`, two degrade revisions, plus recorded `plan.json` for the gate | n/a |
| support | `iacgen/policy/s3_encryption.rego` | the Chapter 4 house-rule policy, reused unchanged | RUNS |
| - | `iacgen/run_smoke.py` | headless end-to-end smoke test; prints `smoke: ok` | RUNS |
| - | `iacgen/tests/test_iacgen.py` | pytest CI assertions | RUNS |

## The honest CI-vs-LLM split

CI has **no LLM API key and no network egress for generation**. The split is the
same one Chapters 11, 12, and 13 use.

**Stubbed (recorded fixtures, no model call):**
- `generate(prompt)` returns the recorded `rev1_insecure` module: the realistic,
  insecure Terraform a careless prompt produces (public-read ACL, no KMS encryption,
  no versioning, no logging, no public-access block).
- `repair(module, findings)` returns the next recorded revision (`rev2_hardened`),
  the corrected module a repair prompt produces.
- The live shapes (`production_generate` / `production_repair`) are in
  `iacgen/generate.py` as docstrings; they are never called in CI.

**Real (runs for real against the fixtures):**
- Checkov 3.3.1 and Trivy 0.71.1 config scan the modules, in parallel.
- The bounded loop, the fail-closed gate, and the retry budget.
- The OPA/Conftest 0.68.2 policy gate (against the recorded `plan.json`).
- SARIF 2.1.0 emission and validation.

So the numbers you see in the trace are what the real scanners produce on the
recorded fixtures, not invented counts.

## Pinned versions (match Chapter 4)

| Tool | Version | Install |
|---|---|---|
| Checkov | 3.3.1 | `pip install checkov==3.3.1` |
| Trivy | 0.71.1 | upstream `install.sh -b <dir> v0.71.1` (binary, not pip) |
| Conftest | 0.68.2 | GitHub release tarball (binary, not pip) |
| Python | 3.14 | `uv venv --python 3.14` |
| pytest | 8.3.4 | `pip install pytest==8.3.4` |

## Run the labs

```bash
cd iacgen

# Isolated env with the pinned Checkov.
uv venv --python 3.14 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -r requirements.txt

# Pinned Trivy + Conftest binaries into ./.tools (the package finds them there).
mkdir -p .tools
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
  | sh -s -- -b "$PWD/.tools" v0.71.1
# Conftest: pick the asset for your OS/arch from the v0.68.2 release.
# Linux x86_64 shown; macOS uses conftest_0.68.2_Darwin_arm64.tar.gz.
curl -sSL https://github.com/open-policy-agent/conftest/releases/download/v0.68.2/conftest_0.68.2_Linux_x86_64.tar.gz \
  | tar -xz -C .tools conftest

export PYTHONPATH=$PWD

# Warm Trivy's checks bundle once (first run pulls it from ghcr.io), then every
# scan uses --skip-check-update so the loop is offline and deterministic.
.tools/trivy config fixtures/rev1_insecure --severity HIGH,CRITICAL || true

.venv/bin/python labs/lab1_generate_scan.py     # generate + scan
.venv/bin/python labs/lab2_loop_gate_sarif.py   # bounded loop + gate + SARIF
.venv/bin/python labs/lab3_degradation.py       # the degradation paradox
.venv/bin/python run_smoke.py                   # -> smoke: ok
.venv/bin/python -m pytest tests/ -q

# The CLI as a CI gate:
.venv/bin/python -m iacgen "a secure S3 bucket Terraform module" \
  --max-passes 3 --sarif iacgen.sarif
```

## What the loop trace looks like (real scanner counts)

```
pass 1: 15 blocking (18 total; HIGH=6, LOW=2, MEDIUM=1, UNKNOWN=9) -> repair()
pass 2: 0 blocking (1 total; LOW=1)
converged: 0 blocking findings within budget
OPA gate: PASS
```

The 6 HIGH come from Trivy (`AWS-0086/0087/0091/0092/0093/0132`). The 9 UNKNOWN
are Checkov's: the open-source Checkov CLI reports no severity, which is exactly
the Chapter 4 gotcha. The loop treats an unranked finding as blocking, so all 15
block, and it treats a scanner that crashed or printed no JSON as a failed scan,
never a clean one. The Conftest gate fails the same way if the policy engine
cannot run. `tests/test_iacgen.py` covers each of these paths.

## The degradation paradox (Listing 14-3)

```
UNCAPPED: pass 1 = 15 -> pass 2 = 28 -> pass 3 = 43  (rising, never converges)
CAPPED  : pass 1 = 15, budget exhausted, build FAILS on the non-clean module
```

These are the real blocking counts (Trivy HIGH plus Checkov's unranked findings) on the recorded degrade fixtures. They are
a **deterministic illustration** of Shukla et al.'s qualitative finding that
unbounded LLM self-refinement can ADD vulnerabilities. They are **not** a
reproduction of the paper's **+37.6%** figure, which is a live-LLM result and
cannot be reproduced in CI without a model. Never present the fixture counts as
the paper's measured magnitude.

## SARIF: native vs hand-rolled

Both scanners emit valid SARIF 2.1.0 natively, so in production you do not
hand-roll it:
- `checkov --output sarif --output-file-path <dir>` writes `results_sarif.sarif`.
- `trivy config --format sarif` writes SARIF to stdout.

`iacgen/sarif.py` shows both: `native_checkov_sarif` / `native_trivy_sarif` run
the binaries, and `to_sarif` hand-rolls a single MERGED SARIF 2.1.0 log from the
normalized cross-scanner findings (useful when you want one report instead of N
native files). `validate_sarif` asserts the structural invariants GitHub code
scanning needs, offline.

Every listing here is version-pinned and CI-tested (job `ch14-iacgen`).
