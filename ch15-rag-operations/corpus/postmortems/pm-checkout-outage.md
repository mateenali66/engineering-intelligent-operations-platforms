# Postmortem: checkout outage on host prod-checkout-7f9c

## Summary
Checkout was unavailable for nineteen minutes during the evening peak. A single
node, prod-checkout-7f9c, held a disproportionate share of checkout pods and a
kernel-level network fault on that node black-holed traffic without failing the
node's health check, so the scheduler did not reschedule the pods.

## Timeline
The first alert fired when checkout success rate dropped. On-call drained
prod-checkout-7f9c after correlating the failing pods to that one host. Once the
pods rescheduled onto healthy nodes, success rate recovered. The faulty node was
cordoned and sent for hardware inspection.

## Root cause
The node prod-checkout-7f9c experienced a NIC firmware fault that dropped
packets silently. The node-level health check tested only kubelet liveness, not
data-path connectivity, so Kubernetes considered the node Ready while it was
black-holing checkout traffic. Pod anti-affinity was not set, so the scheduler
had packed several checkout replicas onto that one node.

## Action items
Add a data-path connectivity probe to node health. Set pod anti-affinity on the
checkout deployment so replicas spread across nodes. Reduce the maximum pods per
node for latency-sensitive services so no single host failure removes a large
fraction of capacity.
