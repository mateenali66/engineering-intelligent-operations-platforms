"""Data model for the agent control plane.

The autonomy levels follow Google SRE's L0 to L4 ladder. The running example pins
its remediation agent at L2 (Partial Autonomy): the agent monitors, investigates,
and proposes, but a human must approve before anything actuates. The types here
make that boundary structural rather than a matter of good intentions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class AutonomyLevel(IntEnum):
    """Google SRE's autonomy ladder. The label is what each level automates;
    approval and actuation are the rungs that matter for who is in control."""

    L0_MANUAL = 0          # humans do everything
    L1_ASSISTED = 1        # agent monitors and investigates; human approves and actuates
    L2_PARTIAL = 2         # agent can actuate, but only after explicit human approval
    L3_HIGH = 3            # agent approves and actuates bounded actions; humans on the loop
    L4_FULL = 4            # end-to-end autonomous resolution


class PRStatus(IntEnum):
    AWAITING_APPROVAL = 0
    APPROVED = 1
    MERGED = 2
    REJECTED = 3


@dataclass
class Actor:
    """Who is taking an action. The is_human flag is the separation-of-duties
    boundary: the control plane refuses to let an agent approve its own work."""

    name: str
    is_human: bool


@dataclass
class Anomaly:
    """A signal handed to the agent, the kind the Chapter 6 detector produces."""

    service: str
    summary: str
    suspect_revision: int


@dataclass
class PullRequest:
    """A proposed change. The agent opens it; it never merges itself. This is the
    two-PR pattern's unit: a diagnosis PR and a remediation PR, both reviewed."""

    kind: str               # "diagnosis" or "remediation"
    title: str
    body: str
    author: Actor
    status: PRStatus = PRStatus.AWAITING_APPROVAL
    approver: Actor | None = None
    # For a remediation PR, the GitOps change it would apply once merged.
    change: dict = field(default_factory=dict)
