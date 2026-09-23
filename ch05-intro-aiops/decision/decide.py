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

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Diagnosis:
    cause: str
    confidence: float  # 0.0 to 1.0; calibrated, not a raw model score (see module docstring)


@dataclass(frozen=True)
class Precondition:
    """A live-state check that must hold for the action to be safe right now,
    for example "other replicas are Ready" or "the node pool has headroom"."""

    name: str
    check: Callable[[], bool]


@dataclass
class Action:
    name: str
    risk_tier: str  # only tiers in AUTO_TIERS may run unattended
    preconditions: tuple[Precondition, ...] = field(default_factory=tuple)


def page_human(*, reason: str, **context: object) -> None:
    """Escalate to a human with pre-assembled context (stubbed here)."""
    print(f"PAGE: {reason} | {context}")


def enqueue_bounded_action(action: Action) -> Action:
    """Hand a safe-tier action to the remediation workflow (stubbed here)."""
    print(f"ENQUEUE: {action.name}")
    return action


# Confidence-gated decision step. The model detects and diagnoses;
# this function decides whether to act automatically or page a human.

AUTO_TIERS = frozenset({"safe"})  # tiers approved to run unattended


def decide(anomaly_score, diagnosis, action, *, score_min, conf_min):
    """Return an action to enqueue, or None to escalate to a human."""
    if anomaly_score < score_min:
        return None  # not anomalous enough to act on

    if diagnosis.confidence < conf_min:
        page_human(reason="low-confidence diagnosis", diagnosis=diagnosis)
        return None

    # Allowlist, not denylist: an unknown or misspelled tier escalates.
    if action.risk_tier not in AUTO_TIERS:
        page_human(reason="tier not approved to auto-run", action=action)
        return None

    # Preconditions are checked against live state at decision time.
    # An action that declares none fails closed.
    unmet = [p.name for p in action.preconditions if not p.check()]
    if not action.preconditions or unmet:
        page_human(reason="preconditions not met", unmet=unmet,
                   action=action)
        return None

    # Clear anomaly, confident diagnosis, approved tier, preconditions hold.
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
    replicas_ready = Precondition("other replicas Ready", lambda: True)
    no_headroom = Precondition("node pool has headroom", lambda: False)

    safe = Action("restart-deployment", "safe", (replicas_ready,))
    risky = Action("failover-database", "consequential")
    confident = Diagnosis(cause="sidecar-memory-leak", confidence=0.92)
    unsure = Diagnosis(cause="unknown", confidence=0.40)
    gate = {"score_min": 0.8, "conf_min": 0.8}

    # Only a confident diagnosis on an approved tier whose preconditions
    # hold auto-runs.
    assert decide(0.95, confident, safe, **gate) is safe
    assert decide(0.10, confident, safe, **gate) is None
    assert decide(0.95, unsure, safe, **gate) is None
    assert decide(0.95, confident, risky, **gate) is None

    # Fail closed on anything the allowlist does not name: an unknown
    # tier, a misspelling, a different case, or an empty value.
    for tier in ("low", "Safe", "safe ", "", "reversible"):
        odd = Action("restart-deployment", tier, (replicas_ready,))
        assert decide(0.95, confident, odd, **gate) is None, tier

    # An approved tier still escalates when a precondition fails, or when
    # the action declares no preconditions at all.
    blocked = Action("scale-up", "safe", (replicas_ready, no_headroom))
    bare = Action("restart-deployment", "safe")
    assert decide(0.95, confident, blocked, **gate) is None
    assert decide(0.95, confident, bare, **gate) is None

    # Calibration: a raw detector score becomes a percentile against a
    # known-good window, which is the number score_min actually gates on.
    window = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert score_to_percentile(0.05, window) == 0.0  # below the window
    assert score_to_percentile(0.6, window) == 1.0  # above the window
    assert score_to_percentile(0.3, window) == 0.6  # ranks 3 of 5 at or below
    # A score below the validation window ranks low, so the gate declines
    # to act (returns None, no enqueue).
    assert decide(score_to_percentile(0.05, window), confident, safe,
                  **gate) is None
    print("ok")
