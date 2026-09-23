"""Listing 14-3 (RUNS IN CI): the refinement-degradation paradox (illustrative).

HONESTY FIRST. Shukla et al. measured that unbounded LLM self-refinement can
ADD vulnerabilities, reporting a +37.6% increase in their study. That empirical
number comes from a LIVE LLM and cannot be reproduced in CI with no API key, so
this lab does NOT reproduce it and never prints it as a measured result.

Instead this is a DETERMINISTIC ILLUSTRATION of the same failure mode. We built
a fixed sequence of recorded "revisions" (fixtures/rev1_insecure ->
degrade_a_policy_wildcard -> degrade_b_back_to_acl) where each "repair", chasing
one finding, introduces more exposed surface. The REAL scanners (Checkov, Trivy)
then measure a HIGH-severity count that RISES across uncapped iterations. With
the cap in place, the loop stops at the budget instead.

What you see below are the scanners' real counts on the fixtures, framed as an
illustration of the paper's qualitative finding, not its magnitude.

Run:
    python labs/lab3_degradation.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from iacgen import generate as gen
from iacgen.scanners import scan_parallel

SEQUENCE = gen.DEGRADATION_SEQUENCE


def _scan_revision(fixture: str, tmp: Path) -> int:
    """Materialize one recorded revision and return its real blocking count."""
    module = gen._materialize(fixture, tmp / fixture)
    result = scan_parallel(module)
    return len(result.blocking)


def run_uncapped(tmp: Path) -> list[tuple[str, int]]:
    """Walk the degradation sequence with NO cap; record blocking count each pass."""
    trace: list[tuple[str, int]] = []
    for i, fixture in enumerate(SEQUENCE, start=1):
        blocking = _scan_revision(fixture, tmp)
        trace.append((fixture, blocking))
    return trace


def run_capped(tmp: Path, max_passes: int = 1) -> list[tuple[str, int]]:
    """Same sequence but stop after `max_passes` passes (the safety rail)."""
    trace: list[tuple[str, int]] = []
    for i, fixture in enumerate(SEQUENCE, start=1):
        if i > max_passes:
            break
        blocking = _scan_revision(fixture, tmp)
        trace.append((fixture, blocking))
    return trace


def main() -> None:
    print("Listing 14-3: refinement-degradation paradox (DETERMINISTIC "
          "ILLUSTRATION).")
    print("These are the real scanner blocking counts on recorded "
          "fixtures.")
    print("They illustrate Shukla et al.'s qualitative finding that unbounded")
    print("refinement can ADD vulnerabilities. They are NOT a reproduction of")
    print("the paper's +37.6% figure, which needs a live LLM.\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        print("UNCAPPED loop (no budget): chasing findings adds surface")
        uncapped = run_uncapped(tmp)
        for i, (fixture, blocking) in enumerate(uncapped, start=1):
            print(f"  pass {i}: {blocking} blocking  [{fixture}]")
        counts = [b for _, b in uncapped]
        print(f"  -> blocking count went {' -> '.join(str(c) for c in counts)} "
              f"(rising, never converges)\n")

        print("CAPPED loop (budget = 1 pass): stops at the rail")
        capped = run_capped(tmp, max_passes=1)
        for i, (fixture, blocking) in enumerate(capped, start=1):
            print(f"  pass {i}: {blocking} blocking  [{fixture}]")
        print("  -> budget exhausted; build FAILS on the non-clean module "
              "instead of looping into a worse one\n")

        # Self-checking assertions: the illustration must actually rise uncapped.
        assert counts == sorted(counts), \
            "uncapped counts must be non-decreasing for the illustration to hold"
        assert counts[-1] > counts[0], \
            "uncapped refinement must end with MORE blocking findings than it started"
        assert len(capped) == 1, "the capped loop must stop after one pass"

    print("illustration: ok (uncapped rises, capped stops)")


if __name__ == "__main__":
    main()
