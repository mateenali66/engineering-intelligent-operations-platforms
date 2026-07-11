# Chapter 18: The Future of Intelligent Operations

The book's final running example: an agent control plane added to AIOSP, the
platform from Chapter 17 now self-operating under human-defined guardrails at L2
autonomy. A remediation agent detects an anomaly, opens a diagnosis pull request
and a remediation pull request, and stops. It cannot actuate. A human approval gate
and the GitOps reconcile from Chapter 17 are the only path to the cluster, and a
guardian (the red button) can pause every agent at once.

The point of the lab is the assist-and-approve CONTROL boundary, not a model, so it
is pure standard library and runs with no LLM, no cluster, and no GPU.

## Listing-to-file map

| Listing | File | Description |
|---|---|---|
| 18-1 | `agentops/agent.py` (`handle`) | The L2 remediation agent: guardian check, then open a diagnosis PR and a remediation PR; it has no method that actuates |

The printed listing is an exact substring of the file.

## Layout

```
agentops/
  models.py        AutonomyLevel (L0-L4), Anomaly, PullRequest, Actor
  guardian.py      the red button: a fleet-wide kill switch
  agent.py         the L2 remediation agent (Listing 18-1)
  control_plane.py the human approval gate + the GitOps reconcile
labs/
  lab1_agent_remediation.py   the assist-and-approve flow, end to end
tests/             the L2 boundary, separation of duties, the guardian
run_smoke.py       asserts the four control properties
```

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.

python labs/lab1_agent_remediation.py   # the narrated flow
python run_smoke.py                      # the four assertions
python -m pytest tests/ -q
```

Expected: the agent opens two PRs and the cluster stays at revision 42; only after a
human approves does it reconcile to revision 41; with the red button engaged the
agent raises `GuardianPaused` and nothing changes.

## The honest CI-vs-live split

RUN in CI (`ch18-future` job, one Python 3.12 venv, no LLM/cluster/GPU): the smoke
test and the full test suite, which assert that the agent opens two pull requests
and actuates nothing, that it cannot approve its own remediation (separation of
duties), that only a human-approved change reconciles, that the red button halts the
agent, and that the agent is structurally pinned at L2 (it exposes no actuate or
reconcile method).

Validation-only (not run): a real LLM agent in place of the deterministic
diagnosis, and the OpenTelemetry agent semantic conventions (still Development, so
the attribute names will change before they stabilize). Same honesty split as the
rest of Part IV and the Chapter 17 capstone.

## Pinned versions

Python 3.12; pytest 8.4.2; ruff 0.9.10. The agent control plane itself is pure
standard library (dataclasses, enum), so there is nothing else to pin.
