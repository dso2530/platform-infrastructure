from pathlib import Path

import yaml


def write_yaml(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(content, sort_keys=False),
        encoding="utf-8",
    )


def valid_root(expected):
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": expected["name"],
            "namespace": "argocd",
        },
        "spec": {
            "project": "platform-infrastructure",
            "source": {
                "repoURL": (
                    "https://github.com/"
                    "dso2530/platform-infrastructure.git"
                ),
                "targetRevision": "main",
                "path": expected["path"],
                "directory": {"recurse": True},
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "argocd",
            },
            "syncPolicy": {},
        },
    }


def valid_child():
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": "test-child"},
        "spec": {},
    }


def prepare_root_environment(tmp_path, validator):
    validator.ROOT = tmp_path
    validator.BOOTSTRAP_DIR = tmp_path / "gitops" / "bootstrap"
    validator.APPLICATIONS_DIR = tmp_path / "gitops" / "applications"

    validator.BOOTSTRAP_DIR.mkdir(parents=True)

    for filename, expected in validator.EXPECTED_ROOTS.items():
        root_path = validator.BOOTSTRAP_DIR / filename
        write_yaml(root_path, valid_root(expected))

        child_dir = tmp_path / expected["path"]
        write_yaml(child_dir / "child.yaml", valid_child())

    return validator.BOOTSTRAP_DIR


def test_valid_root_is_accepted(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    write_yaml(target_dir / "child.yaml", valid_child())

    validator.ROOT = tmp_path

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, valid_root(expected))

    validator.validate_root(root_path, expected)

    assert validator.errors == []
    assert validator.validated == 1


def test_root_with_invalid_name_is_rejected(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    write_yaml(target_dir / "child.yaml", valid_child())

    validator.ROOT = tmp_path

    document = valid_root(expected)
    document["metadata"]["name"] = "wrong-root"

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, document)

    validator.validate_root(root_path, expected)

    assert any("metadata.name" in error for error in validator.errors)


def test_root_cannot_reference_prepared(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    write_yaml(target_dir / "child.yaml", valid_child())

    validator.ROOT = tmp_path

    document = valid_root(expected)
    document["spec"]["source"]["path"] = (
        "gitops/applications/prepared"
    )

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, document)

    validator.validate_root(root_path, expected)

    assert any(
        "source.path" in error or "prepared" in error
        for error in validator.errors
    )


def test_root_cannot_use_automated_sync(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    write_yaml(target_dir / "child.yaml", valid_child())

    validator.ROOT = tmp_path

    document = valid_root(expected)
    document["spec"]["syncPolicy"] = {
        "automated": {"prune": True}
    }

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, document)

    validator.validate_root(root_path, expected)

    assert any(
        "synchronisation automatique" in error
        for error in validator.errors
    )


def test_root_requires_recursive_directory(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    write_yaml(target_dir / "child.yaml", valid_child())

    validator.ROOT = tmp_path

    document = valid_root(expected)
    document["spec"]["source"]["directory"]["recurse"] = False

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, document)

    validator.validate_root(root_path, expected)

    assert any(
        "recurse doit être true" in error
        for error in validator.errors
    )


def test_root_rejects_non_application_child(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    target_dir = tmp_path / expected["path"]
    child = valid_child()
    child["kind"] = "ConfigMap"
    write_yaml(target_dir / "child.yaml", child)

    validator.ROOT = tmp_path

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, valid_root(expected))

    validator.validate_root(root_path, expected)

    assert any(
        "Applications" in error
        for error in validator.errors
    )


def test_root_requires_at_least_one_child(tmp_path, root_validator):
    validator = root_validator
    expected = next(iter(validator.EXPECTED_ROOTS.values()))

    (tmp_path / expected["path"]).mkdir(parents=True)

    validator.ROOT = tmp_path

    root_path = tmp_path / "root.yaml"
    write_yaml(root_path, valid_root(expected))

    validator.validate_root(root_path, expected)

    assert any(
        "aucune Application enfant" in error
        for error in validator.errors
    )


def test_main_accepts_both_expected_roots(tmp_path, root_validator):
    validator = root_validator
    prepare_root_environment(tmp_path, validator)

    assert validator.main() == 0
    assert validator.validated == 2
    assert validator.errors == []


def test_main_rejects_missing_root_file(tmp_path, root_validator):
    validator = root_validator
    bootstrap_dir = prepare_root_environment(tmp_path, validator)

    (bootstrap_dir / "ai-public-benefits-root.yaml").unlink()

    assert validator.main() == 1
    assert any(
        "racines manquantes" in error
        for error in validator.errors
    )


def test_main_rejects_unexpected_root_file(tmp_path, root_validator):
    validator = root_validator
    bootstrap_dir = prepare_root_environment(tmp_path, validator)

    write_yaml(
        bootstrap_dir / "unexpected-root.yaml",
        valid_child(),
    )

    assert validator.main() == 1
    assert any(
        "fichiers inattendus" in error
        for error in validator.errors
    )


def test_main_resets_state_between_runs(tmp_path, root_validator):
    validator = root_validator
    prepare_root_environment(tmp_path, validator)

    validator.errors.append("ancienne erreur")
    validator.validated = 99

    assert validator.main() == 0
    assert validator.errors == []
    assert validator.validated == 2