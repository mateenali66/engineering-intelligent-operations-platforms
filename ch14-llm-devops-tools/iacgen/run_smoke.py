"""End-to-end smoke test for the iacgen running example (Chapter 14).

Runs the bounded generate-scan-repair loop end to end with the REAL scanners
(Checkov 3.3.1 + Trivy 0.71.1, in parallel) and the REAL OPA/Conftest gate
(Conftest 0.68.2) over the recorded fixtures, and asserts the outcomes the
chapter teaches:

  1. the loop STARTS with blocking findings (the recorded insecure module),
  2. it CONVERGES to 0 blocking within the retry budget,
  3. the OPA gate PASSES on the converged module,
  4. the emitted SARIF 2.1.0 is well-formed,
  5. (degradation illustration) an UNCAPPED loop's blocking count RISES while a
     capped loop stops at the rail.

The generate()/repair() steps are stubbed recorded fixtures (no LLM API key, no
network for generation); the scanners and the gate run for real. Prints
"smoke: ok" when every assertion holds.

Run:
    PYTHONPATH=. python run_smoke.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from iacgen.loop import run_loop
from iacgen.sarif import validate_sarif
from labs import lab3_degradation


def main() -> None:
    prompt = "a secure S3 bucket Terraform module for telemetry exports"

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "module"
        sarif_path = Path(tmp) / "iacgen.sarif"

        outcome = run_loop(prompt, workdir, max_passes=3,
                           emit_sarif_to=sarif_path)

        # 1. Starts with blocking findings.
        first = outcome.passes[0]
        print(f"loop pass 1: {first.blocking_count} blocking "
              f"({first.total_count} total)")
        assert first.blocking_count > 0, \
            "the recorded insecure module must start with blocking findings"

        # 2. Converges to 0 within the budget.
        last = outcome.passes[-1]
        print(f"loop final pass {last.index}: {last.blocking_count} blocking")
        assert outcome.converged, "the loop must converge within the budget"
        assert last.blocking_count == 0, "the converged module must have 0 blocking"
        assert len(outcome.passes) <= 3, "must converge within the 3-pass budget"

        # 3. OPA gate passes on the converged module.
        assert outcome.gate is not None, "the gate must run after convergence"
        print(f"OPA gate: {'PASS' if outcome.gate.passed else 'FAIL'}")
        assert outcome.gate.passed, "the OPA gate must pass on the hardened module"

        # 4. SARIF is well-formed.
        validate_sarif(outcome.sarif)
        n_results = sum(len(r["results"]) for r in outcome.sarif["runs"])
        assert sarif_path.exists(), "the SARIF file must be written"
        print(f"SARIF 2.1.0: valid, {n_results} result(s), written to disk")

        # 5. Degradation illustration: uncapped rises, capped stops.
        uncapped = lab3_degradation.run_uncapped(Path(tmp))
        counts = [b for _, b in uncapped]
        capped = lab3_degradation.run_capped(Path(tmp), max_passes=1)
        print(f"degradation (illustrative): uncapped "
              f"{' -> '.join(str(c) for c in counts)}; capped stops at "
              f"{len(capped)} pass")
        assert counts == sorted(counts) and counts[-1] > counts[0], \
            "uncapped illustration must show a rising blocking count"
        assert len(capped) == 1, "capped loop must stop after one pass"

    print("smoke: ok")


if __name__ == "__main__":
    main()
