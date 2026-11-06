import subprocess
from pathlib import Path

import pytest
import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]

CHART_DIR = ROOT_DIR / "helm" / "charts" / "spring-boot-microservice"

COMMON_VALUES = ROOT_DIR / "helm" / "environments" / "dev" / "common.yaml"
DOCUMENT_SERVICE_VALUES = (
    ROOT_DIR / "helm" / "environments" / "dev" / "document-service.yaml"
)


@pytest.fixture(scope="session")
def helm_binary():
    result = subprocess.run(
        ["helm", "version", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail("Helm n'est pas disponible sur cette machine.")

    return "helm"


@pytest.fixture(scope="session")
def chart_dir():
    assert CHART_DIR.is_dir(), f"Chart introuvable : {CHART_DIR}"
    return CHART_DIR


@pytest.fixture(scope="session")
def service_values():
    assert COMMON_VALUES.is_file()
    assert DOCUMENT_SERVICE_VALUES.is_file()

    return [COMMON_VALUES, DOCUMENT_SERVICE_VALUES]


@pytest.fixture
def render_chart(helm_binary, chart_dir, service_values):
    def _render(*overrides):
        command = [
            helm_binary,
            "template",
            "document-service",
            str(chart_dir),
            "--namespace",
            "public-benefits",
        ]

        for values_file in service_values:
            command.extend(["-f", str(values_file)])

        command.extend(overrides)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        return result

    return _render


@pytest.fixture
def parse_manifests():
    def _parse(content):
        return [
            document
            for document in yaml.safe_load_all(content)
            if document is not None
        ]

    return _parse