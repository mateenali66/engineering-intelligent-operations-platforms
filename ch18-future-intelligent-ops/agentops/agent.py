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

        Returns the PRs, all AWAITING_APPROVAL. Raises GuardianPaused if the red
        button is engaged, so no PR is opened at all while the platform is held.
        With no safe rollback target it opens the diagnosis PR only.
        """
        self.guardian.assert_clear()

        # Monitor and investigate (L1 capability): a deterministic diagnosis stands
        # in for the model's reasoning. The target is not "suspect minus one": it
        # is the newest earlier revision the deploy log recorded as healthy on the
        # schema the service runs today, so the rollback is known good and
        # compatible with current data.
        rollback_to = rollback_target(anomaly)
        found = (f"the last healthy revision on the current schema is {rollback_to}."
                 if rollback_to is not None else
                 "no earlier revision is both healthy and on the current schema, "
                 "so no rollback is proposed; a human decides the fix.")
        diagnosis = PullRequest(
            kind="diagnosis",
            title=f"Diagnosis: {anomaly.service} regression after r{anomaly.suspect_revision}",
            body=(
                f"{anomaly.summary} The regression begins at revision "
                f"{anomaly.suspect_revision}; {found}"
            ),
            author=self.identity,
        )
        if rollback_to is None:
            return [diagnosis]

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


def rollback_target(anomaly: Anomaly) -> int | None:
    """The newest revision before the suspect that ran healthy on today's schema."""
    candidates = [d.revision for d in anomaly.history
                  if d.revision < anomaly.suspect_revision
                  and d.healthy and d.schema_version == anomaly.schema_version]
    return max(candidates, default=None)
