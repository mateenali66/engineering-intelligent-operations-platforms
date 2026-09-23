"""Listing 14-2 (RUNS IN CI): bounded generate-scan-repair loop + OPA gate + SARIF.

Wraps Lab 1 in a bounded loop:
  generate() -> scan -> if blocking and budget remains: repair() -> re-scan
The repair() step is a STUBBED LLM that returns the NEXT recorded revision
(rev2_hardened). The scanners (Checkov, Trivy) and the OPA/Conftest gate run for
REAL. After convergence the loop runs the Chapter 4 s3_encryption.rego policy
against the recorded plan JSON, then emits a merged SARIF 2.1.0 report for GitHub
code scanning.

Expected trace: pass 1 has blocking -> repair -> pass 2 has 0 -> gate PASS.

Run:
    python labs/lab2_loop_gate_sarif.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from iacgen.loop import format_trace, run_loop
from iacgen.sarif import validate_sarif


def main() -> None:
    prompt = "a secure S3 bucket Terraform module for telemetry exports"
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "module"
        sarif_path = Path(tmp) / "iacgen.sarif"

        outcome = run_loop(prompt, workdir, max_passes=3,
                           emit_sarif_to=sarif_path)

        print("bounded generate-scan-repair loop (budget = 3 passes):")
        print(format_trace(outcome))

        # The SARIF emitted for the final (clean) module must be well-formed.
        validate_sarif(outcome.sarif)
        n_results = sum(len(r["results"]) for r in outcome.sarif["runs"])
        print(f"\nSARIF 2.1.0: valid, {n_results} result(s) "
              f"(version={outcome.sarif['version']}), written to {sarif_path.name}")

        assert outcome.converged, "loop must converge within the budget"
        assert outcome.gate is not None and outcome.gate.passed, \
            "OPA gate must pass on the hardened module"


if __name__ == "__main__":
    main()
