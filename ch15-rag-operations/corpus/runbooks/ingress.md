# Ingress controller operations

## 502 Bad Gateway from the ingress controller
A 502 Bad Gateway returned by the ingress means the controller reached an
upstream pod but got no valid response. The usual causes are an upstream that
closed the connection, a readiness probe that marks a dead pod as ready, or a
proxy-read-timeout shorter than the backend response time. Check the controller
access log for the upstream address, curl that pod directly, and raise the
proxy timeout annotation if the backend is simply slow rather than broken.

## Rotating TLS certificates on the ingress
TLS certificates on the ingress are issued by cert-manager and renew thirty days
before expiry. To rotate manually, delete the Certificate secret and let
cert-manager reissue, then confirm the new not-after date with openssl s_client.
A stale certificate triggers browser warnings and breaks API clients that pin
the chain.

## Rate limiting at the ingress
Apply rate limiting at the ingress with the limit-rps annotation to protect
backends during a traffic surge. Set it per route, not globally, so a noisy
public endpoint cannot starve authenticated traffic. Return 429 with a Retry
After header so well-behaved clients back off.
