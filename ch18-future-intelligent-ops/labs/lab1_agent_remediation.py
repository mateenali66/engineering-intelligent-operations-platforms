"""Lab 1: the assist-and-approve remediation flow, end to end.

Runs the L2 agent against an anomaly, shows it open two PRs and stop, shows the
cluster unchanged until a human approves, then shows the red button halting the
agent entirely. The implementations are in the agentops package (Listing 18-1 is
the agent's handle method).

Run:
    python lab1_agent_remediation.py
"""

from __future__ import annotations

from agentops.agent import RemediationAgent
from agentops.control_plane import approve, reconcile
from agentops.guardian import Guardian, GuardianPaused
from agentops.models import Actor, Anomaly


def main() -> None:
    guardian = Guardian()
    agent = RemediationAgent(guardian)
    cluster = {"checkout": {"revision": 42}}
    anomaly = Anomaly(
        service="checkout",
        summary="p95 latency tripled right after the 14:02 rollout.",
        suspect_revision=42,
    )

    print(f"agent autonomy level: {agent.level.name}")
    print(f"cluster before: {cluster}")

    # 1. The agent proposes; it opens two PRs and stops.
    prs = agent.handle(anomaly)
    for pr in prs:
        print(f"  opened {pr.kind} PR: '{pr.title}' [{pr.status.name}]")
    print(f"cluster after agent ran: {cluster}  (unchanged: the agent cannot actuate)")

    # 2. A human approves the remediation PR; only then does GitOps reconcile it.
    remediation = next(pr for pr in prs if pr.kind == "remediation")
    sre = Actor(name="oncall-sre", is_human=True)
    approve(remediation, sre)
    cluster = reconcile(remediation, cluster)
    print(f"after human approval + reconcile: {cluster}  (rolled back to r41)")

    # 3. The red button: a human engages the guardian and the agent refuses to act.
    guardian.engage(sre)
    try:
        agent.handle(anomaly)
    except GuardianPaused as exc:
        print(f"red button engaged -> agent halted: {exc}")


if __name__ == "__main__":
    main()
