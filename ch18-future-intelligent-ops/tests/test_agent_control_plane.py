"""Tests for the agent control plane: the L2 boundary is structural, the guardian
halts the fleet, and separation of duties holds."""

from __future__ import annotations

import pytest

from agentops.agent import RemediationAgent
from agentops.control_plane import ApprovalDenied, approve, reconcile
from agentops.guardian import Guardian, GuardianOverrideDenied, GuardianPaused
from agentops.models import Actor, Anomaly, AutonomyLevel, Deploy, PRStatus

# r41 ran healthy on the current schema, so it is the rollback target.
HISTORY = (
    Deploy(40, healthy=True, schema_version=3),
    Deploy(41, healthy=True, schema_version=3),
    Deploy(42, healthy=False, schema_version=3),
)


def _setup():
    guardian = Guardian()
    agent = RemediationAgent(guardian)
    anomaly = Anomaly("checkout", "p95 tripled after the 14:02 rollout.", 42,
                      schema_version=3, history=HISTORY)
    return guardian, agent, anomaly


def test_agent_is_pinned_at_l2():
    _, agent, _ = _setup()
    assert agent.level == AutonomyLevel.L2_PARTIAL
    # The agent exposes no actuation: the only public action is handle().
    assert not hasattr(agent, "reconcile")
    assert not hasattr(agent, "actuate")


def test_agent_proposes_two_prs_and_actuates_nothing():
    _, agent, anomaly = _setup()
    prs = agent.handle(anomaly)
    assert [p.kind for p in prs] == ["diagnosis", "remediation"]
    assert all(p.status == PRStatus.AWAITING_APPROVAL for p in prs)
    assert all(p.author.is_human is False for p in prs)


def test_agent_cannot_approve_its_own_remediation():
    _, agent, anomaly = _setup()
    remediation = next(p for p in agent.handle(anomaly) if p.kind == "remediation")
    with pytest.raises(ApprovalDenied):
        approve(remediation, agent.identity)


def test_reconcile_refuses_unapproved_change():
    _, agent, anomaly = _setup()
    remediation = next(p for p in agent.handle(anomaly) if p.kind == "remediation")
    with pytest.raises(PermissionError):
        reconcile(remediation, {"checkout": {"revision": 42}})


def test_human_approval_then_reconcile_applies_the_rollback():
    _, agent, anomaly = _setup()
    remediation = next(p for p in agent.handle(anomaly) if p.kind == "remediation")
    approve(remediation, Actor("oncall-sre", is_human=True))
    cluster = reconcile(remediation, {"checkout": {"revision": 42}})
    assert cluster == {"checkout": {"revision": 41}}
    assert remediation.status == PRStatus.MERGED


def test_red_button_halts_the_agent_before_it_opens_a_pr():
    guardian, agent, anomaly = _setup()
    guardian.engage(Actor("oncall-sre", is_human=True))
    with pytest.raises(GuardianPaused):
        agent.handle(anomaly)


def test_red_button_engage_refuses_a_non_human_actor():
    guardian, agent, _ = _setup()
    # An agent cannot press the red button: engaging it is a human oversight action.
    with pytest.raises(GuardianOverrideDenied):
        guardian.engage(agent.identity)
    assert guardian.paused is False


def test_red_button_releases_only_by_a_human_disengage():
    guardian, agent, anomaly = _setup()
    human = Actor("oncall-sre", is_human=True)
    guardian.engage(human)
    assert guardian.paused is True
    # An agent cannot release the red button on itself; only a human disengage does.
    with pytest.raises(GuardianOverrideDenied):
        guardian.disengage(agent.identity)
    assert guardian.paused is True
    guardian.disengage(human)
    assert guardian.paused is False
    # Once released, the agent acts again.
    prs = agent.handle(anomaly)
    assert len(prs) == 2


def test_rollback_skips_an_unhealthy_prior_revision():
    # "Suspect minus one" is not assumed good: r41 was unhealthy, so r40.
    history = (Deploy(40, True, 3), Deploy(41, False, 3), Deploy(42, False, 3))
    anomaly = Anomaly("checkout", "p95 tripled.", 42, schema_version=3,
                      history=history)
    prs = RemediationAgent(Guardian()).handle(anomaly)
    remediation = next(p for p in prs if p.kind == "remediation")
    assert remediation.change == {"service": "checkout", "revision": 40}


def test_no_rollback_across_a_schema_change():
    # Every earlier revision expects an older schema, so rolling back would run
    # old code on new data. The agent proposes no rollback and a human decides.
    history = (Deploy(40, True, 2), Deploy(41, True, 2), Deploy(42, False, 3))
    anomaly = Anomaly("checkout", "p95 tripled.", 42, schema_version=3,
                      history=history)
    prs = RemediationAgent(Guardian()).handle(anomaly)
    assert [p.kind for p in prs] == ["diagnosis"]
    assert "no rollback is proposed" in prs[0].body

