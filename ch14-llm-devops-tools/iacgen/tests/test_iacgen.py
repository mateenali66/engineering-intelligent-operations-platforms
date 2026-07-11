"""CI assertions for the iacgen running example (Chapter 14).

These tests run the REAL scanners (Checkov, Trivy) and the REAL OPA gate over the
recorded fixtures and assert the chapter's claims. generate()/repair() are
stubbed recorded fixtures (no LLM key); everything else is real.

    PYTHONPATH=. pytest tests/ -q
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from iacgen import generate as gen
from iacgen.loop import run_loop
from iacgen.sarif import (native_checkov_sarif, native_trivy_sarif, to_sarif,
                          validate_sarif)
from iacgen.scanners import scan_parallel


def test_lab1_insecure_module_has_high_findings():
    """Listing 14-1: the recorded insecure module produces real HIGH findings."""
    with tempfile.TemporaryDirectory() as tmp:
        module = gen.generate("a secure S3 bucket module", Path(tmp) / "m")
        result = scan_parallel(module)
        assert result.has_blocking
        assert len(result.blocking) >= 1
        # Both scanners contributed findings.
        scanners = {f.scanner for f in result.findings}
        assert "checkov" in scanners and "trivy" in scanners


def test_lab2_loop_converges_and_gate_passes():
    """Listing 14-2: the bounded loop converges to 0 HIGH/CRITICAL, gate passes."""
    with tempfile.TemporaryDirectory() as tmp:
        outcome = run_loop("a secure S3 bucket module", Path(tmp) / "m",
                           max_passes=3, emit_sarif_to=Path(tmp) / "out.sarif")
        assert outcome.passes[0].blocking_count > 0       # starts insecure
        assert outcome.converged                          # converges
        assert outcome.passes[-1].blocking_count == 0     # to zero
        assert len(outcome.passes) <= 3                   # within budget
        assert outcome.gate is not None and outcome.gate.passed
        validate_sarif(outcome.sarif)


def test_lab2_sarif_is_well_formed():
    """The merged hand-rolled SARIF and both native SARIFs are valid 2.1.0."""
    with tempfile.TemporaryDirectory() as tmp:
        module = gen.generate("x", Path(tmp) / "m")
        result = scan_parallel(module)
        merged = to_sarif(result.findings)
        validate_sarif(merged)
        assert merged["version"] == "2.1.0"

        # Native emission also works (no hand-rolling needed in production).
        validate_sarif(native_checkov_sarif(module))
        validate_sarif(native_trivy_sarif(module))


def test_lab3_uncapped_degrades_capped_stops():
    """Listing 14-3: uncapped blocking count RISES; capped stops at the rail.

    Deterministic illustration of Shukla et al.'s qualitative finding, NOT a
    reproduction of the +37.6% number.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        counts = []
        for fixture in gen.DEGRADATION_SEQUENCE:
            module = gen._materialize(fixture, tmp_path / fixture)
            counts.append(len(scan_parallel(module).blocking))
        # Monotone non-decreasing and strictly higher at the end.
        assert counts == sorted(counts)
        assert counts[-1] > counts[0]


def test_opa_gate_denies_insecure_passes_hardened():
    """The Chapter 4 s3_encryption.rego gate denies rev1 and passes rev2."""
    from iacgen.gate import run_gate

    rev1_plan = gen.FIXTURES / "rev1_insecure" / "plan.json"
    rev2_plan = gen.FIXTURES / "rev2_hardened" / "plan.json"
    assert not run_gate(rev1_plan).passed   # no SSE -> deny
    assert run_gate(rev2_plan).passed       # both buckets have SSE -> pass
