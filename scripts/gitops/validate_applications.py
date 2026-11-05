#!/usr/bin/env python3

from fnmatch import fnmatchcase
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = ROOT / "gitops" / "projects"
APPLICATIONS_DIR = ROOT / "gitops" / "applications"

errors = []
validated = 0
projects = {}

# Exceptions explicites aux conventions de nommage.
FILE_NAME_EXCEPTIONS = {
    "developer-content-creator/dev/repository-service.yaml":
        "developer-content-creator-repository-service-dev",
}


def error(path, message):
    errors.append(f"{path}: {message}")


def load_yaml(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        error(path.relative_to(ROOT), f"lecture impossible : {exc}")
        return None


def matches_pattern(value, patterns):
    if not isinstance(value, str):
        return False

    return any(
        isinstance(pattern, str) and fnmatchcase(value, pattern)
        for pattern in patterns
    )


def load_projects():
    for path in sorted(PROJECTS_DIR.glob("*.yaml")):
        project = load_yaml(path)

        if not isinstance(project, dict):
            continue

        metadata = project.get("metadata", {})
        spec = project.get("spec", {})

        if isinstance(metadata, dict) and isinstance(spec, dict):
            name = metadata.get("name")

            if isinstance(name, str) and name:
                if name in projects:
                    error(
                        path.relative_to(ROOT),
                        f"AppProject dupliqué : {name}",
                    )
                else:
                    projects[name] = spec


def validate_source(path, source, project_spec, index=None):
    prefix = "source" if index is None else f"sources[{index}]"

    if not isinstance(source, dict):
        error(path, f"{prefix} doit être un objet")
        return

    repo_url = source.get("repoURL")
    target_revision = source.get("targetRevision")
    source_path = source.get("path")
    chart = source.get("chart")
    ref = source.get("ref")

    if not isinstance(repo_url, str) or not repo_url.strip():
        error(path, f"{prefix}.repoURL est obligatoire")
    else:
        allowed_repos = project_spec.get("sourceRepos", [])

        if not matches_pattern(repo_url, allowed_repos):
            error(
                path,
                f"dépôt non autorisé par AppProject : {repo_url}",
            )

    if not isinstance(target_revision, str) or not target_revision.strip():
        error(path, f"{prefix}.targetRevision est obligatoire")

    if source_path is not None and (
        not isinstance(source_path, str) or not source_path.strip()
    ):
        error(path, f"{prefix}.path est invalide")

    if chart is not None and (
        not isinstance(chart, str) or not chart.strip()
    ):
        error(path, f"{prefix}.chart est invalide")

    if source_path and chart:
        error(
            path,
            f"{prefix} ne doit pas définir simultanément path et chart",
        )

    if ref is not None and (
        not isinstance(ref, str) or not ref.strip()
    ):
        error(path, f"{prefix}.ref est invalide")


def validate_destination(path, destination, project_spec):
    if not isinstance(destination, dict):
        error(path, "spec.destination doit être un objet")
        return

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
            path,
            "spec.destination doit définir exactement "
            "un champ parmi server et name",
        )
        return

    if not isinstance(namespace, str) or not namespace.strip():
        error(path, "spec.destination.namespace est obligatoire")
        return

    allowed = project_spec.get("destinations", [])

    authorized = False

    for rule in allowed:
        if not isinstance(rule, dict):
            continue

        rule_namespace = rule.get("namespace")
        rule_server = rule.get("server")
        rule_name = rule.get("name")

        namespace_allowed = (
            isinstance(rule_namespace, str)
            and fnmatchcase(namespace, rule_namespace)
        )

        if has_server:
            cluster_allowed = (
                isinstance(rule_server, str)
                and fnmatchcase(server, rule_server)
            )
        else:
            cluster_allowed = (
                isinstance(rule_name, str)
                and fnmatchcase(cluster_name, rule_name)
            )

        if namespace_allowed and cluster_allowed:
            authorized = True
            break

    if not authorized:
        cluster = server if has_server else cluster_name

        error(
            path,
            f"destination non autorisée par AppProject : "
            f"cluster={cluster}, namespace={namespace}",
        )


def validate_sources(path, spec, project_spec):
    source = spec.get("source")
    sources = spec.get("sources")

    if source is not None and sources is not None:
        error(
            path,
            "spec ne doit pas définir simultanément source et sources",
        )
        return

    if source is not None:
        validate_source(path, source, project_spec)
        return

    if not isinstance(sources, list) or not sources:
        error(path, "spec.source ou spec.sources doit être défini")
        return

    refs = set()

    for index, item in enumerate(sources):
        validate_source(path, item, project_spec, index)

        if isinstance(item, dict):
            ref = item.get("ref")

            if isinstance(ref, str) and ref:
                if ref in refs:
                    error(path, f"référence source dupliquée : {ref}")

                refs.add(ref)

    # Vérification des références utilisées dans les fichiers Helm.
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            continue

        helm = item.get("helm", {})

        if not isinstance(helm, dict):
            continue

        value_files = helm.get("valueFiles", [])

        if not isinstance(value_files, list):
            error(
                path,
                f"sources[{index}].helm.valueFiles doit être une liste",
            )
            continue

        for value_file in value_files:
            if not isinstance(value_file, str):
                error(
                    path,
                    f"sources[{index}] contient un valueFile invalide",
                )
                continue

            if value_file.startswith("$"):
                reference = value_file.split("/", 1)[0][1:]

                if reference not in refs:
                    error(
                        path,
                        f"référence Helm ${reference} absente de spec.sources",
                    )


def validate_application(path):
    global validated

    relative_path = path.relative_to(ROOT)
    application = load_yaml(path)

    if not isinstance(application, dict):
        error(relative_path, "le document doit être un objet YAML")
        return

    if application.get("apiVersion") != "argoproj.io/v1alpha1":
        error(
            relative_path,
            "apiVersion doit être argoproj.io/v1alpha1",
        )

    if application.get("kind") != "Application":
        error(relative_path, "kind doit être Application")

    metadata = application.get("metadata")
    spec = application.get("spec")

    if not isinstance(metadata, dict):
        error(relative_path, "metadata doit être un objet")
        return

    name = metadata.get("name")

    if not isinstance(name, str) or not name:
        error(relative_path, "metadata.name est obligatoire")
    else:
        relative_name = path.relative_to(
            APPLICATIONS_DIR
        ).as_posix()

        expected_name = FILE_NAME_EXCEPTIONS.get(
            relative_name,
            path.stem,
        )

        if expected_name != name:
            error(
                relative_path,
                f"nom du fichier incohérent avec metadata.name ({name})",
            )

    if metadata.get("namespace") != "argocd":
        error(relative_path, "metadata.namespace doit être argocd")

    if not isinstance(spec, dict):
        error(relative_path, "spec doit être un objet")
        return

    project_name = spec.get("project")

    if not isinstance(project_name, str) or not project_name:
        error(relative_path, "spec.project est obligatoire")
        return

    project_spec = projects.get(project_name)

    if project_spec is None:
        error(relative_path, f"AppProject inexistant : {project_name}")
        return

    validate_sources(relative_path, spec, project_spec)

    validate_destination(
        relative_path,
        spec.get("destination"),
        project_spec,
    )

    # Les Applications actives restent en synchronisation manuelle.
    if path.parent.name == "dev":
        sync_policy = spec.get("syncPolicy", {})

        if isinstance(sync_policy, dict) and "automated" in sync_policy:
            error(
                relative_path,
                "la synchronisation automatique est interdite dans dev/",
            )

    validated += 1
    print(f"[OK] {relative_path}")


def main():
    global validated

    # Réinitialisation de l'état pour les exécutions successives.
    errors.clear()
    projects.clear()
    validated = 0

    if not PROJECTS_DIR.is_dir() or not APPLICATIONS_DIR.is_dir():
        print(
            "[ERREUR] Répertoire GitOps manquant.",
            file=sys.stderr,
        )
        return 1

    load_projects()

    application_files = sorted(
        APPLICATIONS_DIR.rglob("*.yaml")
    )

    if not application_files:
        print(
            "[ERREUR] Aucune Application trouvée.",
            file=sys.stderr,
        )
        return 1

    for path in application_files:
        validate_application(path)

    print()
    print(f"Applications contrôlées : {validated}")

    if errors:
        print(
            f"Erreurs détectées : {len(errors)}",
            file=sys.stderr,
        )

        for message in errors:
            print(f"[ERREUR] {message}", file=sys.stderr)

        return 1

    print("Validation des Applications réussie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
