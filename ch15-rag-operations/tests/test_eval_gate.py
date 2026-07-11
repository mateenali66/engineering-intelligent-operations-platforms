"""The deterministic eval gate passes a grounded answer and fails a hallucination."""

from __future__ import annotations

from labs import lab4_eval_gate as gate


def test_good_release_passes():
    assert gate.gate(gate.GOOD_ANSWER)


def test_regressed_release_fails():
    assert not gate.gate(gate.HALLUCINATED_ANSWER)
