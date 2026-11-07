#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CHART="helm/charts/spring-boot-microservice"
COMMON_VALUES="helm/environments/dev/common.yaml"
KUBECONFORM_SCHEMA=".kubeconform/ExternalSecret-external-secrets.io-v1.json"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

# Vérification des prérequis
for command in helm kubeconform; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERREUR : commande requise introuvable : $command" >&2
        exit 1
    fi
done

# Vérification des fichiers communs
if [[ ! -f "$COMMON_VALUES" ]]; then
    echo "ERREUR : fichier de valeurs commun introuvable : $COMMON_VALUES" >&2
    exit 1
fi

if [[ ! -f "$KUBECONFORM_SCHEMA" ]]; then
    echo "ERREUR : schéma ExternalSecret introuvable : $KUBECONFORM_SCHEMA" >&2
    exit 1
fi

validate_service() {
    if (( $# != 5 )); then
        echo "ERREUR : validate_service attend 5 arguments, reçu : $#" >&2
        return 1
    fi

    local service="$1"
    local release="$2"
    local namespace="$3"
    local values="$4"
    local external_secret="$5"
    local rendered="${TEMP_DIR}/${service}-rendered.yaml"

    echo
    echo "=========================================="
    echo "Validation : ${service}"
    echo "=========================================="

    if [[ ! -f "$values" ]]; then
        echo "ERREUR : fichier de valeurs introuvable : $values" >&2
        return 1
    fi

    echo "===== Helm lint ====="

    helm lint "$CHART" \
        --strict \
        -f "$COMMON_VALUES" \
        -f "$values"

    echo "===== Helm template ====="

    helm template "$release" "$CHART" \
        --namespace "$namespace" \
        -f "$COMMON_VALUES" \
        -f "$values" \
        > "$rendered"

    echo "===== Kubeconform ====="

    local kubeconform_args=(
        -strict
        -summary
        -verbose
        -schema-location default
    )

    if [[ "$external_secret" == "true" ]]; then
        kubeconform_args+=(
            -schema-location "$KUBECONFORM_SCHEMA"
        )
    fi

    kubeconform "${kubeconform_args[@]}" "$rendered"

    echo "Validation réussie : ${service}"
}

# AI Public Benefits
validate_service "document-service" "document-service" "public-benefits" "helm/environments/dev/ai-public-benefits/document-service.yaml" "true"

# Developer Content Creator
validate_service "repository-service" "developer-content-creator-repository-service-dev" "developer-content-creator" "helm/environments/dev/developer-content-creator/repository-service.yaml" "false"

echo
echo "===== Git diff check ====="

git diff --check

echo
echo "=========================================="
echo "Validation Helm terminée avec succès."
echo "Microservices validés : 2"
echo "=========================================="