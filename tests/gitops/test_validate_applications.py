from pathlib import Path

import yaml


def write_yaml(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(content, stream, sort_keys=False)


def setup_environment(tmp_path, monkeypatch, validator):
    root = tmp_path

    projects_dir = root / "gitops" / "projects"
    applications_dir = root / "gitops" / "applications"

    projects_dir.mkdir(parents=True)
    applications_dir.mkdir(parents=True)

    monkeypatch.setattr(validator, "ROOT", root)
    monkeypatch.setattr(validator, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(validator, "APPLICATIONS_DIR", applications_dir)

    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {
            "name": "test-project",
            "namespace": "argocd",
        },
        "spec": {
            "sourceRepos": [
                "https://github.com/example/*.git",
            ],
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default",
                },
            ],
        },
    }

    write_yaml(
        projects_dir / "test-project.yaml",
        project,
    )

    return projects_dir, applications_dir


def valid_application():
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": "test-app",
            "namespace": "argocd",
        },
        "spec": {
            "project": "test-project",
            "source": {
                "repoURL": "https://github.com/example/test.git",
                "targetRevision": "main",
                "path": "deploy",
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "default",
            },
        },
    }


def prepare_application(
    tmp_path,
    monkeypatch,
    validator,
    application=None,
    environment="dev",
):
    _, applications_dir = setup_environment(
        tmp_path,
        monkeypatch,
        validator,
    )

    application_path = (
        applications_dir
        / "test"
        / environment
        / "test-app.yaml"
    )

    write_yaml(
        application_path,
        application or valid_application(),
    )

    validator.projects["test-project"] = {
        "sourceRepos": [
            "https://github.com/example/*.git",
        ],
        "destinations": [
            {
                "server": "https://kubernetes.default.svc",
                "namespace": "default",
            },
        ],
    }

    return application_path


def test_validate_application_accepts_valid_application(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
    )

    validator.validate_application(application_path)

    assert validator.errors == []
    assert validator.validated == 1


def test_validate_application_rejects_invalid_api_version(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["apiVersion"] = "v1"

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("apiVersion" in error for error in validator.errors)


def test_validate_application_rejects_invalid_kind(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["kind"] = "AppProject"

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("kind doit être Application" in error
               for error in validator.errors)


def test_validate_application_rejects_filename_mismatch(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["metadata"]["name"] = "another-app"

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("nom du fichier incohérent" in error
               for error in validator.errors)


def test_validate_application_rejects_missing_project(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["spec"]["project"] = "unknown-project"

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("AppProject inexistant" in error
               for error in validator.errors)


def test_validate_application_rejects_unauthorized_repository(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["spec"]["source"]["repoURL"] = (
        "https://github.com/unauthorized/repository.git"
    )

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("dépôt non autorisé" in error
               for error in validator.errors)


def test_validate_application_rejects_unauthorized_destination(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["spec"]["destination"]["namespace"] = "kube-system"

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any("destination non autorisée" in error
               for error in validator.errors)


def test_validate_application_rejects_source_and_sources_together(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["spec"]["sources"] = [
        {
            "repoURL": "https://github.com/example/other.git",
            "targetRevision": "main",
            "path": "deploy",
        }
    ]

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any(
        "source et sources" in error
        for error in validator.errors
    )


def test_validate_application_rejects_missing_helm_reference(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()

    application["spec"].pop("source")
    application["spec"]["sources"] = [
        {
            "repoURL": "https://github.com/example/test.git",
            "targetRevision": "main",
            "chart": "test-chart",
            "helm": {
                "valueFiles": [
                    "$missing/values.yaml",
                ],
            },
        },
    ]

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
    )

    validator.validate_application(application_path)

    assert any(
        "référence Helm $missing absente" in error
        for error in validator.errors
    )


def test_validate_application_rejects_automated_sync_in_dev(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    application = valid_application()
    application["spec"]["syncPolicy"] = {
        "automated": {
            "prune": True,
            "selfHeal": True,
        }
    }

    application_path = prepare_application(
        tmp_path,
        monkeypatch,
        validator,
        application,
        environment="dev",
    )

    validator.validate_application(application_path)

    assert any(
        "synchronisation automatique est interdite" in error
        for error in validator.errors
    )


def test_main_validates_all_applications(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    _, applications_dir = setup_environment(
        tmp_path,
        monkeypatch,
        validator,
    )

    application_path = (
        applications_dir
        / "test"
        / "dev"
        / "test-app.yaml"
    )

    write_yaml(application_path, valid_application())

    assert validator.main() == 0
    assert validator.validated == 1
    assert validator.errors == []


def test_main_resets_validation_state_between_runs(
    application_validator,
    tmp_path,
    monkeypatch,
):
    validator = application_validator

    _, applications_dir = setup_environment(
        tmp_path,
        monkeypatch,
        validator,
    )

    application_path = (
        applications_dir
        / "test"
        / "dev"
        / "test-app.yaml"
    )

    write_yaml(application_path, valid_application())

    assert validator.main() == 0
    assert validator.validated == 1
    assert validator.errors == []

    invalid_application = valid_application()
    invalid_application["apiVersion"] = "v1"

    write_yaml(application_path, invalid_application)

    assert validator.main() == 1
    assert validator.validated == 1
    assert any(
        "apiVersion" in error
        for error in validator.errors
    )

    write_yaml(application_path, valid_application())

    assert validator.main() == 0
    assert validator.validated == 1
    assert validator.errors == []
