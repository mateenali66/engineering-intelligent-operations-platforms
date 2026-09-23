# Chapter 5: Introduction to AIOps

Conceptual chapter. Two small, runnable artifacts make the "decide" and
"recover" stages of the AIOps loop concrete.

| Listing | File | What it is |
|---|---|---|
| Listing 5-1 | `decision/decide.py` | Confidence-gated decision step. Automates an action only when the diagnosis is confident, its risk tier is on an explicit allowlist, and its live-state preconditions hold; everything else, including an unknown tier, escalates to a human. |
| Listing 5-2 | `remediation/restart-deployment.yaml` | An Argo Workflows template for a bounded, safe-tier remediation: restart one named deployment, verify the rollout, and page on-call from the exit handler if it fails. |
| (support) | `remediation/rbac.yaml` | The least-privilege service account and roles the runbook runs as. |

## Run it

```bash
# Decision gate: runs an in-file assertion suite, including the
# fail-closed cases (unknown tiers, failed or missing preconditions).
python decision/decide.py
# -> ENQUEUE: restart-deployment
#    PAGE: low-confidence diagnosis | ...
#    PAGE: tier not approved to auto-run | ...   (six times)
#    PAGE: preconditions not met | ...           (twice)
#    ok

# Remediation runbook: install the RBAC and the template (needs a cluster
# with Argo Workflows; tested on kind with Argo Workflows v4.1.4).
kubectl apply -f remediation/rbac.yaml
kubectl apply -f remediation/restart-deployment.yaml
```

`decide.py` is standard-library only and self-contained. It also ships
`score_to_percentile`, the ten-line calibration helper from Section 5.5: it
ranks a raw Chapter 6 detector score against a known-good validation window so
`score_min` becomes a false-positive budget rather than a magic number. The
assertion suite exercises it. The Argo `WorkflowTemplate` targets
`argoproj.io/v1alpha1` and is parameterized by deployment and namespace; it is
invoked by the decision step, not run by hand.
