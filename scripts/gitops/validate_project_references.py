#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]

PROJECTS_DIR = ROOT / "gitops" / "projects"
APPLICATIONS_DIR = ROOT / "gitops" / "applications"
BOOTSTRAP_DIR = ROOT / "gitops" / "bootstrap"

errors = []
projects = {}
references = {}
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


def load_projects():
    for path in sorted(PROJECTS_DIR.glob("*.yaml")):
        project = load_yaml(path)

        if not isinstance(project, dict):
            error(path.relative_to(ROOT), "AppProject invalide")
            continue

        metadata = project.get("metadata")

        if not isinstance(metadata, dict):
            error(path.relative_to(ROOT), "metadata invalide")
            continue

        name = metadata.get("name")

        if not isinstance(name, str) or not name:
            error(path.relative_to(ROOT), "metadata.name manquant")
            continue

        if name in projects:
            error(
                path.relative_to(ROOT),
                f"AppProject dupliqué : {name}",
            )
            continue

        projects[name] = path


def validate_application(path):
    global validated

    application = load_yaml(path)

    if not isinstance(application, dict):
        error(path.relative_to(ROOT), "Application invalide")
        return

    if application.get("kind") != "Application":
        error(
            path.relative_to(ROOT),
            "kind doit être Application",
        )
        return

    metadata = application.get("metadata")

    if not isinstance(metadata, dict):
        error(path.relative_to(ROOT), "metadata invalide")
        return

    name = metadata.get("name")

    spec = application.get("spec")

    if not isinstance(spec, dict):
        error(path.relative_to(ROOT), "spec invalide")
        return

    project = spec.get("project")

    if not isinstance(project, str) or not project:
        error(
            path.relative_to(ROOT),
            "spec.project manquant",
        )
        return

    if project not in projects:
        error(
            path.relative_to(ROOT),
            f"AppProject référencé inexistant : {project}",
        )
        return

    references.setdefault(project, []).append(
        {
            "application": name,
            "path": path.relative_to(ROOT),
        }
    )

    validated += 1


def main():
    global validated

    errors.clear()
    projects.clear()
    references.clear()
    validated = 0
    
    if not PROJECTS_DIR.is_dir():
        print("[ERREUR] Répertoire projects manquant.", file=sys.stderr)
        return 1

    if not APPLICATIONS_DIR.is_dir():
        print("[ERREUR] Répertoire applications manquant.", file=sys.stderr)
        return 1

    if not BOOTSTRAP_DIR.is_dir():
        print("[ERREUR] Répertoire bootstrap manquant.", file=sys.stderr)
        return 1

    load_projects()

    application_files = sorted(APPLICATIONS_DIR.rglob("*.yaml"))
    root_files = sorted(BOOTSTRAP_DIR.glob("*.yaml"))

    for path in application_files + root_files:
        validate_application(path)

    unused_projects = set(projects) - set(references)

    for project in sorted(unused_projects):
        error(
            projects[project].relative_to(ROOT),
            f"AppProject non référencé : {project}",
        )

    print()
    print("===== Références Application / AppProject =====")
    print(f"AppProjects chargés       : {len(projects)}")
    print(f"Applications contrôlées   : {validated}")
    print(f"AppProjects référencés    : {len(references)}")
    print(f"AppProjects non référencés: {len(unused_projects)}")

    if errors:
        print(f"\nErreurs détectées : {len(errors)}", file=sys.stderr)

        for message in errors:
            print(f"[ERREUR] {message}", file=sys.stderr)

        return 1

    print("\n[OK] Toutes les références Application / AppProject sont valides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
