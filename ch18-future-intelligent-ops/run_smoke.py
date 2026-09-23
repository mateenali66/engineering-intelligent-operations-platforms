"""Smoke test for the agent control plane: prove the assist-and-approve boundary
holds, with no LLM and no cluster.

Asserts the four properties that make this L2 and not L4:
  1. The agent proposes (two PRs) and the cluster is UNCHANGED until a human acts.
  2. Only a human can approve; the agent cannot approve its own remediation.
  3. Reconcile refuses anything a human has not approved.
  4. The red button halts the agent: engaged, it opens no PR and changes nothing.
"""

from __future__ import annotations

from agentops.agent import RemediationAgent
from agentops.control_plane import ApprovalDenied, approve, reconcile
from agentops.guardian import Guardian, GuardianPaused
from agentops.models import Actor, Anomaly, Deploy, PRStatus

# r41 ran healthy on the current schema, so it is the rollback target.
HISTORY = (
    Deploy(40, healthy=True, schema_version=3),
    Deploy(41, healthy=True, schema_version=3),
    Deploy(42, healthy=False, schema_version=3),
)


def main() -> None:
    guardian = Guardian()
    agent = RemediationAgent(guardian)
    cluster = {"checkout": {"revision": 42}}
    anomaly = Anomaly("checkout", "p95 tripled after the 14:02 rollout.", 42,
                      schema_version=3, history=HISTORY)

    # 1. Propose only: two PRs, cluster unchanged.
    prs = agent.handle(anomaly)
    assert len(prs) == 2 and {p.kind for p in prs} == {"diagnosis", "remediation"}
    assert all(p.status == PRStatus.AWAITING_APPROVAL for p in prs)
    assert cluster == {"checkout": {"revision": 42}}
    print("1. agent proposed 2 PRs; cluster unchanged: PASS")

    remediation = next(p for p in prs if p.kind == "remediation")

    # 2. The agent cannot approve its own work.
    try:
        approve(remediation, agent.identity)
        raise AssertionError("agent must not be able to approve")
    except ApprovalDenied:
        pass
    print("2. agent self-approval refused (separation of duties): PASS")

    # 3. Reconcile refuses an unapproved PR.
    try:
        reconcile(remediation, cluster)
        raise AssertionError("reconcile must refuse an unapproved PR")
    except PermissionError:
        pass

    # ...then a human approves and reconcile applies the rollback.
    approve(remediation, Actor("oncall-sre", is_human=True))
    cluster = reconcile(remediation, cluster)
    assert cluster == {"checkout": {"revision": 41}}
    print("3. only human-approved change reconciles (r42 -> r41): PASS")

    # 4. The red button halts the agent entirely.
    guardian.engage(Actor("oncall-sre", is_human=True))
    halted = False
    try:
        agent.handle(anomaly)
    except GuardianPaused:
        halted = True
    assert halted and cluster == {"checkout": {"revision": 41}}
    print("4. red button halts the agent; nothing changes: PASS")

    print("smoke: ok")


if __name__ == "__main__":
    main()
