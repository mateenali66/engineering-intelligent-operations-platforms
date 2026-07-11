"""The human gate and the GitOps actuation.

This is the half of the control plane an agent cannot reach. approve() enforces
separation of duties: only a human actor can approve a pull request, so the agent
that opened it can never bless its own work. reconcile() is the GitOps apply, the
point where Argo CD would sync the merged change to the cluster; it refuses to run
on anything a human has not approved. Together they are the structural reason the
running example sits at L2 and cannot drift to L4: the path to the cluster passes
through a human every time.
"""

from __future__ import annotations

from agentops.models import Actor, PRStatus, PullRequest


class ApprovalDenied(Exception):
    """Raised when a non-human actor tries to approve a pull request."""


def approve(pr: PullRequest, actor: Actor) -> PullRequest:
    """Human approval gate. Only a human may approve; an agent actor is refused,
    which is what keeps the agent from approving its own remediation."""
    if not actor.is_human:
        raise ApprovalDenied(
            f"{actor.name} is not human; only a human can approve a remediation"
        )
    pr.status = PRStatus.APPROVED
    pr.approver = actor
    return pr


def reconcile(pr: PullRequest, cluster: dict) -> dict:
    """GitOps actuation: apply an APPROVED remediation to the cluster state.

    Refuses anything not approved, so an unapproved (or agent-opened-only) PR can
    never change the cluster. Returns the new cluster state.
    """
    if pr.status != PRStatus.APPROVED:
        raise PermissionError(
            "reconcile refused: the pull request is not approved by a human"
        )
    cluster = dict(cluster)
    cluster[pr.change["service"]] = {"revision": pr.change["revision"]}
    pr.status = PRStatus.MERGED
    return cluster
