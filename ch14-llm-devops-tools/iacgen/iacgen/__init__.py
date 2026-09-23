"""iacgen: an LLM-powered IaC generator with a bounded scan-repair loop.

The running example for Chapter 14. A CLI that takes a natural-language request,
generates Terraform, scans it with multiple security scanners in parallel, runs
a bounded generate-scan-repair loop, fails closed on blocking findings
(HIGH, CRITICAL, or unranked) and scanner errors, and emits SARIF.

Honest CI-vs-LLM split: the generate() and repair() steps are RECORDED FIXTURES
(see fixtures/), not live model calls, so the lab runs headless in CI with no
LLM API key. The scanners (Checkov 3.3.1, Trivy 0.71.1, Conftest 0.68.2) run for
REAL against those fixtures, and the loop / gate / SARIF logic is real code.
"""

__version__ = "0.1.0"
