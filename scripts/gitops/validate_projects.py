#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = ROOT / "gitops" / "projects"

errors = []
validated = 0


def error(path, message):
    errors.append(f"{path}: {message}")


def check_unique(path, values, label):
    if len(values) != len(set(values)):
        error(path, f"{label} contient des doublons")


def validate_project(path):
    global validated

    relative_path = path.relative_to(ROOT)

    try:
        with path.open("r", encoding="utf-8") as stream:
            project = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        error(relative_path, f"lecture impossible : {exc}")
        return

    if not isinstance(project, dict):
        error(relative_path, "le document doit être un objet YAML")
        return

    metadata = project.get("metadata", {})
    spec = project.get("spec", {})

    if project.get("apiVersion") != "argoproj.io/v1alpha1":
        error(relative_path, "apiVersion doit être argoproj.io/v1alpha1")

    if project.get("kind") != "AppProject":
        error(relative_path, "kind doit être AppProject")

    if not isinstance(metadata, dict):
        error(relative_path, "metadata doit être un objet")
        return

    name = metadata.get("name")

    if not name:
        error(relative_path, "metadata.name est obligatoire")
    elif path.stem != name:
        error(
            relative_path,
            f"nom du fichier incohérent avec metadata.name ({name})",
        )

    if metadata.get("namespace") != "argocd":
        error(relative_path, "metadata.namespace doit être argocd")

    if not isinstance(spec, dict):
        error(relative_path, "spec doit être un objet")
        return

    source_repos = spec.get("sourceRepos")
    destinations = spec.get("destinations")
    cluster_resources = spec.get("clusterResourceWhitelist")
    namespace_resources = spec.get("namespaceResourceWhitelist")

    # Validation des dépôts autorisés.
    if not isinstance(source_repos, list) or not source_repos:
        error(relative_path, "spec.sourceRepos doit être une liste non vide")
    else:
        if any(
            not isinstance(repo, str) or not repo.strip()
            for repo in source_repos
        ):
            error(relative_path, "spec.sourceRepos contient une valeur invalide")

        check_unique(relative_path, source_repos, "spec.sourceRepos")

    # Validation des destinations.
    if not isinstance(destinations, list) or not destinations:
        error(relative_path, "spec.destinations doit être une liste non vide")
        destinations = []
    else:
        destination_keys = []

        for index, destination in enumerate(destinations):
            if not isinstance(destination, dict):
                error(relative_path, f"destination[{index}] doit être un objet")
                continue

            server = destination.get("server")
            cluster_name = destination.get("name")
            namespace = destination.get("namespace")

            has_server = isinstance(server, str) and bool(server.strip())
            has_name = (
                isinstance(cluster_name, str)
                and bool(cluster_name.strip())
            )

            if has_server == has_name:
                error(
                    relative_path,
                    f"destination[{index}] doit définir exactement "
                    "un seul champ parmi server et name",
                )

            if not isinstance(namespace, str) or not namespace.strip():
                error(
                    relative_path,
                    f"destination[{index}].namespace est obligatoire",
                )

            destination_keys.append(
                (server or "", cluster_name or "", namespace or "")
            )

        check_unique(
            relative_path,
            destination_keys,
            "spec.destinations",
        )

    # Validation des ressources autorisées.
    for field, resources in (
        ("clusterResourceWhitelist", cluster_resources),
        ("namespaceResourceWhitelist", namespace_resources),
    ):
        if not isinstance(resources, list):
            error(relative_path, f"spec.{field} doit être une liste")
            continue

        resource_keys = []

        for index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                error(relative_path, f"{field}[{index}] doit être un objet")
                continue

            group = resource.get("group")
            kind = resource.get("kind")

            if not isinstance(group, str) or not isinstance(kind, str):
                error(
                    relative_path,
                    f"{field}[{index}] doit définir group et kind",
                )
                continue

            if not kind.strip():
                error(
                    relative_path,
                    f"{field}[{index}].kind ne peut pas être vide",
                )

            resource_keys.append((group, kind))

        check_unique(relative_path, resource_keys, f"spec.{field}")

    # Contrôles spécifiques au projet central.
    if name == "platform-infrastructure":
        expected_repositories = {
            "https://github.com/dso2530/platform-infrastructure.git"
        }

        if set(source_repos or []) != expected_repositories:
            error(
                relative_path,
                "platform-infrastructure doit autoriser uniquement "
                "le dépôt platform-infrastructure",
            )

        expected_destinations = {
            ("https://kubernetes.default.svc", "argocd")
        }

        actual_destinations = {
            (item.get("server"), item.get("namespace"))
            for item in destinations
            if isinstance(item, dict)
        }

        if actual_destinations != expected_destinations:
            error(
                relative_path,
                "platform-infrastructure doit cibler uniquement "
                "argocd sur le cluster local",
            )

        if cluster_resources != []:
            error(
                relative_path,
                "platform-infrastructure ne doit autoriser "
                "aucune ressource de cluster",
            )

        expected_namespace_resources = {
            ("argoproj.io", "Application")
        }

        actual_namespace_resources = {
            (item.get("group"), item.get("kind"))
            for item in namespace_resources or []
            if isinstance(item, dict)
        }

        if actual_namespace_resources != expected_namespace_resources:
            error(
                relative_path,
                "platform-infrastructure doit autoriser uniquement "
                "les ressources Application ArgoCD",
            )

    validated += 1
    print(f"[OK] {relative_path}")


if not PROJECTS_DIR.is_dir():
    print(
        f"[ERREUR] Répertoire absent : {PROJECTS_DIR}",
        file=sys.stderr,
    )
    sys.exit(1)

project_files = sorted(PROJECTS_DIR.glob("*.yaml"))

if not project_files:
    print("[ERREUR] Aucun AppProject trouvé.", file=sys.stderr)
    sys.exit(1)

for project_file in project_files:
    validate_project(project_file)

print()
print(f"AppProjects contrôlés : {validated}")

if errors:
    print(f"Erreurs détectées : {len(errors)}", file=sys.stderr)

    for message in errors:
        print(f"[ERREUR] {message}", file=sys.stderr)

    sys.exit(1)

print("Validation des AppProjects réussie.")
