#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_DIR = ROOT / "gitops" / "bootstrap"
APPLICATIONS_DIR = ROOT / "gitops" / "applications"

EXPECTED_ROOTS = {
    "ai-public-benefits-root.yaml": {
        "name": "ai-public-benefits-root",
        "path": "gitops/applications/ai-public-benefits/dev",
    },
    "developer-content-creator-root.yaml": {
        "name": "developer-content-creator-root",
        "path": "gitops/applications/developer-content-creator/dev",
    },
}

EXPECTED_REPO = (
    "https://github.com/dso2530/platform-infrastructure.git"
)
EXPECTED_REVISION = "main"
EXPECTED_PROJECT = "platform-infrastructure"
EXPECTED_SERVER = "https://kubernetes.default.svc"
EXPECTED_NAMESPACE = "argocd"

errors = []
validated = 0


def error(path, message):
    errors.append(f"{path}: {message}")


def load_yaml(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        error(path.relative_to(ROOT), f"lecture impossible : {exc}")
        return None


def validate_root(path, expected):
    global validated

    relative_path = path.relative_to(ROOT)
    application = load_yaml(path)

    if not isinstance(application, dict):
        error(relative_path, "le document doit être un objet YAML")
        return

    if application.get("apiVersion") != "argoproj.io/v1alpha1":
        error(relative_path, "apiVersion ArgoCD invalide")

    if application.get("kind") != "Application":
        error(relative_path, "kind doit être Application")

    metadata = application.get("metadata")

    if not isinstance(metadata, dict):
        error(relative_path, "metadata doit être un objet")
        return

    if metadata.get("name") != expected["name"]:
        error(
            relative_path,
            f"metadata.name doit être {expected['name']}",
        )

    if metadata.get("namespace") != EXPECTED_NAMESPACE:
        error(
            relative_path,
            f"metadata.namespace doit être {EXPECTED_NAMESPACE}",
        )

    spec = application.get("spec")

    if not isinstance(spec, dict):
        error(relative_path, "spec doit être un objet")
        return

    if spec.get("project") != EXPECTED_PROJECT:
        error(
            relative_path,
            f"spec.project doit être {EXPECTED_PROJECT}",
        )

    # Une racine doit utiliser une source unique.
    source = spec.get("source")

    if not isinstance(source, dict):
        error(relative_path, "spec.source doit être un objet")
        return

    if spec.get("sources") is not None:
        error(
            relative_path,
            "une Application racine ne doit pas utiliser spec.sources",
        )

    if source.get("repoURL") != EXPECTED_REPO:
        error(relative_path, "repoURL de la racine invalide")

    if source.get("targetRevision") != EXPECTED_REVISION:
        error(
            relative_path,
            f"targetRevision doit être {EXPECTED_REVISION}",
        )

    source_path = source.get("path")

    if source_path != expected["path"]:
        error(
            relative_path,
            f"source.path doit être {expected['path']}",
        )

    if "prepared" in str(source_path).split("/"):
        error(
            relative_path,
            "une racine ne doit jamais référencer prepared/",
        )

    directory = source.get("directory")

    if not isinstance(directory, dict):
        error(relative_path, "source.directory doit être défini")
    elif directory.get("recurse") is not True:
        error(
            relative_path,
            "source.directory.recurse doit être true",
        )

    # Vérification de la destination locale ArgoCD.
    destination = spec.get("destination")

    if not isinstance(destination, dict):
        error(relative_path, "spec.destination doit être un objet")
    else:
        if destination.get("server") != EXPECTED_SERVER:
            error(
                relative_path,
                "destination.server doit être le cluster local",
            )

        if destination.get("name") is not None:
            error(
                relative_path,
                "destination.name ne doit pas être défini pour la racine",
            )

        if destination.get("namespace") != EXPECTED_NAMESPACE:
            error(
                relative_path,
                f"destination.namespace doit être {EXPECTED_NAMESPACE}",
            )

    # Les racines doivent rester en synchronisation manuelle.
    sync_policy = spec.get("syncPolicy", {})

    if isinstance(sync_policy, dict):
        if "automated" in sync_policy:
            error(
                relative_path,
                "la synchronisation automatique est interdite sur une racine",
            )
    elif sync_policy is not None:
        error(relative_path, "spec.syncPolicy doit être un objet")

    # Vérification du répertoire géré par la racine.
    target_dir = ROOT / expected["path"]

    if not target_dir.is_dir():
        error(
            relative_path,
            f"répertoire cible inexistant : {expected['path']}",
        )
        return

    child_files = sorted(target_dir.glob("*.yaml"))

    if not child_files:
        error(
            relative_path,
            f"aucune Application enfant dans {expected['path']}",
        )
        return

    # Une racine ne doit gérer que des Applications enfants.
    for child_path in child_files:
        child = load_yaml(child_path)

        if not isinstance(child, dict):
            error(
                child_path.relative_to(ROOT),
                "le document enfant doit être un objet YAML",
            )
            continue

        if child.get("apiVersion") != "argoproj.io/v1alpha1":
            error(
                child_path.relative_to(ROOT),
                "apiVersion de l'enfant invalide",
            )

        if child.get("kind") != "Application":
            error(
                child_path.relative_to(ROOT),
                "une racine ne doit gérer que des Applications",
            )

    validated += 1
    print(f"[OK] {relative_path}")


def main():
    global validated

    errors.clear()
    validated = 0

    if not BOOTSTRAP_DIR.is_dir():
        print(
            "[ERREUR] Répertoire bootstrap manquant.",
            file=sys.stderr,
        )
        return 1

    actual_files = {
        path.name
        for path in BOOTSTRAP_DIR.glob("*.yaml")
    }

    expected_files = set(EXPECTED_ROOTS)

    if actual_files != expected_files:
        missing = expected_files - actual_files
        unexpected = actual_files - expected_files

        if missing:
            error(
                "gitops/bootstrap",
                f"racines manquantes : {sorted(missing)}",
            )

        if unexpected:
            error(
                "gitops/bootstrap",
                f"fichiers inattendus : {sorted(unexpected)}",
            )

    for filename, expected in EXPECTED_ROOTS.items():
        path = BOOTSTRAP_DIR / filename

        if path.is_file():
            validate_root(path, expected)

    print()
    print(f"Applications racines contrôlées : {validated}")

    if errors:
        print(
            f"Erreurs détectées : {len(errors)}",
            file=sys.stderr,
        )

        for message in errors:
            print(f"[ERREUR] {message}", file=sys.stderr)

        return 1

    print("Validation des Applications racines réussie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
