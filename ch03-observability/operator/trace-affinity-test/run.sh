#!/usr/bin/env bash
# Trace-affinity test for Listing 3-1. Creates a three-node kind cluster, installs
# cert-manager and the OpenTelemetry Operator, deploys the repo's agent resource
# and a two-replica gateway test double, sends traces whose spans are split
# across the two agents, and fails if any trace reaches more than one gateway
# replica. Needs docker, kind, kubectl, and python3. Deletes the cluster on exit.
set -euo pipefail
cd "$(dirname "$0")"
CLUSTER=ch03-trace-affinity
CERT_MANAGER=v1.21.2
OPERATOR=v0.135.0
trap 'kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true' EXIT

kind create cluster --name "$CLUSTER" --config kind.yaml --wait 180s
kubectl config use-context "kind-$CLUSTER" >/dev/null
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/$CERT_MANAGER/cert-manager.yaml" >/dev/null
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=300s
kubectl apply --server-side -f "https://github.com/open-telemetry/opentelemetry-operator/releases/download/$OPERATOR/opentelemetry-operator.yaml" >/dev/null
kubectl -n opentelemetry-operator-system rollout status deploy/opentelemetry-operator-controller-manager --timeout=300s

# The agent and its RBAC are the repo's resources, unchanged. The gateway is a test double
# with a debug exporter, so each replica logs the traces it received.
kubectl create namespace observability
# The operator webhook can refuse connections for a few seconds after its
# deployment reports ready, so retry the first apply.
for _ in $(seq 1 30); do
  kubectl apply -f gateway-test-cr.yaml && break
  sleep 5
done
python3 - <<'PY' | kubectl apply -f -
import sys, yaml
docs = [d for d in yaml.safe_load_all(open("../otel-collector-cr.yaml"))
        if d["metadata"]["name"] != "gateway"]
yaml.safe_dump_all(docs, sys.stdout)
PY
for kind_name in agent gateway; do
  until kubectl -n observability get pods -l "app.kubernetes.io/name=$kind_name-collector" -o name | grep -q .; do sleep 2; done
done
kubectl -n observability wait pods --all --for=condition=Ready --timeout=300s

AGENTS=$(kubectl -n observability get pods -l app.kubernetes.io/name=agent-collector \
  -o jsonpath='{range .items[*]}{.status.podIP},{end}' | sed 's/,$//')
kubectl -n observability create configmap sender --from-file=send_split_traces.py

send() {  # send <trace-id prefix>: 40 traces, each split across the agents
  kubectl -n observability delete pod sender --ignore-not-found >/dev/null
  kubectl -n observability run sender --image=python:3.12-alpine --restart=Never \
    --overrides="{\"spec\":{\"containers\":[{\"name\":\"sender\",\"image\":\"python:3.12-alpine\",
    \"command\":[\"python\",\"/s/send_split_traces.py\",\"$AGENTS\",\"$1\",\"40\"],
    \"volumeMounts\":[{\"name\":\"s\",\"mountPath\":\"/s\"}]}],
    \"volumes\":[{\"name\":\"s\",\"configMap\":{\"name\":\"sender\"}}]}}" >/dev/null
  kubectl -n observability wait pod/sender --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null
  kubectl -n observability logs sender
  sleep 15  # agent batch timeout (5s) plus gateway flush
}

echo "phase 1: two gateway replicas"
send ab
python3 check_affinity.py ab 2

# Phase 2: change the replica set, then send as soon as the new replica is
# Ready. Every agent must switch to the same new set, or traces split.
echo "phase 2: scale the gateway to three replicas"
kubectl -n observability patch opentelemetrycollector gateway --type=merge -p '{"spec":{"replicas":3}}'
until [ "$(kubectl -n observability get pods -l app.kubernetes.io/name=gateway-collector \
  --field-selector=status.phase=Running -o name | wc -l)" -eq 3 ]; do sleep 2; done
kubectl -n observability wait pods -l app.kubernetes.io/name=gateway-collector --for=condition=Ready --timeout=300s
send cd
python3 check_affinity.py cd 2
