# Payments gateway incident mitigations

## Payments gateway elevated declines: general triage
This is the general mitigation playbook for the payments gateway. When the
payments gateway shows elevated declines, drain the affected gateway instances
and let the load balancer reroute to healthy capacity. This generic mitigation
applies to most payments gateway decline incidents before a specific cause is
known. Use it when you have no incident number to look up.

## Mitigating incident INC-4821 on the payments gateway
On-call confirmed the upstream processor was healthy. The root cause was a bad
recent gateway deploy, and the resolution was to roll back the deploy. Decline
rate returned to baseline after the rollback completed.

## Mitigating incident INC-4822 on the payments gateway
On-call confirmed the upstream processor was healthy. The root cause was an
expired processor API credential, and the resolution was to rotate the
credential and restart the gateway workers. Decline rate returned to baseline
once the new credential propagated.

## Mitigating incident INC-4823 on the payments gateway
On-call confirmed the upstream processor was healthy. The root cause was an
undersized gateway connection pool, and the resolution was to raise the pool
limit. Decline rate returned to baseline after the pool change rolled out.
