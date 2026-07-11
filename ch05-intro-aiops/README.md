# Chapter 5: Introduction to AIOps

Conceptual chapter. Two small, runnable artifacts make the "decide" and
"recover" stages of the AIOps loop concrete.

| Listing | File | What it is |
|---|---|---|
| Listing 5-1 | `decision/decide.py` | Confidence-gated decision step. Automates an action only when the diagnosis is confident and the action is reversible; everything else escalates to a human. |
| Listing 5-2 | `remediation/restart-deployment.yaml` | An Argo Workflows template for a bounded, safe-tier remediation (restart one named deployment). |

## Run it

```bash
# Decision gate: runs an in-file assertion suite over the four cases.
python decision/decide.py
# -> ENQUEUE: restart-deployment
#    PAGE: low-confidence diagnosis | ...
#    PAGE: action requires human approval | ...
#    ok

# Remediation runbook: validate the manifest (requires a cluster with Argo).
kubectl apply --dry-run=client -f remediation/restart-deployment.yaml
```

`decide.py` is standard-library only and self-contained. It also ships
`score_to_percentile`, the ten-line calibration helper from Section 5.5: it
ranks a raw Chapter 6 detector score against a known-good validation window so
`score_min` becomes a false-positive budget rather than a magic number. The
assertion suite exercises it. The Argo `WorkflowTemplate` targets
`argoproj.io/v1alpha1` and is parameterized by deployment and namespace; it is
invoked by the decision step, not run by hand.
