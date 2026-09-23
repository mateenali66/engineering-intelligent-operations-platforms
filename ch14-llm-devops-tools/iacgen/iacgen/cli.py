"""iacgen CLI: natural-language request -> generated IaC -> scan-repair loop -> SARIF.

    python -m iacgen "a secure S3 bucket Terraform module" \
        --max-passes 3 --sarif out.sarif --workdir ./.iacgen-work

The generate/repair steps are stubbed recorded fixtures (no LLM key); the
scanners and the gate run for real. Exit code is 0 when the loop converges to no
blocking findings within the budget AND the OPA gate passes; non-zero
otherwise, so the command is a usable CI gate.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .gate import plan_summary
from .loop import format_trace, run_loop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="iacgen", description=__doc__)
    parser.add_argument("prompt", help="natural-language IaC request")
    parser.add_argument("--max-passes", type=int, default=3,
                        help="retry budget (max scan passes); default 3")
    parser.add_argument("--workdir", default=None,
                        help="where to materialize the module; default a temp dir")
    parser.add_argument("--sarif", default=None,
                        help="write the merged SARIF 2.1.0 report to this path")
    args = parser.parse_args(argv)

    tmp_ctx = None
    if args.workdir:
        workdir = Path(args.workdir)
    else:
        tmp_ctx = tempfile.TemporaryDirectory()
        workdir = Path(tmp_ctx.name) / "module"

    try:
        outcome = run_loop(args.prompt, workdir,
                           max_passes=args.max_passes,
                           emit_sarif_to=args.sarif)
        print(format_trace(outcome))
        if outcome.final_module is not None:
            plan = outcome.final_module / "plan.json"
            if plan.exists():
                # Show the diff beside the findings: a clean scan of the wrong
                # change is still the wrong change.
                print("planned changes (review these, not just the scan):")
                for line in plan_summary(plan):
                    print(f"  {line}")
        if args.sarif:
            n = sum(len(r["results"]) for r in outcome.sarif["runs"])
            print(f"SARIF: {n} result(s) written to {args.sarif}")

        gate_ok = outcome.gate is not None and outcome.gate.passed
        if outcome.converged and gate_ok:
            print("RESULT: PASS (converged within budget, OPA gate passed)")
            return 0
        print("RESULT: FAIL (blocking findings remain, a scanner failed, or OPA gate failed)")
        return 1
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


if __name__ == "__main__":
    sys.exit(main())
