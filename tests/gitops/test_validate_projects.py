import yaml


def create_project(tmp_path, name="test-project", **overrides):
    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {
            "name": name,
            "namespace": "argocd",
        },
        "spec": {
            "sourceRepos": [
                "https://github.com/example/repo.git",
            ],
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default",
                },
            ],
            "clusterResourceWhitelist": [],
            "namespaceResourceWhitelist": [
                {
                    "group": "",
                    "kind": "ConfigMap",
                },
            ],
        },
    }

    for key, value in overrides.items():
        if key == "metadata":
            project["metadata"].update(value)
        elif key == "spec":
            project["spec"].update(value)
        else:
            project[key] = value

    projects_dir = tmp_path / "gitops" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    path = projects_dir / f"{name}.yaml"
    path.write_text(
        yaml.safe_dump(project, sort_keys=False),
        encoding="utf-8",
    )

    return path


def test_validate_project_accepts_valid_project(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(tmp_path)

    validator.validate_project(path)

    assert validator.errors == []
    assert validator.validated == 1


def test_validate_project_rejects_invalid_api_version(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(tmp_path, apiVersion="v1")

    validator.validate_project(path)

    assert any("apiVersion" in error for error in validator.errors)


def test_validate_project_rejects_invalid_kind(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(tmp_path, kind="Application")

    validator.validate_project(path)

    assert any("kind" in error for error in validator.errors)


def test_validate_project_rejects_filename_mismatch(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        metadata={"name": "another-project"},
    )

    validator.validate_project(path)

    assert any(
        "nom du fichier incohérent" in error
        for error in validator.errors
    )


def test_validate_project_rejects_invalid_namespace(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        metadata={"namespace": "default"},
    )

    validator.validate_project(path)

    assert any(
        "metadata.namespace" in error
        for error in validator.errors
    )


def test_validate_project_rejects_empty_source_repositories(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        spec={"sourceRepos": []},
    )

    validator.validate_project(path)

    assert any(
        "sourceRepos" in error
        for error in validator.errors
    )


def test_validate_project_rejects_duplicate_source_repositories(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    repository = "https://github.com/example/repo.git"

    path = create_project(
        tmp_path,
        spec={"sourceRepos": [repository, repository]},
    )

    validator.validate_project(path)

    assert any(
        "doublons" in error
        for error in validator.errors
    )


def test_validate_project_rejects_destination_with_server_and_name(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        spec={
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                    "name": "local-cluster",
                    "namespace": "default",
                },
            ],
        },
    )

    validator.validate_project(path)

    assert any(
        "exactement" in error
        for error in validator.errors
    )


def test_validate_project_rejects_destination_without_namespace(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        spec={
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                },
            ],
        },
    )

    validator.validate_project(path)

    assert any(
        "namespace est obligatoire" in error
        for error in validator.errors
    )


def test_validate_project_rejects_empty_resource_kind(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = create_project(
        tmp_path,
        spec={
            "namespaceResourceWhitelist": [
                {
                    "group": "",
                    "kind": "",
                },
            ],
        },
    )

    validator.validate_project(path)

    assert any(
        "kind ne peut pas être vide" in error
        for error in validator.errors
    )


def test_main_validates_all_projects(
    tmp_path,
    monkeypatch,
    project_validator,
    capsys,
):
    validator = project_validator

    projects_dir = tmp_path / "gitops" / "projects"

    create_project(tmp_path, name="first-project")
    create_project(tmp_path, name="second-project")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "PROJECTS_DIR", projects_dir)

    assert validator.main() == 0
    assert validator.validated == 2
    assert validator.errors == []

    assert "AppProjects contrôlés : 2" in capsys.readouterr().out


def test_main_fails_when_no_projects_exist(
    tmp_path,
    monkeypatch,
    project_validator,
    capsys,
):
    validator = project_validator

    projects_dir = tmp_path / "gitops" / "projects"
    projects_dir.mkdir(parents=True)

    monkeypatch.setattr(validator, "PROJECTS_DIR", projects_dir)

    assert validator.main() == 1

    assert (
        "Aucun AppProject trouvé"
        in capsys.readouterr().err
    )


def test_main_resets_validation_state_between_runs(
    tmp_path,
    monkeypatch,
    project_validator,
):
    validator = project_validator

    projects_dir = tmp_path / "gitops" / "projects"

    create_project(tmp_path, name="first-project")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "PROJECTS_DIR", projects_dir)

    assert validator.main() == 0
    assert validator.validated == 1

    validator.errors.append("ancienne erreur")

    assert validator.main() == 0
    assert validator.validated == 1
    assert validator.errors == []