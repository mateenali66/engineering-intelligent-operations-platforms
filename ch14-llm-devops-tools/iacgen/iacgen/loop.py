"""The bounded generate-scan-repair loop, the OPA gate, and SARIF emission.

This is Listing 14-2, the heart of iacgen. The loop:

  1. generate()  -> recorded insecure module (the stubbed LLM)
  2. scan it in PARALLEL with Checkov + Trivy (real scanners)
  3. if there are HIGH/CRITICAL findings AND the retry budget is not exhausted,
     repair() -> the next recorded, more-hardened revision, then re-scan
  4. repeat up to `max_passes`
  5. once clean, run the OPA/Conftest gate against the plan JSON
  6. emit a merged SARIF 2.1.0 report for GitHub code scanning

The CAP is the whole point. Chapter 14 (and Shukla et al.) show that unbounded
LLM refinement can ADD vulnerabilities, so the budget is a hard safety rail: the
loop either converges within the budget or fails the build. Listing 14-3
(lab3_degradation.py) demonstrates what happens without the cap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import generate as gen
from . import sarif as sarif_mod
from .gate import GateResult, run_gate
from .scanners import ScanResult, scan_parallel


@dataclass
class PassRecord:
    """One pass through the loop: what was scanned and what came back."""

    index: int                       # 1-based pass number
    blocking_count: int              # HIGH/CRITICAL findings this pass
    total_count: int                 # all findings this pass
    counts_by_severity: dict[str, int]
    repaired: bool                   # did we call repair() after this pass?


@dataclass
class LoopOutcome:
    converged: bool                  # reached 0 blocking findings within budget
    passes: list[PassRecord] = field(default_factory=list)
    final_module: Path | None = None
    final_scan: ScanResult | None = None
    gate: GateResult | None = None
    sarif: dict | None = None


def run_loop(prompt: str, workdir: str | Path, *,
             max_passes: int = 3,
             sequence: list[str] | None = None,
             emit_sarif_to: str | Path | None = None) -> LoopOutcome:
    """Run the bounded generate-scan-repair loop and the OPA gate.

    `max_passes` is the retry budget: at most this many scan passes. The loop
    stops early the moment a scan has zero HIGH/CRITICAL findings.
    """
    workdir = Path(workdir)
    module = gen.generate(prompt, workdir, sequence=sequence)

    outcome = LoopOutcome(converged=False)
    repairs_done = 0

    for i in range(1, max_passes + 1):
        scan = scan_parallel(module)
        record = PassRecord(
            index=i,
            blocking_count=len(scan.blocking),
            total_count=len(scan.findings),
            counts_by_severity=scan.counts_by_severity(),
            repaired=False,
        )

        if not scan.has_blocking:
            # Converged: no HIGH/CRITICAL findings remain.
            outcome.converged = True
            outcome.passes.append(record)
            outcome.final_module = module
            outcome.final_scan = scan
            break

        # Still blocking. Repair only if budget remains for another pass.
        if i < max_passes:
            repairs_done += 1
            module = gen.repair(workdir, scan.blocking, repairs_done,
                                sequence=sequence)
            record.repaired = True

        outcome.passes.append(record)
        outcome.final_module = module
        outcome.final_scan = scan

    # OPA/Conftest gate against the recorded plan JSON for the final module.
    if outcome.converged and outcome.final_module is not None:
        plan_json = outcome.final_module / "plan.json"
        outcome.gate = run_gate(plan_json)

    # Merged SARIF for the final scan (what GitHub code scanning would ingest).
    if outcome.final_scan is not None:
        doc = sarif_mod.to_sarif(outcome.final_scan.findings, tool_name="iacgen")
        sarif_mod.validate_sarif(doc)
        outcome.sarif = doc
        if emit_sarif_to is not None:
            sarif_mod.write_sarif(doc, emit_sarif_to)

    return outcome


def format_trace(outcome: LoopOutcome) -> str:
    """Human-readable loop trace, the lines the chapter pastes."""
    lines: list[str] = []
    for p in outcome.passes:
        sev = ", ".join(f"{k}={v}" for k, v in sorted(p.counts_by_severity.items()))
        tail = " -> repair()" if p.repaired else ""
        lines.append(
            f"pass {p.index}: {p.blocking_count} HIGH/CRITICAL "
            f"({p.total_count} total; {sev or 'none'}){tail}"
        )
    if outcome.converged:
        lines.append("converged: 0 HIGH/CRITICAL within budget")
    else:
        lines.append("NOT converged: budget exhausted with HIGH/CRITICAL remaining")
    if outcome.gate is not None:
        lines.append(f"OPA gate: {'PASS' if outcome.gate.passed else 'FAIL'}"
                     + ("" if outcome.gate.passed
                        else f" ({'; '.join(outcome.gate.failures)})"))
    return "\n".join(lines)
