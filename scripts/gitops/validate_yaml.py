#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
GITOPS_DIR = ROOT / "gitops"

errors = []
validated = 0


def validate_file(path):
    """
    Vérifie la syntaxe et le contenu d'un fichier YAML.

    Retourne True si le fichier est valide, False sinon.
    """
    try:
        with path.open("r", encoding="utf-8") as stream:
            documents = list(yaml.safe_load_all(stream))

    except yaml.YAMLError as exc:
        errors.append(
            f"{path.relative_to(ROOT)}: YAML invalide: {exc}"
        )
        return False

    except OSError as exc:
        errors.append(
            f"{path.relative_to(ROOT)}: erreur de lecture: {exc}"
        )
        return False

    relative_path = path.relative_to(ROOT)

    if not documents:
        errors.append(f"{relative_path}: fichier YAML vide")
        return False

    if any(document is None for document in documents):
        errors.append(f"{relative_path}: document YAML vide")
        return False

    print(f"[OK] {relative_path}")
    return True


def main():
    global validated

    errors.clear()
    validated = 0

    if not GITOPS_DIR.is_dir():
        print(
            "[ERREUR] Répertoire gitops manquant.",
            file=sys.stderr,
        )
        return 1

    yaml_files = sorted(GITOPS_DIR.rglob("*.yaml"))

    if not yaml_files:
        print(
            "[ERREUR] Aucun fichier YAML trouvé.",
            file=sys.stderr,
        )
        return 1

    for path in yaml_files:
        if validate_file(path):
            validated += 1

    print()
    print(f"Fichiers YAML contrôlés : {len(yaml_files)}")
    print(f"Fichiers YAML valides   : {validated}")

    if errors:
        print(
            f"Erreurs détectées : {len(errors)}",
            file=sys.stderr,
        )

        for message in errors:
            print(f"[ERREUR] {message}", file=sys.stderr)

        return 1

    print("Validation YAML réussie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
