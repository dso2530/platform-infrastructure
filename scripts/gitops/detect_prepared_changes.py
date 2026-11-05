#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def get_comparison():
    event_name = os.getenv("GITHUB_EVENT_NAME", "")

    if event_name in ("pull_request", "push"):
        base = os.getenv("BASE_SHA")
        head = os.getenv("HEAD_SHA")

    elif event_name == "workflow_dispatch":
        try:
            head = run_git("rev-parse", "HEAD")
            base = run_git("rev-parse", "HEAD^")
        except subprocess.CalledProcessError:
            print(
                "[INFO] Aucun commit parent disponible pour la comparaison."
            )
            return None

    else:
        print(f"[INFO] Événement non pris en charge : {event_name}")
        return None

    if not base or not head or base == "0" * 40:
        print("[INFO] Aucun commit de référence disponible.")
        return None

    return base, head


def is_prepared_file(path):
    parts = Path(path).parts

    return (
        len(parts) >= 5
        and parts[0] == "gitops"
        and parts[1] == "applications"
        and bool(parts[2])
        and parts[3] == "prepared"
    )


def get_prepared_changes(base, head):
    output = run_git(
        "diff",
        "--name-status",
        "-M",    
        base,
        head,
        "--",
    )

    changes = []

    for line in output.splitlines():
        fields = line.split("\t")
        status = fields[0]

        if status.startswith(("R", "C")):
            if len(fields) != 3:
                raise ValueError(
                    f"Format Git inattendu pour le statut {status}: {line}"
                )

            old_path, new_path = fields[1:3]

            if (
                is_prepared_file(old_path)
                or is_prepared_file(new_path)
            ):
                changes.append((status, old_path, new_path))

        else:
            if len(fields) != 2:
                raise ValueError(
                    f"Format Git inattendu pour le statut {status}: {line}"
                )

            path = fields[1]

            if is_prepared_file(path):
                changes.append((status, path, None))

    return sorted(changes)


def main():
    print("===== Détection des changements prepared/ =====")

    comparison = get_comparison()

    if comparison is None:
        print("[INFO] Comparaison impossible ou non nécessaire.")
        return 0

    base, head = comparison

    try:
        changes = get_prepared_changes(base, head)

    except (subprocess.CalledProcessError, ValueError) as exc:
        print(
            f"[ERREUR] Comparaison Git impossible : {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"Changements détectés : {len(changes)}")

    if not changes:
        print("[OK] Aucun changement dans prepared/.")
        return 0

    print("\n[ATTENTION] Changements dans prepared/ :")

    labels = {
        "A": "AJOUT",
        "M": "MODIFICATION",
        "D": "SUPPRESSION",
        "T": "TYPE",
    }

    for status, old_path, new_path in changes:
        if status.startswith("R"):
            print(
                f"  [RENOMMAGE] {old_path} -> {new_path}"
            )

        elif status.startswith("C"):
            print(
                f"  [COPIE] {old_path} -> {new_path}"
            )

        else:
            print(
                f"  [{labels.get(status, status)}] {old_path}"
            )

    print(
        "\n[INFO] Les manifests prepared/ restent inactifs. "
        "Aucun déploiement ne sera déclenché."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())