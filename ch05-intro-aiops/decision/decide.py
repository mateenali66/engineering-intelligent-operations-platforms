"""Confidence-gated decision step for an AIOps remediation loop.

The model detects and diagnoses. This module decides whether an action runs
automatically or escalates to a human. The ``decide`` function shown in
Chapter 5 (Listing 5-1) is the core; the dataclasses and stubs below make it
runnable and testable in isolation. In a real system, ``page_human`` and
``enqueue_bounded_action`` are backed by your on-call and workflow tooling.

Provenance of the two gate inputs (Chapter 5, Section 5.5): the raw material
for ``anomaly_score`` is the detector Chapter 6 builds, which emits a raw,
model-specific score, not a probability. ``score_to_percentile`` below turns
that raw score into a calibrated percentile against a known-good validation
window; ``diagnosis.confidence`` is earned the same way (diagnostic agreement
or historical confirmation rate), never taken as a raw score or softmax value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Diagnosis:
    cause: str
    confidence: float  # 0.0 to 1.0; calibrated, not a raw model score (see module docstring)


@dataclass
class Action:
    name: str
    risk_tier: str  # "safe" or "consequential"


def page_human(*, reason: str, **context: object) -> None:
    """Escalate to a human with pre-assembled context (stubbed here)."""
    print(f"PAGE: {reason} | {context}")


def enqueue_bounded_action(action: Action) -> Action:
    """Hand a safe-tier action to the remediation workflow (stubbed here)."""
    print(f"ENQUEUE: {action.name}")
    return action


def decide(anomaly_score, diagnosis, action, *, score_min, conf_min):
    """Return an action to enqueue, or None to escalate to a human."""
    if anomaly_score < score_min:
        return None  # not anomalous enough to act on

    if diagnosis.confidence < conf_min:
        page_human(reason="low-confidence diagnosis", diagnosis=diagnosis)
        return None

    if action.risk_tier == "consequential":
        page_human(reason="action requires human approval", action=action)
        return None

    # High anomaly score, high-confidence diagnosis, reversible action.
    return enqueue_bounded_action(action)


def score_to_percentile(score, calibration_window):
    """Calibrate a raw detector score against a known-good validation window.

    Chapter 6's detector emits a raw, model-specific anomaly score, not a
    probability, so it cannot be compared to a fixed threshold directly. Ranking
    a live score against a window of scores from known-good operation returns its
    percentile in [0, 1], which is what ``decide`` gates on. That gives
    ``score_min`` an operational meaning as a false-positive budget:
    ``score_min=0.995`` acts only above the 99.5th percentile of normal.
    """
    window = sorted(calibration_window)
    at_or_below = sum(1 for s in window if s <= score)
    return at_or_below / len(window)


if __name__ == "__main__":
    safe = Action(name="restart-deployment", risk_tier="safe")
    risky = Action(name="failover-database", risk_tier="consequential")
    confident = Diagnosis(cause="sidecar-memory-leak", confidence=0.92)
    unsure = Diagnosis(cause="unknown", confidence=0.40)

    # Only the confident diagnosis on a safe, reversible action auto-runs.
    assert decide(0.95, confident, safe, score_min=0.8, conf_min=0.8) is safe
    assert decide(0.10, confident, safe, score_min=0.8, conf_min=0.8) is None
    assert decide(0.95, unsure, safe, score_min=0.8, conf_min=0.8) is None
    assert decide(0.95, confident, risky, score_min=0.8, conf_min=0.8) is None

    # Calibration: a raw detector score becomes a percentile against a
    # known-good window, which is the number score_min actually gates on.
    window = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert score_to_percentile(0.05, window) == 0.0  # below the window
    assert score_to_percentile(0.6, window) == 1.0  # above the window
    assert score_to_percentile(0.3, window) == 0.6  # ranks 3 of 5 at or below
    # A score below the validation window ranks low, so the gate declines to act
    # (returns None, no enqueue), leaving the printed output above unchanged.
    assert decide(score_to_percentile(0.05, window), confident, safe,
                  score_min=0.8, conf_min=0.8) is None
    print("ok")
