#!/usr/bin/env bash
# Stand up AIOSP on a local kind cluster: Argo CD plus KServe, then let Argo CD
# reconcile the three workloads from Git. The anomaly-detector serves the book's
# own detector, trained here from Chapter 11's train.py, so run this from the
# companion repository clone, where ../ch11-model-serving exists. This needs a real cluster (Docker +
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
cd "$(dirname "$0")"

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

if grep -rq "${PLACEHOLDER}" platform/apps/ platform/argocd/; then
  sed -i.bak "s#${PLACEHOLDER}#${AIOSP_REPO_URL}#g" platform/apps/*.yaml platform/argocd/*.yaml
  rm -f platform/apps/*.yaml.bak platform/argocd/*.yaml.bak
  echo "Rewrote the placeholder repoURL in platform/apps/ and platform/argocd/ to ${AIOSP_REPO_URL}."
  echo "Argo CD pulls the Applications from that remote, not from this working"
  echo "copy: commit and push the rewrite, then rerun ./setup.sh."
  exit 1
fi

if ! git ls-remote "${AIOSP_REPO_URL}" HEAD >/dev/null 2>&1; then
  echo "ERROR: cannot reach ${AIOSP_REPO_URL}." >&2
  echo "Push this chapter's tree there first; Argo CD will fetch it from there." >&2
  exit 1
fi

# 1. The folder the served detector's model file will live in. The kind node
#    mounts it in the next step; step 6 trains the model into it.
mkdir -p model-store/anomaly-detector

# 2. A local cluster whose node mounts the model folder at /models, where the
#    PersistentVolume in platform/storage/ finds it. Writable, because the
#    training Job in step 6 writes the model file through it.
cat > model-store/kind-config.yaml <<KIND
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: $PWD/model-store
        containerPath: /models
KIND
kind create cluster --name aiosp --config model-store/kind-config.yaml

# 3. Argo CD: the delivery substrate.
kubectl create namespace argocd
# Server-side apply: since Argo CD 3.3 the ApplicationSet CRD is too large for
# client-side apply's last-applied annotation, and a plain apply fails on it.
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/install.yaml
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# 4. KServe: the serving substrate (predictive AND generative).
curl -sL -o /tmp/kserve-install.sh \
  https://github.com/kserve/kserve/releases/download/v0.19.0/kserve-standard-mode-full-install-with-manifests.sh
bash /tmp/kserve-install.sh

# 5. The OpenTelemetry Collector: the observability substrate.
kubectl create namespace observability
kubectl apply -f platform/observability/otel-collector.yaml

# 6. The book's detector. For sklearn over the V2 protocol, KServe picks its
#    kserve-mlserver runtime, so read that runtime's image from the cluster and
#    train with it, as a Job on the node that already caches the image. The
#    model file is then written by the same scikit-learn version that loads it.
TRAIN_SRC="$PWD/../ch11-model-serving/serving"
[[ -f "${TRAIN_SRC}/train.py" ]] || { echo "ERROR: ${TRAIN_SRC}/train.py not found." >&2; exit 1; }
kubectl create namespace aiops --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap detector-train-src -n aiops \
  --from-file=train.py="${TRAIN_SRC}/train.py" --dry-run=client -o yaml | kubectl apply -f -
RUNTIME_IMAGE=$(kubectl get clusterservingruntime kserve-mlserver \
  -o jsonpath='{.spec.containers[0].image}')
kubectl delete job train-detector -n aiops --ignore-not-found
sed "s#RUNTIME_IMAGE#${RUNTIME_IMAGE}#" platform/storage/train-detector.yaml | kubectl apply -f -
kubectl wait --for=condition=complete --timeout=900s job/train-detector -n aiops

# 7. The detector's model volume, bound in the namespace the detector runs in.
kubectl apply -f platform/storage/detector-model.yaml

# 8. Hand the whole platform to Argo CD with one app-of-apps. The project comes
#    first, because Argo CD will not sync an Application whose project is
#    missing. From here, Git is the source of truth: Argo CD reconciles the
#    AIOps, MLOps, and LLMOps workloads onto the cluster.
kubectl apply -f platform/argocd/project.yaml
kubectl apply -f platform/apps/root.yaml

echo "AIOSP is reconciling. Watch it with: kubectl get applications -n argocd"
echo "Expect aiosp-root and the three workload Applications to reach Synced."
echo "Then: kubectl get inferenceservice -A. The anomaly-detector (the book's"
echo "detector) and the churn-model (KServe's public example model) reach"
echo "READY True; the Incident Copilot needs a GPU node and stays unready without one."
