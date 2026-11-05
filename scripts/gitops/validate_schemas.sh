#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

KUBECONFORM_VERSION="v0.8.0"

if ! command -v kubeconform >/dev/null 2>&1; then
    echo "[ERROR] kubeconform n'est pas installé."
    exit 1
fi

INSTALLED_VERSION="$(kubeconform -v)"

if [[ "$INSTALLED_VERSION" != "$KUBECONFORM_VERSION" ]]; then
    echo "[ERROR] Version kubeconform attendue : $KUBECONFORM_VERSION"
    echo "[ERROR] Version installée : $INSTALLED_VERSION"
    exit 1
fi

echo "===== Validation des Applications ArgoCD ====="

kubeconform \
    -strict \
    -summary \
    -schema-location schemas/argocd/json/Application_v1alpha1.json \
    gitops/applications/ \
    gitops/bootstrap/

echo "===== Validation des AppProjects ArgoCD ====="

kubeconform \
    -strict \
    -summary \
    -schema-location schemas/argocd/json/AppProject_v1alpha1.json \
    gitops/projects/

echo "===== Validation des schémas terminée ====="
