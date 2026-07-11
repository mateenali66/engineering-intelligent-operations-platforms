"""Listing 18-1 (RUNS IN CI): a remediation agent pinned at L2 autonomy.

The agent monitors, investigates, and proposes a fix, then opens two pull requests,
one for the diagnosis and one for the remediation, and stops. It has no method that
actuates: the only path from a proposal to the cluster runs through a human approval
in the control plane. That is the assist-and-approve pattern made structural. Before
it does anything, it checks the guardian (the red button), so a single human action
can halt every agent on the platform.

This is CI-runnable with no LLM and no cluster: the diagnosis is a deterministic
rule over the anomaly, and the "cluster" is a dict the control plane mutates only
after a human approves. Swapping in a real model changes how the diagnosis is
written, not who is allowed to actuate.
"""

from __future__ import annotations

from agentops.guardian import Guardian
from agentops.models import Anomaly, AutonomyLevel, Actor, PullRequest


class RemediationAgent:
    """An L2 agent: it can propose an actuation, but cannot perform one."""

    level = AutonomyLevel.L2_PARTIAL

    def __init__(self, guardian: Guardian) -> None:
        self.guardian = guardian
        self.identity = Actor(name="remediation-agent", is_human=False)

    def handle(self, anomaly: Anomaly) -> list[PullRequest]:
        """Investigate the anomaly and open a diagnosis PR and a remediation PR.

        Returns the two PRs, both AWAITING_APPROVAL. Raises GuardianPaused if the
        red button is engaged, so no PR is opened at all while the platform is held.
        """
        self.guardian.assert_clear()

        # Monitor and investigate (L1 capability): a deterministic diagnosis stands
        # in for the model's reasoning. The roll-forward revision is the suspect one.
        rollback_to = anomaly.suspect_revision - 1
        diagnosis = PullRequest(
            kind="diagnosis",
            title=f"Diagnosis: {anomaly.service} regression after r{anomaly.suspect_revision}",
            body=(
                f"{anomaly.summary} The regression begins at revision "
                f"{anomaly.suspect_revision}; the prior good revision is "
                f"{rollback_to}."
            ),
            author=self.identity,
        )

        # Propose an actuation (L2 capability) as a GitOps change. The agent opens
        # the PR; it does not and cannot merge or apply it.
        remediation = PullRequest(
            kind="remediation",
            title=f"Roll back {anomaly.service} to r{rollback_to}",
            body=(
                f"Revert {anomaly.service} to revision {rollback_to} to clear the "
                f"regression. Awaiting human approval before Argo CD reconciles it."
            ),
            author=self.identity,
            change={"service": anomaly.service, "revision": rollback_to},
        )
        return [diagnosis, remediation]
