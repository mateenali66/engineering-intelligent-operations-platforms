#!/usr/bin/env bash
# Stand up AIOSP on a local kind cluster: Argo CD plus KServe, then let Argo CD
# reconcile the three workloads from Git. This needs a real cluster (Docker +
# kind) and, for the Incident Copilot, a GPU node, so it is NOT run in CI; the
# manifests it applies are yaml-linted and convergence-checked in CI instead.
#
# ONE-TIME PREREQUISITE: Argo CD pulls the platform/ tree from a Git remote, so
# the tree must live in a repository you own. Push this chapter's directory to
# your own remote, export AIOSP_REPO_URL to point at it, and run this script:
# the first run rewrites the placeholder repoURL in platform/apps/ and stops so
# you can commit and push the rewrite; the second run brings the cluster up.
#
# Versions pinned to the mid-2026 lines verified for the chapter:
#   kind v0.32.0, Argo CD 3.4.4, KServe 0.19.0, Backstage Helm chart 2.8.2.
set -euo pipefail

PLACEHOLDER="https://github.com/YOUR-USERNAME/aiosp-platform.git"

# 0. The Git remote Argo CD reconciles from: yours, and it must be reachable.
if [[ -z "${AIOSP_REPO_URL:-}" ]]; then
  echo "ERROR: AIOSP_REPO_URL is not set." >&2
  echo "Argo CD reconciles the platform FROM GIT, so this tree must live in a" >&2
  echo "repository you own. Push this directory to your own remote, then:" >&2
  echo "  export AIOSP_REPO_URL=https://github.com/YOUR-USERNAME/aiosp-platform.git" >&2
  echo "  ./setup.sh" >&2
  exit 1
fi

if grep -rq "${PLACEHOLDER}" platform/apps/; then
  sed -i.bak "s#${PLACEHOLDER}#${AIOSP_REPO_URL}#g" platform/apps/*.yaml
  rm -f platform/apps/*.yaml.bak
  echo "Rewrote the placeholder repoURL in platform/apps/ to ${AIOSP_REPO_URL}."
  echo "Argo CD pulls the Applications from that remote, not from this working"
  echo "copy: commit and push the rewrite, then rerun ./setup.sh."
  exit 1
fi

if ! git ls-remote "${AIOSP_REPO_URL}" HEAD >/dev/null 2>&1; then
  echo "ERROR: cannot reach ${AIOSP_REPO_URL}." >&2
  echo "Push this chapter's tree there first; Argo CD will fetch it from there." >&2
  exit 1
fi

# 1. A local cluster.
kind create cluster --name aiosp

# 2. Argo CD: the delivery substrate.
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/install.yaml
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# 3. KServe: the serving substrate (predictive AND generative).
curl -sL -o /tmp/kserve-install.sh \
  https://github.com/kserve/kserve/releases/download/v0.19.0/kserve-standard-mode-full-install-with-manifests.sh
bash /tmp/kserve-install.sh

# 4. The OpenTelemetry Collector: the observability substrate.
kubectl create namespace observability
kubectl apply -f platform/observability/otel-collector.yaml

# 5. Hand the whole platform to Argo CD with one app-of-apps. From here, Git is
#    the source of truth: Argo CD reconciles the AIOps, MLOps, and LLMOps
#    workloads onto the cluster.
kubectl apply -f platform/apps/root.yaml

echo "AIOSP is reconciling. Watch it with: kubectl get applications -n argocd"
echo "Expect aiosp-root and the three workload Applications to reach Synced."
echo "Then: kubectl get inferenceservice -A. The two sklearn workloads reach"
echo "READY True (they pull KServe's public example model); the Incident"
echo "Copilot needs a GPU node and stays unready without one."
