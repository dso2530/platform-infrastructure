import yaml


def write_yaml(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(content, sort_keys=False),
        encoding="utf-8",
    )


def valid_project(name="test-project"):
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": name},
    }


def valid_application(
    name="test-application",
    project="test-project",
):
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name},
        "spec": {"project": project},
    }


def prepare_environment(tmp_path, validator):
    validator.ROOT = tmp_path
    validator.PROJECTS_DIR = tmp_path / "gitops" / "projects"
    validator.APPLICATIONS_DIR = tmp_path / "gitops" / "applications"
    validator.BOOTSTRAP_DIR = tmp_path / "gitops" / "bootstrap"

    validator.PROJECTS_DIR.mkdir(parents=True)
    validator.APPLICATIONS_DIR.mkdir(parents=True)
    validator.BOOTSTRAP_DIR.mkdir(parents=True)

    write_yaml(
        validator.PROJECTS_DIR / "test-project.yaml",
        valid_project(),
    )

    return validator


def test_valid_application_reference_is_accepted(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    application_path = (
        validator.APPLICATIONS_DIR / "application.yaml"
    )
    write_yaml(application_path, valid_application())

    validator.load_projects()
    validator.validate_application(application_path)

    assert validator.errors == []
    assert validator.validated == 1
    assert "test-project" in validator.references


def test_nonexistent_project_reference_is_rejected(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    application_path = (
        validator.APPLICATIONS_DIR / "application.yaml"
    )
    write_yaml(
        application_path,
        valid_application(project="unknown-project"),
    )

    validator.load_projects()
    validator.validate_application(application_path)

    assert any(
        "AppProject référencé inexistant" in error
        for error in validator.errors
    )
    assert validator.validated == 0


def test_missing_project_reference_is_rejected(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    application_path = (
        validator.APPLICATIONS_DIR / "application.yaml"
    )
    application = valid_application()
    del application["spec"]["project"]
    write_yaml(application_path, application)

    validator.load_projects()
    validator.validate_application(application_path)

    assert any(
        "spec.project manquant" in error
        for error in validator.errors
    )


def test_invalid_application_kind_is_rejected(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    application_path = (
        validator.APPLICATIONS_DIR / "application.yaml"
    )
    application = valid_application()
    application["kind"] = "ConfigMap"
    write_yaml(application_path, application)

    validator.load_projects()
    validator.validate_application(application_path)

    assert any(
        "kind doit être Application" in error
        for error in validator.errors
    )


def test_duplicate_project_names_are_rejected(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    write_yaml(
        validator.PROJECTS_DIR / "duplicate-project.yaml",
        valid_project(),
    )

    write_yaml(
        validator.APPLICATIONS_DIR / "application.yaml",
        valid_application(),
    )

    validator.load_projects()

    assert any(
        "AppProject dupliqué" in error
        for error in validator.errors
    )


def test_unused_project_is_rejected(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    assert validator.main() == 1

    assert any(
        "AppProject non référencé" in error
        for error in validator.errors
    )


def test_main_validates_child_and_root_applications(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    write_yaml(
        validator.APPLICATIONS_DIR / "child.yaml",
        valid_application(name="child-application"),
    )

    write_yaml(
        validator.BOOTSTRAP_DIR / "root.yaml",
        valid_application(name="root-application"),
    )

    assert validator.main() == 0
    assert validator.validated == 2
    assert len(validator.references["test-project"]) == 2
    assert validator.errors == []


def test_main_resets_state_between_runs(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator
    prepare_environment(tmp_path, validator)

    write_yaml(
        validator.APPLICATIONS_DIR / "child.yaml",
        valid_application(),
    )

    validator.errors.append("ancienne erreur")
    validator.projects["old-project"] = tmp_path / "old.yaml"
    validator.references["old-project"] = []
    validator.validated = 99

    assert validator.main() == 0

    assert validator.errors == []
    assert set(validator.projects) == {"test-project"}
    assert set(validator.references) == {"test-project"}
    assert validator.validated == 1


def test_main_fails_when_projects_directory_is_missing(
    tmp_path,
    project_reference_validator,
):
    validator = project_reference_validator

    validator.ROOT = tmp_path
    validator.PROJECTS_DIR = tmp_path / "missing-projects"
    validator.APPLICATIONS_DIR = tmp_path / "applications"
    validator.BOOTSTRAP_DIR = tmp_path / "bootstrap"

    validator.APPLICATIONS_DIR.mkdir()
    validator.BOOTSTRAP_DIR.mkdir()

    assert validator.main() == 1