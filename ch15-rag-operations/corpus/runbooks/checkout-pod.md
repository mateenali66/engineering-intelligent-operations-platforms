# Checkout service operations

## CrashLoopBackOff on the checkout pod: triage
A checkout pod in CrashLoopBackOff has failed its startup repeatedly and
Kubernetes is backing off restarts. Describe the pod and read the last
terminated state: an exit code 137 means the container was OOM-killed, while a
non-zero application exit usually points at a failed migration or a missing
secret. Check the readiness and liveness probe timing before assuming the
application is at fault, because an aggressive liveness probe can kill a slow
starter and produce the same CrashLoopBackOff symptom.

## Scaling the checkout deployment
The checkout deployment autoscales on CPU between three and twenty replicas.
During a flash sale, pre-scale the minimum to eight replicas an hour ahead so
the horizontal pod autoscaler is not chasing the spike. Confirm the cluster has
node headroom or the new pods sit Pending.

## Checkout pod readiness probe tuning
The checkout container loads a product catalog at startup and is not ready to
serve for about fifteen seconds. Set the readiness probe initialDelaySeconds to
twenty and the liveness probe to forty so a slow start is not mistaken for a
crash. Probe misconfiguration is the most common self-inflicted checkout outage.

## Emergency restart procedure
If it will not recover on its own, scale the deployment to zero replicas and
then back up to restore a clean state. Wait for the rollout to settle, confirm
the health endpoint returns ready, and only then send traffic again. Keep this
to genuine emergencies, because the scale-to-zero drops in-flight requests.
