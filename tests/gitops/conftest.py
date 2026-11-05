import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts" / "gitops"

sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def yaml_validator():
    import validate_yaml

    validate_yaml.errors.clear()
    validate_yaml.validated = 0

    return validate_yaml

@pytest.fixture
def project_validator():
    import validate_projects

    validate_projects.errors.clear()
    validate_projects.validated = 0

    return validate_projects

@pytest.fixture
def application_validator():
    import validate_applications

    validate_applications.errors.clear()
    validate_applications.projects.clear()
    validate_applications.validated = 0

    return validate_applications    

@pytest.fixture
def root_validator():
    import validate_roots

    validate_roots.errors.clear()
    validate_roots.validated = 0

    return validate_roots

@pytest.fixture
def project_reference_validator():
    import validate_project_references

    validate_project_references.errors.clear()
    validate_project_references.projects.clear()
    validate_project_references.references.clear()
    validate_project_references.validated = 0

    return validate_project_references

@pytest.fixture
def prepared_detector():
    import detect_prepared_changes

    return detect_prepared_changes