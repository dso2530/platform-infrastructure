#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
GITOPS_DIR = ROOT / "gitops"

errors = []
validated = 0

for path in sorted(GITOPS_DIR.rglob("*.yaml")):
    relative_path = path.relative_to(ROOT)

    try:
        with path.open("r", encoding="utf-8") as stream:
            documents = list(yaml.safe_load_all(stream))

        if not documents:
            errors.append(f"{relative_path}: fichier YAML vide")
            continue

        if any(document is None for document in documents):
            errors.append(f"{relative_path}: document YAML vide")
            continue

        validated += 1
        print(f"[OK] {relative_path}")

    except yaml.YAMLError as exc:
        errors.append(f"{relative_path}: YAML invalide: {exc}")

    except OSError as exc:
        errors.append(f"{relative_path}: erreur de lecture: {exc}")


print()
print(f"Fichiers YAML validés : {validated}")

if errors:
    print(f"Erreurs détectées : {len(errors)}", file=sys.stderr)

    for error in errors:
        print(f"[ERREUR] {error}", file=sys.stderr)

    sys.exit(1)

print("Validation YAML réussie.")
