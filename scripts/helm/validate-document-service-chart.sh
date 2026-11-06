#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CHART="helm/charts/spring-boot-microservice"
VALUES="helm/environments/dev/document-service.yaml"
RENDERED="/tmp/document-service-rendered.yaml"

echo "===== Helm lint ====="
helm lint "$CHART" --strict -f "$VALUES"

echo "===== Helm template ====="
helm template document-service "$CHART" \
  --namespace ai-public-benefits \
  -f "$VALUES" \
  > "$RENDERED"

echo "===== Kubeconform ====="
kubeconform \
  -strict \
  -summary \
  -verbose \
  -schema-location default \
  -schema-location '.kubeconform/ExternalSecret-external-secrets.io-v1.json' \
  "$RENDERED"

echo "===== Git diff check ====="
git diff --check

echo "Validation terminée avec succès."